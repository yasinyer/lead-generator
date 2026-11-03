const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
let META = null;
let activeId = null;

const BAD = new Set(["none", "social", "directory", "offline", "placeholder"]);
const WARN = new Set(["weak", "builder"]);

async function api(path, opts = {}) {
  const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || r.statusText);
  return data;
}

function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => (t.hidden = true), 2200);
}

function fillSelect(sel, entries) {
  for (const [v, label] of entries) sel.insertAdjacentHTML("beforeend", `<option value="${esc(v)}">${esc(label)}</option>`);
}

function filterParams() {
  const p = new URLSearchParams();
  const set = (k, v) => v && v !== "0" && p.set(k, v);
  set("q", $("#f-q").value.trim());
  set("sector", $("#f-sector").value);
  set("city", $("#f-city").value);
  set("web_status", $("#f-web").value);
  set("status", $("#f-status").value);
  set("min_score", $("#f-score").value);
  set("min_reviews", $("#f-reviews").value);
  return p;
}

function scoreClass(s) { return s >= 70 ? "hot" : s >= 50 ? "good" : ""; }
function webChip(ws) {
  const cls = BAD.has(ws) ? "bad" : WARN.has(ws) ? "warn" : ws === "ok" ? "okc" : "";
  return `<span class="chip ${cls}">${esc(META.web_statuses[ws] || ws || "?")}</span>`;
}
function stars(l) {
  if (l.rating == null) return `<span class="meta">geen Google-data</span>`;
  return `<span class="stars">★</span> ${l.rating.toFixed(1)} <span class="meta">(${l.review_count ?? 0})</span>`;
}
function statusSelect(l) {
  return `<select data-status="${l.id}">` + META.statuses.map(([v, lab]) =>
    `<option value="${v}" ${v === l.status ? "selected" : ""}>${esc(lab)}</option>`).join("") + `</select>`;
}

async function loadStats() {
  const s = await api("/api/stats");
  const items = [
    [s.total, "leads"], [s.hot, "toppers (≥ 70)"], [s.no_site, "zonder eigen site"],
    [s.weak, "zwakke site"], [s.contacted, "gecontacteerd"], [s.clients, "klanten"],
  ];
  $("#stats").innerHTML = items.map(([n, l]) => `<div class="stat"><b>${n}</b><span>${l}</span></div>`).join("");
}

async function loadLeads() {
  const p = filterParams();
  $("#exportBtn").href = "/api/export.csv?" + p;
  const leads = await api("/api/leads?" + p);
  const tbody = $("#leads tbody");
  tbody.innerHTML = leads.map((l) => `
    <tr data-id="${l.id}" class="${l.id === activeId ? "active" : ""}">
      <td><span class="score ${scoreClass(l.score)}">${l.score ?? "–"}</span></td>
      <td><div class="name">${esc(l.name)}</div>
          <div class="meta">${esc(META.sectors[l.sector] || l.sector || "")} · ${esc(l.city || "")}</div></td>
      <td>${webChip(l.web_status)}${l.issues.length ? `<div class="meta">${l.issues.length} probleem${l.issues.length > 1 ? "en" : ""}</div>` : ""}</td>
      <td>${stars(l)}</td>
      <td><div>${esc(l.phone || "")}</div><div class="meta">${esc(l.email || "")}</div></td>
      <td onclick="event.stopPropagation()">${statusSelect(l)}</td>
    </tr>`).join("");
  $("#empty").hidden = leads.length > 0 || filterParams().toString() !== "";
}

