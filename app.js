/**
 * High Lakes Explorer — app.js
 * Interactive Leaflet map for WA WDFW High Lakes (King, Kittitas, Chelan)
 */

// ── State ─────────────────────────────────────────────────────────
const state = {
  lakes: [],
  filtered: [],
  activeMarkers: new Map(),   // lake.name → L.CircleMarker
  activeListItem: null,
  filters: {
    search: '',
    county: 'all',
    species: 'all',
    camping: 'all',
    maxDist: 15,
    maxGain: 5000,
    minElev: 3000,
  }
};

// ── Elevation → color mapping ─────────────────────────────────────
function elevColor(elev) {
  if (elev >= 7000) return '#1a4e6e';
  if (elev >= 6000) return '#2c7da0';
  if (elev >= 4500) return '#45b7d1';
  return '#4ecdc4';
}

function elevRadius(acres) {
  if (!acres || acres <= 0) return 5;
  const r = 4 + Math.sqrt(acres) * 0.9;
  return Math.min(r, 14);
}

// ── Map init ─────────────────────────────────────────────────────
const map = L.map('map', {
  center: [47.5, -121.0],
  zoom: 9,
  zoomControl: true,
  preferCanvas: true,
});

// Base layer: USGS Topo
L.tileLayer('https://basemap.nationalmap.gov/arcgis/rest/services/USGSHydroNHD/MapServer/tile/{z}/{y}/{x}', {
  attribution: '© USGS National Map · WDFW',
  maxZoom: 16,
  opacity: 0.9,
}).addTo(map);

// Slight overlay for readability
L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager_only_labels/{z}/{x}/{y}{r}.png', {
  attribution: '',
  maxZoom: 19,
  opacity: 0.5,
}).addTo(map);

// ── Popup builder ─────────────────────────────────────────────────
function buildPopup(lake) {
  const campIcon = lake.camping && lake.camping.toLowerCase().startsWith('yes')
    ? `<span class="camping-yes">⛺ ${lake.camping}</span>`
    : `<span class="camping-no">✗ No camping</span>`;

  const speciesHtml = (lake.species || [])
    .map(s => `<span class="species-tag">${s}</span>`).join('');

  const trailHtml = (lake.trailhead_name && lake.trailhead_name !== 'Unknown')
    ? `<div class="popup-section">
        <div class="popup-section-title">🥾 Trailhead</div>
        <div class="popup-section-content">
          <strong>${lake.trailhead_name}</strong><br/>
          ${lake.hiking_distance_miles !== 'unknown' ? `${lake.hiking_distance_miles} mi` : ''}
          ${lake.elevation_gain_ft !== 'unknown' ? ` · +${Number(lake.elevation_gain_ft).toLocaleString()} ft gain` : ''}
        </div>
      </div>`
    : '';

  const stockHtml = (lake.stocking_history && lake.stocking_history.length > 0)
    ? `<div class="popup-section">
        <div class="popup-section-title">🐟 Recent Stocking</div>
        <table class="stocking-table">
          <tr><th>Year</th><th>Species</th><th>Count</th></tr>
          ${lake.stocking_history.slice(-3).map(s =>
            `<tr><td>${s.year}</td><td>${s.species}</td><td>${s.count.toLocaleString()}</td></tr>`
          ).join('')}
        </table>
      </div>`
    : '';

  const wildHtml = (lake.wilderness_area && lake.wilderness_area !== 'unknown')
    ? `<div class="popup-section">
        <div class="popup-section-title">🌲 Wilderness</div>
        <div class="popup-section-content">${lake.wilderness_area}</div>
      </div>`
    : '';

  return `
    <div>
      <div class="popup-header">
        <div class="popup-lake-name">${lake.name}</div>
        <div class="popup-county">${lake.county} County, WA</div>
      </div>
      <div class="popup-body">
        <div class="popup-stats">
          <div class="popup-stat">
            <div class="popup-stat-val">${lake.elevation_ft.toLocaleString()} ft</div>
            <div class="popup-stat-label">Elevation</div>
          </div>
          <div class="popup-stat">
            <div class="popup-stat-val">${lake.acres > 0 ? lake.acres.toFixed(1) : '—'} ac</div>
            <div class="popup-stat-label">Surface Area</div>
          </div>
        </div>
        ${speciesHtml ? `<div class="popup-species">${speciesHtml}</div>` : ''}
        <div class="popup-section">
          <div class="popup-section-title">⛺ Camping</div>
          <div class="popup-camping">${campIcon}</div>
        </div>
        ${trailHtml}
        ${wildHtml}
        ${stockHtml}
        ${lake.access_description && lake.access_description !== 'unknown'
          ? `<div class="popup-section">
              <div class="popup-section-title">🗺 Access</div>
              <div class="popup-section-content">${lake.access_description}</div>
            </div>`
          : ''}
        <a class="popup-link" href="${lake.source_url}" target="_blank" rel="noopener">
          View on WDFW →
        </a>
      </div>
    </div>
  `;
}

