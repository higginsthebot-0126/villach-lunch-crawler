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

function render(menus){
  const app = $('#app');
  app.innerHTML = '';

  const grouped = groupByDay(menus);
  if (grouped.length === 0){
    app.innerHTML = '<div class="day"><h2>Aucune donnée</h2><div class="sub">Vérifie le fichier docs/sample.json.</div></div>';
    return;
  }

  for (const [day, dayMenus] of grouped){
    const dayEl = document.createElement('section');
    dayEl.className = 'day';
    dayEl.innerHTML = `<h2>${day}</h2>`;

    for (const m of dayMenus){
      const src = m.source || m.restaurant || m.name || 'source';
      const url = m.url || m.sourceUrl || '';
      const meta = document.createElement('div');
      meta.className = 'meta';
      meta.innerHTML = `
        <span class="chip">${src}</span>
        ${url ? `<span class="chip"><a href="${url}" target="_blank" rel="noopener">ouvrir</a></span>` : ''}
      `;
      dayEl.appendChild(meta);

      const items = m.items || [];
      const itemsEl = document.createElement('div');
      itemsEl.className = 'items';

      for (const it of items){
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

    app.appendChild(dayEl);
  }
}

async function load(){
  const status = $('#status');
  status.textContent = 'Chargement…';
  try{
    const res = await fetch('./sample.json', { cache: 'no-store' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    // the CLI outputs a list of DailyMenu objects
    render(Array.isArray(data) ? data : (data.menus || []));
    status.textContent = `OK (${new Date().toLocaleTimeString()})`;
  }catch(e){
    status.textContent = `Erreur: ${e.message}`;
  }
}

$('#reload').addEventListener('click', load);
load();