async function openLead(id) {
  activeId = id;
  document.querySelectorAll("#leads tbody tr").forEach((tr) => tr.classList.toggle("active", +tr.dataset.id === id));
  const l = await api(`/api/leads/${id}`);
  const link = (url, label) => url ? `<a href="${esc(url)}" target="_blank" rel="noopener">${esc(label || url)}</a>` : "–";
  const mapsUrl = l.maps_url || `https://www.google.com/maps/search/${encodeURIComponent(l.name + " " + (l.city || ""))}`;
  $("#drawerBody").innerHTML = `
    <h2>${esc(l.name)}</h2>
    <div class="row">
      <span class="score ${scoreClass(l.score)}">${l.score}</span> ${webChip(l.web_status)}
      <span class="chip">${esc(META.sectors[l.sector] || l.sector)}</span>
    </div>
    <section>
      <dl class="kv">
        <dt>Adres</dt><dd>${esc(l.address || l.city || "–")}</dd>
        <dt>Telefoon</dt><dd>${l.phone ? `<a href="tel:${esc(l.phone)}">${esc(l.phone)}</a>` : "–"}</dd>
        <dt>E-mail</dt><dd>${l.email ? `<a href="mailto:${esc(l.email)}">${esc(l.email)}</a>` : "–"}</dd>
        <dt>Website</dt><dd>${link(l.website)}</dd>
        <dt>Facebook</dt><dd>${link(l.facebook)}</dd>
        <dt>Google</dt><dd>${stars(l)} · ${link(mapsUrl, "Open in Maps")}</dd>
        ${l.pagespeed != null ? `<dt>PageSpeed</dt><dd>${l.pagespeed}/100 (mobiel)</dd>` : ""}
        <dt>Bron</dt><dd>${esc(l.sources || "")}</dd>
      </dl>
    </section>
    ${l.issues.length ? `<section><h3>Wat er mis is</h3><ul class="issues">${l.issues.map((i) => `<li>${esc(i.text)}</li>`).join("")}</ul></section>` : ""}
    ${l.screenshot ? `<section><h3>Huidige site op gsm</h3><a href="/screenshots/${esc(l.screenshot)}" target="_blank"><img class="shot" src="/screenshots/${esc(l.screenshot)}" alt="Screenshot op gsm"></a></section>` : ""}
    <section>
      <h3>Opvolging</h3>
      <div class="row">${statusSelect(l)}<span class="hint" id="saved"></span></div>
      <textarea id="notes" placeholder="Notities: gebeld op…, terugbellen…, interesse in…">${esc(l.notes || "")}</textarea>
    </section>
    <section>
      <h3>Pitch (e-mail / bericht)</h3>
      ${META.designer_set ? "" : `<p class="hint">Tip: zet DESIGNER_NAME, DESIGNER_PHONE… in .env om je gegevens automatisch in te vullen.</p>`}
      <div class="row"><b>Onderwerp:</b> <span id="subject">${esc(l.pitch.subject)}</span></div>
      <textarea class="pitch" id="pitchBody">${esc(l.pitch.body)}</textarea>
      <div class="row">
        <button class="btn small" data-copy="pitchBody">Kopieer bericht</button>
        ${l.email ? `<a class="btn small" href="mailto:${esc(l.email)}?subject=${encodeURIComponent(l.pitch.subject)}&body=${encodeURIComponent(l.pitch.body)}">Open in mail</a>` : ""}
      </div>
    </section>
    <section>
      <h3>Belscript</h3>
      <textarea id="callScript">${esc(l.pitch.call)}</textarea>
      <button class="btn small" data-copy="callScript">Kopieer</button>
    </section>`;
  $("#drawer").hidden = false;

  let t;
  $("#notes").addEventListener("input", (e) => {
    clearTimeout(t);
    $("#saved").textContent = "…";
    t = setTimeout(async () => {
      await api(`/api/leads/${id}`, { method: "PATCH", body: JSON.stringify({ notes: e.target.value }) });
      $("#saved").textContent = "opgeslagen ✓";
    }, 600);
  });
}

document.addEventListener("change", async (e) => {
  const id = e.target.dataset?.status;
  if (!id) return;
  await api(`/api/leads/${id}`, { method: "PATCH", body: JSON.stringify({ status: e.target.value }) });
  toast("Status bijgewerkt");
  loadStats();
  document.querySelectorAll(`select[data-status="${id}"]`).forEach((s) => (s.value = e.target.value));
});

