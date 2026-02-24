const $ = (sel) => document.querySelector(sel);

function isoDate(d){
  try{ return new Date(d).toISOString().slice(0,10); }catch{ return String(d); }
}

function groupByDay(menus){
  const map = new Map();
  for (const m of menus){
    const day = m.day || m.date || m.when || null;
    const k = day ? String(day) : 'unknown';
    if (!map.has(k)) map.set(k, []);
    map.get(k).push(m);
  }
  return Array.from(map.entries()).sort(([a],[b]) => a.localeCompare(b));
}

let DATA = null;

function matchesFilters(menu, item){
  const zoneSel = $('#zone')?.value || 'all';
  const onlyCurry = $('#onlyCurry')?.checked || false;
  const avoidLactose = $('#avoidLactose')?.checked || false;

  const zone = menu.zone || menu.meta?.zone || null;
  if (zoneSel !== 'all' && zone !== zoneSel) return false;

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

  const grouped = groupByDay(menus);
  if (grouped.length === 0){
    app.innerHTML = '<div class="day"><h2>Aucune donnée</h2><div class="sub">Vérifie le fichier docs/data.json.</div></div>';
    return;
  }

  for (const [day, dayMenus] of grouped){
    // Build day section, but drop empty restaurant blocks after filtering
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

        const itemEl = document.createElement('div');
        itemEl.className = 'item';
        itemEl.innerHTML = `<div class="name">${name}</div>`;

        const tagWrap = document.createElement('div');
        tagWrap.className = 'tags';

        if (curry) tagWrap.innerHTML += `<span class="tag ok">curry</span>`;
        if (lactoseRisk) tagWrap.innerHTML += `<span class="tag bad">lactose (risque)</span>`;
        else tagWrap.innerHTML += `<span class="tag ok">sans lactose (prob.)</span>`;

        itemEl.appendChild(tagWrap);
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
    rerender();
    status.textContent = `OK (${new Date().toLocaleTimeString()})`;
  }catch(e){
    status.textContent = `Erreur: ${e.message}`;
  }
}

$('#reload').addEventListener('click', load);
['zone','onlyCurry','avoidLactose'].forEach(id => {
  const el = document.getElementById(id);
  if (el) el.addEventListener('change', rerender);
});
load();