// ── Marker management ─────────────────────────────────────────────
function createMarker(lake) {
  const marker = L.circleMarker([lake.latitude, lake.longitude], {
    radius: elevRadius(lake.acres),
    fillColor: elevColor(lake.elevation_ft),
    color: 'rgba(255,255,255,0.85)',
    weight: 1.5,
    opacity: 1,
    fillOpacity: 0.85,
  }).addTo(map);

  marker.bindPopup(buildPopup(lake), {
    maxWidth: 300,
    className: 'lake-popup',
  });

  marker.on('click', () => {
    highlightListItem(lake.name);
  });

  return marker;
}

function clearMarkers() {
  state.activeMarkers.forEach(m => map.removeLayer(m));
  state.activeMarkers.clear();
}

function renderMarkers(lakes) {
  clearMarkers();
  lakes.forEach(lake => {
    if (lake.latitude && lake.longitude && lake.latitude !== 0) {
      const m = createMarker(lake);
      state.activeMarkers.set(lake.name, m);
    }
  });
  updateCount(lakes.length);
}

// ── Lake list ─────────────────────────────────────────────────────
function renderList(lakes) {
  const ul = document.getElementById('lake-list');
  const empty = document.getElementById('list-empty');
  const label = document.getElementById('list-count-label');

  ul.innerHTML = '';
  label.textContent = `Showing ${lakes.length}`;

  if (lakes.length === 0) {
    empty.style.display = 'flex';
    return;
  }
  empty.style.display = 'none';

  const sorted = [...lakes].sort((a, b) => a.name.localeCompare(b.name));
  sorted.forEach((lake, i) => {
    const li = document.createElement('li');
    li.className = 'lake-item';
    li.style.animationDelay = `${Math.min(i * 8, 200)}ms`;
    li.dataset.name = lake.name;

    const speciesList = (lake.species || []).slice(0, 2).join(', ') || 'Unknown species';
    li.innerHTML = `
      <div class="lake-dot" style="background:${elevColor(lake.elevation_ft)}"></div>
      <div class="lake-item-info">
        <div class="lake-item-name">${lake.name}</div>
        <div class="lake-item-meta">${lake.county} · ${speciesList}</div>
      </div>
      <div class="lake-item-elev">${lake.elevation_ft.toLocaleString()} ft</div>
    `;

    li.addEventListener('click', () => {
      const marker = state.activeMarkers.get(lake.name);
      if (marker) {
        map.setView([lake.latitude, lake.longitude], 13, { animate: true });
        setTimeout(() => marker.openPopup(), 400);
      }
      highlightListItem(lake.name);
    });

    ul.appendChild(li);
  });
}

function highlightListItem(name) {
  if (state.activeListItem) {
    state.activeListItem.classList.remove('active');
  }
  const el = document.querySelector(`.lake-item[data-name="${CSS.escape(name)}"]`);
  if (el) {
    el.classList.add('active');
    el.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    state.activeListItem = el;
  }
}

function updateCount(n) {
  document.getElementById('filtered-count').textContent = n;
}

// ── Filtering ─────────────────────────────────────────────────────
function applyFilters() {
  const f = state.filters;
  const search = f.search.toLowerCase().trim();

  state.filtered = state.lakes.filter(lake => {
    // Search
    if (search && !lake.name.toLowerCase().includes(search)) return false;

    // County
    if (f.county !== 'all' && lake.county !== f.county) return false;

    // Species
    if (f.species !== 'all') {
      const species = lake.species || [];
      if (!species.includes(f.species)) return false;
    }

    // Camping
    if (f.camping !== 'all') {
      const hascamp = lake.camping && lake.camping.toLowerCase().startsWith('yes');
      if (f.camping === 'yes' && !hascamp) return false;
      if (f.camping === 'no' && hascamp) return false;
    }

    // Distance
    if (f.maxDist < 15 && lake.hiking_distance_miles !== 'unknown') {
      const d = parseFloat(lake.hiking_distance_miles);
      if (!isNaN(d) && d > f.maxDist) return false;
    }

    // Elevation gain
    if (f.maxGain < 5000 && lake.elevation_gain_ft !== 'unknown') {
      const g = parseFloat(lake.elevation_gain_ft);
      if (!isNaN(g) && g > f.maxGain) return false;
    }

    // Min lake elevation
    if (f.minElev > 3000 && lake.elevation_ft < f.minElev) return false;

    return true;
  });

  renderMarkers(state.filtered);
  renderList(state.filtered);
}

// ── Pill filter groups ────────────────────────────────────────────
function initPillGroup(groupId, stateKey) {
  const group = document.getElementById(groupId);
  group.addEventListener('click', e => {
    const pill = e.target.closest('.pill');
    if (!pill) return;
    group.querySelectorAll('.pill').forEach(p => p.classList.remove('active'));
    pill.classList.add('active');
    state.filters[stateKey] = pill.dataset.value;
    applyFilters();
  });
}