document.addEventListener("click", async (e) => {
  const copy = e.target.dataset?.copy;
  if (copy) {
    await navigator.clipboard.writeText($("#" + copy).value);
    toast("Gekopieerd");
  }
});

$("#leads tbody").addEventListener("click", (e) => {
  const tr = e.target.closest("tr[data-id]");
  if (tr) openLead(+tr.dataset.id);
});
$("#drawerClose").onclick = () => { $("#drawer").hidden = true; activeId = null; loadLeads(); };
document.addEventListener("keydown", (e) => e.key === "Escape" && ($("#drawer").hidden = true));

let ft;
for (const id of ["f-q", "f-sector", "f-city", "f-web", "f-status", "f-score", "f-reviews"]) {
  $("#" + id).addEventListener("input", () => { clearTimeout(ft); ft = setTimeout(loadLeads, 250); });
}

/* ---------- scan ---------- */
function chip(name, value, label, checked = false) {
  return `<label><input type="checkbox" name="${name}" value="${esc(value)}" ${checked ? "checked" : ""}>${esc(label)}</label>`;
}

function setupScanDialog() {
  $("#scanSectors").innerHTML = Object.entries(META.sectors).map(([k, v]) => chip("sector", k, v)).join("");
  $("#scanCities").innerHTML = META.cities.map((c) => chip("city", c, c, c === "Hasselt")).join("");
  $("#o-radius").value = META.default_radius;
  $("#o-calls").value = META.places_max_calls;
  const warn = [];
  for (const id of ["o-places", "o-enrich", "o-pagespeed", "o-browser"]) {
    $("#" + id).disabled = false;
    $("#" + id).checked = true;
  }
  if (!META.has_google_key) {
    warn.push("Geen GOOGLE_API_KEY ingesteld: alleen OpenStreetMap, dus geen reviews of ratings.");
    $("#o-places").checked = $("#o-enrich").checked = false;
    $("#o-places").disabled = $("#o-enrich").disabled = true;
  }
  if (!META.has_pagespeed_key) { $("#o-pagespeed").checked = false; $("#o-pagespeed").disabled = true; }
  if (!META.has_playwright) {
    warn.push("Playwright is niet geïnstalleerd: geen gsm-check en screenshots.");
    $("#o-browser").checked = false; $("#o-browser").disabled = true;
  } else if (META.browser === "installing") {
    warn.push("De browser voor de gsm-check wordt nog gedownload (eenmalig). Scan je nu, dan gebeurt dat zonder gsm-check.");
  } else if (META.browser === "missing") {
    warn.push("Geen browser voor de gsm-check gevonden. Installeer Google Chrome om gsm-checks en screenshots te krijgen.");
  }
  $("#keyWarning").innerHTML = warn.map(esc).join("<br>");
  $("#keyWarning").hidden = !warn.length;
  $("#scanProvince").onchange = (e) => ($("#scanCities").style.opacity = e.target.checked ? 0.4 : 1);
}

$("#scanBtn").onclick = () => $("#scanDialog").showModal();

$("#scanStart").onclick = async () => {
  const checked = (n) => [...document.querySelectorAll(`input[name=${n}]:checked`)].map((i) => i.value);
  const body = {
    sectors: checked("sector"),
    cities: $("#scanProvince").checked ? [] : checked("city"),
    province: $("#scanProvince").checked,
    osm: $("#o-osm").checked, places: $("#o-places").checked, enrich: $("#o-enrich").checked,
    browser: $("#o-browser").checked, pagespeed: $("#o-pagespeed").checked,
    radius: +$("#o-radius").value, max_places_calls: +$("#o-calls").value,
  };
  try {
    await api("/api/scan", { method: "POST", body: JSON.stringify(body) });
  } catch (err) { toast(err.message); return; }
  $("#scanStart").disabled = true;
  const log = $("#scanLog");
  log.hidden = false;
  log.textContent = "";
  let since = 0;
  const poll = async () => {
    const s = await api("/api/scan/status?since=" + since);
    since = s.next;
    if (s.log.length) { log.textContent += s.log.join("\n") + "\n"; log.scrollTop = log.scrollHeight; }
    if (s.running) return setTimeout(poll, 1200);
    $("#scanStart").disabled = false;
    if (s.error) toast("Scan mislukt: " + s.error);
    else toast("Scan klaar");
    loadStats(); loadLeads();
  };
  poll();
};

