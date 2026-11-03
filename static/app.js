const $ = (sel) => document.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const api = (path, opts) => fetch(path, opts).then((r) => (r.ok ? r.json() : Promise.reject(r)));

const fmt = (v) => {
  if (v == null) return "—";
  const a = Math.abs(v);
  if (a >= 1e9) return (v / 1e9).toFixed(2) + "B";
  if (a >= 1e6) return (v / 1e6).toFixed(2) + "M";
  if (a >= 1e4) return Math.round(v / 1e3) + "k";
  if (a >= 100) return Math.round(v).toLocaleString();
  return (+v.toPrecision(3)).toString();
};

const compare = new Set();
let priceChart = null;

// ---------- tabs ----------
function showTab(name) {
  document.querySelectorAll("button.tab").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  document.querySelectorAll(".panel").forEach((p) => (p.hidden = p.id !== `tab-${name}`));
  if (name === "compare") renderCompare();
}
document.querySelectorAll("button.tab").forEach((b) => b.addEventListener("click", () => showTab(b.dataset.tab)));

// ---------- provenance rendering ----------
function sourceLine(src) {
  if (!src) return "";
  const title = src.url ? `<a href="${esc(src.url)}" target="_blank" rel="noopener">${esc(src.title)}</a>` : esc(src.title);
  const unverified = src.verified ? "" : `<span class="badge unverified" title="Value not yet checked against the document">unverified</span>`;
  return `${esc(src.publisher)} — ${title}${src.published ? ` (${esc(src.published)})` : ""}${unverified}`;
}

function factValue(f, unit) {
  if (f.value_text) return esc(f.value_text);
  const shownUnit = unit === "ratio" || unit === "fraction" ? "" : unit; // dimensionless: no label
  const mid = `${fmt(f.value)} ${esc(shownUnit ?? "")}`;
  if (f.value_low != null || f.value_high != null) return `${mid} <span class="meta">(${fmt(f.value_low ?? f.value)}–${fmt(f.value_high ?? f.value)})</span>`;
  return mid;
}

function metricHtml(m) {
  if (m.status === "unknown") {
    return `<div class="metric"><div class="metric-head"><span class="metric-label">${esc(m.label)}</span>
      <span class="value unknown">Unknown<span class="badge unknown" title="Either not published, or not yet found in public filings">not yet sourced</span></span></div></div>`;
  }
  // Time series (prices) are summarised by their latest value; the chart shows the rest.
  const facts = m.facts.length > 1 && m.facts[0].period?.includes("-") ? [m.facts[m.facts.length - 1]] : m.facts;
  return facts.map((f) => `<div class="metric">
      <div class="metric-head"><span class="metric-label">${esc(m.label)}</span>
        <span class="value">${factValue(f, m.unit)}<span class="badge ${esc(f.kind)}">${esc(f.kind)}</span></span></div>
      <div class="cite">${f.period ? esc(f.period) + " · " : ""}${sourceLine(f.source)}</div>
      ${f.method ? `<div class="cite">Method: ${esc(f.method)}</div>` : ""}
      ${f.notes ? `<div class="cite">${esc(f.notes)}</div>` : ""}
    </div>`).join("");
}

// ---------- site panel ----------
async function showFacility(id) {
  showTab("site");
  history.replaceState(null, "", `#site=${encodeURIComponent(id)}`);
  const f = await api(`/api/facilities/${id}`);
  const r = await api(`/api/regions/${f.region_id}`);
  const inCompare = compare.has(id);
  $("#tab-site").innerHTML = `
    <h2>${esc(f.name)}</h2>
    <div class="meta">${esc(f.operator)} · ${esc(f.city || "")}${f.city ? ", " : ""}${esc(f.state)} · status: ${esc(f.status)}</div>
    <div class="cite">Location (${esc(f.location_precision)}-level): ${sourceLine(f.location_source)}</div>
    ${f.notes ? `<p class="note">${esc(f.notes)}</p>` : ""}
    <p><button class="btn ${inCompare ? "secondary" : ""}" id="cmp-btn">${inCompare ? "Remove from compare" : "Add to compare"}</button></p>
    <h3>Facility</h3>
    ${Object.values(f.metrics).map(metricHtml).join("")}
    <h3>Region: ${esc(r.name)}</h3>
    <div class="meta">Utilities: ${esc(r.utilities)} · Balancing authority: ${esc(r.balancing_authority)} · eGRID: ${esc(r.egrid_subregion)}</div>
    ${Object.values(r.metrics).map(metricHtml).join("")}
    <div class="chart-wrap"><canvas id="price-chart"></canvas></div>`;
  $("#cmp-btn").onclick = () => {
    inCompare ? compare.delete(id) : compare.size < 4 && compare.add(id);
    $("#compare-count").textContent = compare.size ? `(${compare.size})` : "";
    showFacility(id);
  };
  drawPrices(r);
}

function drawPrices(region) {
  priceChart?.destroy();
  const series = [
    ["retail_price_res_cents_kwh", "Residential"],
    ["retail_price_com_cents_kwh", "Commercial"],
    ["retail_price_ind_cents_kwh", "Industrial"],
  ].map(([k, label]) => ({ label, data: region.metrics[k].facts.map((f) => ({ x: f.period, y: f.value })) }))
   .filter((s) => s.data.length);
  const canvas = $("#price-chart");
  if (!series.length) { canvas.parentElement.remove(); return; }
  const css = getComputedStyle(document.documentElement);
  const colors = [css.getPropertyValue("--accent"), css.getPropertyValue("--estimate"), css.getPropertyValue("--assumption")];
  priceChart = new Chart(canvas, {
    type: "line",
    data: { datasets: series.map((s, i) => ({ ...s, borderColor: colors[i], pointRadius: 0, borderWidth: 1.5 })) },
    options: {
      maintainAspectRatio: false, parsing: true,
      scales: { x: { type: "category", ticks: { maxTicksLimit: 6 } }, y: { title: { display: true, text: "¢/kWh (statewide avg)" } } },
      plugins: { title: { display: true, text: "Retail electricity price, EIA" } },
    },
  });
}

