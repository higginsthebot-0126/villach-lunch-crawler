const $ = (sel) => document.querySelector(sel);

function isoDate(d){
  try{ return new Date(d).toISOString().slice(0,10); }catch{ return String(d); }
}

function uniqSorted(arr){
  return Array.from(new Set(arr.filter(Boolean).map(String))).sort((a,b)=>a.localeCompare(b));
}

function computeDefaultTargetDay(availableDays){
  const days = new Set((availableDays || []).map(String));
  const now = new Date(); // local time (GitHub Pages user's tz)

  const dow = now.getDay(); // 0=Sun..6=Sat

  function addDays(d, n){
    const x = new Date(d);
    x.setDate(x.getDate() + n);
    return x;
  }
  function toISO(d){
    return d.toISOString().slice(0,10);
  }

  // If weekend -> next Monday
  if (dow === 6) { // Saturday
    const cand = toISO(addDays(now, 2));
    return days.has(cand) ? cand : cand;
  }
  if (dow === 0) { // Sunday
    const cand = toISO(addDays(now, 1));
    return days.has(cand) ? cand : cand;
  }

  const h = now.getHours();
  const m = now.getMinutes();
  const before1030 = (h < 10) || (h === 10 && m < 30);

  let target = new Date(now);

  if (before1030){
    // today noon
  } else {
    // after 10:30 -> tomorrow noon; Friday after 10:30 -> Monday
    if (dow === 5){
      target = addDays(target, 3);
    } else {
      target = addDays(target, 1);
    }
  }

  // If target lands on weekend, push to Monday
  const tdow = target.getDay();
  if (tdow === 6) target = addDays(target, 2);
  if (tdow === 0) target = addDays(target, 1);

  const iso = toISO(target);

  // If this day isn't present in data, fallback to nearest available
  if (!days.has(iso)){
    const sorted = Array.from(days).sort((a,b)=>a.localeCompare(b));
    if (sorted.length) return sorted[0];
  }
  return iso;
}

let DATA = null;
let SELECTED_DAY = null;

function matchesFilters(menu, item){
  const zoneSel = $('#zone')?.value || 'all';
  const onlyCurry = $('#onlyCurry')?.checked || false;
  const avoidLactose = $('#avoidLactose')?.checked || false;
  const showNoise = $('#showNoise')?.checked || false;

  const zone = menu.zone || menu.meta?.zone || null;
  if (zoneSel !== 'all' && zone !== zoneSel) return false;

  const qc = item.qc || null;
  if (!showNoise && qc && qc.isNoise) return false;

  const name = item.name || item.text || String(item);
  const tags = (item.tags || []).map(String);
  const allergens = (item.allergens || item.allergenes || []);
  const lactoseRisk = item.lactoseRisk || (Array.isArray(allergens) && allergens.includes('G'));
  const curry = tags.includes('curry') || /curry/i.test(name);

  if (onlyCurry && !curry) return false;
  if (avoidLactose && lactoseRisk) return false;
  return true;
}