/* ---------- instellingen ---------- */
async function openSettings() {
  const s = await api("/api/settings");
  const form = $("#settingsForm");
  for (const el of form.querySelectorAll("input[name]")) {
    if (el.name === "GOOGLE_API_KEY") continue;
    el.value = s[el.name] ?? "";
  }
  const k = s.GOOGLE_API_KEY;
  $("#keyInput").value = "";
  $("#keyInput").placeholder = k.set ? `Ingesteld (${k.hint}). Laat leeg om te behouden.` : "Plak hier je key (begint meestal met AIza…)";
  $("#keyHint").innerHTML = k.set ? `<a href="#" id="removeKey">Key verwijderen</a>` : "Zonder key zoekt de tool alleen via OpenStreetMap: geen reviews of ratings.";
  $("#settingsDialog").showModal();
}

async function saveSettings(extra = {}) {
  const body = { ...extra };
  for (const el of $("#settingsForm").querySelectorAll("input[name]")) body[el.name] = el.value.trim();
  try {
    await api("/api/settings", { method: "POST", body: JSON.stringify(body) });
  } catch (err) { toast(err.message); return; }
  $("#settingsDialog").close();
  toast("Instellingen bewaard");
  META = await api("/api/meta");
  setupScanDialog();
  $("#welcome").hidden = META.designer_set;
  if (activeId) openLead(activeId);
}

$("#settingsBtn").onclick = openSettings;
$("#welcomeBtn").onclick = openSettings;
$("#settingsSave").onclick = () => saveSettings();
$("#keyHint").addEventListener("click", (e) => {
  if (e.target.id === "removeKey") { e.preventDefault(); saveSettings({ remove_key: true }); }
});

/* ---------- app-levenscyclus ---------- */
let lastBrowser = null;
async function ping() {
  try {
    const r = await api("/api/ping", { method: "POST", body: "{}" });
    if (lastBrowser === "installing" && r.browser === "ready") toast("Browser voor de gsm-check is klaar");
    if (r.browser !== lastBrowser && META) {
      META.browser = r.browser;
      if (!r.scan_running && !$("#scanDialog").open) setupScanDialog();
    }
    lastBrowser = r.browser;
  } catch { /* server gestopt */ }
}
setInterval(ping, 30000);

$("#quitBtn").onclick = async () => {
  if (!confirm("Lead Generator afsluiten? Je leads blijven bewaard.")) return;
  await api("/api/shutdown", { method: "POST", body: "{}" }).catch(() => {});
  document.body.innerHTML = `<div class="empty"><h2>Lead Generator is gestopt</h2>
    <p>Je kunt dit tabblad sluiten. Open de app opnieuw om verder te werken.</p></div>`;
};

(async function init() {
  META = await api("/api/meta");
  $("#welcome").hidden = META.designer_set;
  fillSelect($("#f-sector"), Object.entries(META.sectors));
  fillSelect($("#f-city"), META.cities.map((c) => [c, c]));
  fillSelect($("#f-web"), Object.entries(META.web_statuses));
  fillSelect($("#f-status"), META.statuses);
  setupScanDialog();
  lastBrowser = META.browser;
  ping();
  await Promise.all([loadStats(), loadLeads()]);
})();