// ── Range sliders ─────────────────────────────────────────────────
function initRange(id, stateKey, labelId, format) {
  const input = document.getElementById(id);
  const label = document.getElementById(labelId);

  function update() {
    const v = parseFloat(input.value);
    const max = parseFloat(input.max);
    const pct = ((v - parseFloat(input.min)) / (max - parseFloat(input.min))) * 100;
    input.style.setProperty('--fill', pct + '%');
    state.filters[stateKey] = v;
    label.textContent = (v >= max) ? 'Any' : format(v);
    applyFilters();
  }

  input.addEventListener('input', update);
  update();
}

// ── Search ───────────────────────────────────────────────────────
function initSearch() {
  const input = document.getElementById('search-input');
  const clearBtn = document.getElementById('search-clear');

  input.addEventListener('input', () => {
    state.filters.search = input.value;
    clearBtn.classList.toggle('visible', input.value.length > 0);
    applyFilters();
  });

  clearBtn.addEventListener('click', () => {
    input.value = '';
    state.filters.search = '';
    clearBtn.classList.remove('visible');
    applyFilters();
  });
}

// ── Reset ─────────────────────────────────────────────────────────
function initReset() {
  document.getElementById('reset-filters').addEventListener('click', () => {
    // Reset state
    state.filters = { search: '', county: 'all', species: 'all', camping: 'all', maxDist: 15, maxGain: 5000, minElev: 3000 };

    // Reset search
    document.getElementById('search-input').value = '';
    document.getElementById('search-clear').classList.remove('visible');

    // Reset pills
    ['county-filters', 'species-filters', 'camping-filters'].forEach(id => {
      const g = document.getElementById(id);
      g.querySelectorAll('.pill').forEach(p => p.classList.remove('active'));
      g.querySelector('[data-value="all"]').classList.add('active');
    });

    // Reset sliders
    document.getElementById('dist-filter').value = 15;
    document.getElementById('gain-filter').value = 5000;
    document.getElementById('elev-filter').value = 3000;
    ['dist-val', 'gain-val', 'elev-val'].forEach(id => {
      document.getElementById(id).textContent = 'Any';
    });

    // Reset slider fill
    ['dist-filter', 'gain-filter', 'elev-filter'].forEach(id => {
      const el = document.getElementById(id);
      el.style.setProperty('--fill', '100%');
    });

    applyFilters();
  });
}

// ── Mobile sidebar ───────────────────────────────────────────────
function initMobileSidebar() {
  const toggle = document.getElementById('sidebar-toggle');
  const sidebar = document.getElementById('sidebar');

  toggle.addEventListener('click', () => {
    sidebar.classList.toggle('open');
  });

  // Close sidebar when clicking map on mobile
  map.on('click', () => {
    if (window.innerWidth <= 768) {
      sidebar.classList.remove('open');
    }
  });
}

// ── Boot ─────────────────────────────────────────────────────────
async function init() {
  try {
    const resp = await fetch('high_lakes_dataset.json');
    if (!resp.ok) throw new Error('Failed to load dataset');
    state.lakes = await resp.json();

    document.getElementById('visible-count').textContent = state.lakes.length;

    // Init controls
    initSearch();
    initPillGroup('county-filters', 'county');
    initPillGroup('species-filters', 'species');
    initPillGroup('camping-filters', 'camping');
    initRange('dist-filter', 'maxDist', 'dist-val', v => `≤ ${v} mi`);
    initRange('gain-filter', 'maxGain', 'gain-val', v => `≤ ${v.toLocaleString()} ft`);
    initRange('elev-filter', 'minElev', 'elev-val', v => `≥ ${v.toLocaleString()} ft`);
    initReset();
    initMobileSidebar();

    // Initial render
    state.filtered = [...state.lakes];
    renderMarkers(state.filtered);
    renderList(state.filtered);

    // Fit bounds
    const coords = state.lakes
      .filter(l => l.latitude && l.longitude)
      .map(l => [l.latitude, l.longitude]);
    if (coords.length) {
      map.fitBounds(L.latLngBounds(coords).pad(0.05));
    }

  } catch (err) {
    console.error('Init failed:', err);
    document.getElementById('map').innerHTML = `
      <div style="display:flex;align-items:center;justify-content:center;height:100%;
        font-family:'DM Sans',sans-serif;color:#5c4a3a;flex-direction:column;gap:12px;background:#f2f7f5;">
        <p style="font-size:18px;font-weight:600;">⚠ Could not load lake data</p>
        <p style="font-size:13px;color:#8a9a8a;">Make sure high_lakes_dataset.json is present and the page is served via HTTP.</p>
      </div>`;
  }
}

document.addEventListener('DOMContentLoaded', init);