function render(menus){
  const app = $('#app');
  app.innerHTML = '';

  if (!Array.isArray(menus) || menus.length === 0){
    app.innerHTML = '<div class="day"><h2>Aucune donnée</h2><div class="sub">Vérifie le fichier docs/data.json.</div></div>';
    return;
  }

  const daySel = $('#daySelect');
  const selected = (daySel && daySel.value) ? daySel.value : SELECTED_DAY;

  const visibleMenus = (selected && selected !== 'all')
    ? menus.filter(m => String(m.day || m.date || m.when || '') === String(selected))
    : menus;

  const days = uniqSorted(visibleMenus.map(m => m.day || m.date || m.when));
  if (days.length === 0){
    app.innerHTML = '<div class="day"><h2>0 résultat</h2><div class="sub">Aucun menu pour le jour sélectionné.</div></div>';
    return;
  }

  for (const day of days){
    const dayMenus = visibleMenus.filter(m => String(m.day || m.date || m.when || '') === String(day));

    const dayEl = document.createElement('section');
    dayEl.className = 'day';
    dayEl.innerHTML = `<h2>${day}</h2>`;

    let anyInDay = false;

    for (const m of dayMenus){
      const items = m.items || [];
      const kept = items.filter(it => matchesFilters(m, it));
      if (kept.length === 0) continue;
      anyInDay = true;

      const src = m.source || m.restaurant || m.name || 'source';
      const url = m.url_menu || m.url || m.sourceUrl || '';
      const zone = m.zone || m.meta?.zone || '';

      const meta = document.createElement('div');
      meta.className = 'meta';
      meta.innerHTML = `
        <span class="chip">${src}</span>
        ${zone ? `<span class="chip">${zone}</span>` : ''}
        ${url ? `<span class="chip"><a href="${url}" target="_blank" rel="noopener">menu</a></span>` : ''}
      `;
      dayEl.appendChild(meta);

      const itemsEl = document.createElement('div');
      itemsEl.className = 'items';

      for (const it of kept){
        const name = it.name || it.text || String(it);
        const tags = (it.tags || []).map(String);
        const allergens = (it.allergens || it.allergenes || []);
        const lactoseRisk = it.lactoseRisk || (Array.isArray(allergens) && allergens.includes('G'));
        const curry = tags.includes('curry') || /curry/i.test(name);
        const qc = it.qc || null;

        const itemEl = document.createElement('div');
        itemEl.className = 'item' + (qc?.isNoise ? ' noise' : '');
        itemEl.innerHTML = `<div class="name">${name}</div>`;

        const tagWrap = document.createElement('div');
        tagWrap.className = 'tags';

        if (curry) tagWrap.innerHTML += `<span class="tag ok">curry</span>`;
        if (lactoseRisk) tagWrap.innerHTML += `<span class="tag bad">lactose (risque)</span>`;
        else tagWrap.innerHTML += `<span class="tag ok">sans lactose (prob.)</span>`;

        if (qc?.isNoise) tagWrap.innerHTML += `<span class="tag warn">bruit</span>`;
        if (qc && typeof qc.confidence === 'number' && qc.confidence < 0.8) tagWrap.innerHTML += `<span class="tag warn">conf ${Math.round(qc.confidence*100)}%</span>`;

        itemEl.appendChild(tagWrap);

        if (qc?.isNoise && (qc.flags || []).length){
          const dbg = document.createElement('div');
          dbg.className = 'qc';
          dbg.textContent = `QC: ${(qc.flags || []).join(', ')}`;
          itemEl.appendChild(dbg);
        }

        itemsEl.appendChild(itemEl);
      }

      dayEl.appendChild(itemsEl);
    }

    if (anyInDay) app.appendChild(dayEl);
  }

  if (app.innerHTML.trim() === ''){
    app.innerHTML = '<div class="day"><h2>0 résultat</h2><div class="sub">Aucun plat ne correspond aux filtres.</div></div>';
  }
}

function initDaySelect(menus){
  const sel = $('#daySelect');
  if (!sel) return;

  const days = uniqSorted((menus || []).map(m => m.day || m.date || m.when));
  sel.innerHTML = '';
  for (const d of days){
    const opt = document.createElement('option');
    opt.value = d;
    opt.textContent = d;
    sel.appendChild(opt);
  }

  // Optional "all"
  const optAll = document.createElement('option');
  optAll.value = 'all';
  optAll.textContent = 'tous';
  sel.appendChild(optAll);

  const def = computeDefaultTargetDay(days);
  SELECTED_DAY = def;
  sel.value = days.includes(def) ? def : (days[0] || 'all');
}

function rerender(){
  if (!DATA) return;
  const menus = Array.isArray(DATA) ? DATA : (DATA.menus || []);
  render(menus);
}

async function load(){
  const status = $('#status');
  status.textContent = 'Chargement…';
  try{
    const res = await fetch('./data.json', { cache: 'no-store' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    DATA = await res.json();

    const menus = Array.isArray(DATA) ? DATA : (DATA.menus || []);
    initDaySelect(menus);

    rerender();
    status.textContent = `OK (${new Date().toLocaleTimeString()})`;
  }catch(e){
    status.textContent = `Erreur: ${e.message}`;
  }
}

$('#reload')?.addEventListener('click', load);
['daySelect','zone','onlyCurry','avoidLactose','showNoise'].forEach(id => {
  const el = document.getElementById(id);
  if (el) el.addEventListener('change', rerender);
});

load();