// ---------- compare ----------
async function renderCompare() {
  const el = $("#tab-compare");
  if (!compare.size) { el.innerHTML = `<p class="hint">Use “Add to compare” on a site to line it up here (up to 4).</p>`; return; }
  const sites = await Promise.all([...compare].map((id) => api(`/api/facilities/${id}`)));
  const metrics = Object.keys(sites[0].metrics);
  const cell = (m) => m.status === "unknown"
    ? `<span class="value unknown">Unknown</span>`
    : m.facts.map((f) => `${factValue(f, m.unit)}<span class="badge ${esc(f.kind)}">${esc(f.kind)}</span>`).join("<br>");
  el.innerHTML = `<h2>Compare sites</h2>
    <table class="compare"><tr><th></th>${sites.map((s) => `<th>${esc(s.name)}</th>`).join("")}</tr>
    ${metrics.map((k) => `<tr><th>${esc(sites[0].metrics[k].label)}</th>${sites.map((s) => `<td>${cell(s.metrics[k])}</td>`).join("")}</tr>`).join("")}
    </table><p class="note">Open a site for the source behind each value.</p>`;
}

// ---------- model ----------
$("#model-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = Object.fromEntries(new FormData(e.target));
  const body = { region_id: fd.region_id, it_capacity_mw: +fd.it_capacity_mw, cooling: fd.cooling };
  if (fd.pue) body.pue = +fd.pue;
  if (fd.utilization) body.utilization = +fd.utilization;
  const res = await api("/api/estimate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

  const row = (label, o) => o
    ? `<div class="result-row"><div>${label} <span class="badge estimate">estimate</span></div>
        <div class="central">${fmt(o.central)} ${esc(o.unit)}</div>
        <div class="range">range ${fmt(o.low)} – ${fmt(o.high)}</div></div>`
    : `<div class="result-row"><div>${label}</div><div class="value unknown">Unknown — grid emission rate not sourced for this region</div></div>`;
  const input = (name, f) => f.status === "unknown"
    ? `<div class="metric"><span class="metric-label">${esc(name)}</span> <span class="value unknown">Unknown</span></div>`
    : f.kind === "user_input"
      ? `<div class="metric"><span class="metric-label">${esc(name)}</span> <span class="value">${fmt(f.value)}</span><span class="badge user_input">your input</span></div>`
      : metricHtml({ label: name, unit: f.unit, status: "known", facts: [f] });

  const o = res.outputs;
  $("#model-result").innerHTML = `
    ${row("Average grid demand", o.avg_grid_demand)}
    ${row("Annual electricity", o.annual_energy)}
    ${row("Annual site water", o.annual_site_water)}
    ${row("Annual CO₂ (location-based)", o.annual_co2)}
    <ul class="caveats">${res.caveats.map((c) => `<li>${esc(c)}</li>`).join("")}</ul>
    <h3>Inputs used</h3>
    ${Object.entries(res.inputs).map(([k, f]) => input(k, f)).join("")}`;
});

// ---------- map ----------
async function init() {
  const map = L.map("map").setView([38.5, -96], 4);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  }).addTo(map);

  const [regions, facilities, cov] = await Promise.all([api("/api/regions"), api("/api/facilities"), api("/api/coverage")]);
  $("#coverage").textContent =
    `Coverage: ${cov.facility_metrics_sourced} of ${cov.facility_metrics_total} facility metrics sourced; ` +
    `${cov.sources_verified} of ${cov.sources_total} sources verified. ·`;
  $("#region-select").innerHTML = regions.map((r) => `<option value="${esc(r.id)}">${esc(r.name)}</option>`).join("");

  const markers = facilities.map((f) => {
    const m = L.circleMarker([f.lat, f.lon], {
      radius: 8, weight: 2, fillOpacity: 0.6,
      dashArray: f.location_precision === "site" ? null : "3 3",
    }).addTo(map);
    m.bindTooltip(`${esc(f.name)}<br><small>${f.known_metrics}/${f.total_metrics} metrics sourced · ${esc(f.location_precision)}-level location</small>`);
    m.on("click", () => showFacility(f.id));
    return m;
  });
  // The grid layout can settle after Leaflet first measures the container, so re-measure
  // and re-fit on every resize until the user takes over the view. (No "zoomstart":
  // fitBounds fires it too, which would count our own fit as user input.)
  const bounds = markers.length ? L.featureGroup(markers).getBounds().pad(0.2) : null;
  let userMoved = false;
  map.once("mousedown wheel touchstart keydown", () => (userMoved = true));
  const fit = () => {
    map.invalidateSize();
    if (bounds && !userMoved) map.fitBounds(bounds, { animate: false });
  };
  fit();
  new ResizeObserver(fit).observe($("#map"));

  // Shareable links: /#site=<facility id> opens that site's panel.
  const linked = new URLSearchParams(location.hash.slice(1)).get("site");
  if (linked && facilities.some((f) => f.id === linked)) showFacility(linked);
}
init();
