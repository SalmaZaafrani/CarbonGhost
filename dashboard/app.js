/* CarbonGhost Sentinel — interface de supervision (application monopage, sans framework). */
"use strict";

// ═════════════════════════════ Configuration ═════════════════════════════

const HOST = window.location.hostname || "localhost";
const API = {
  user: `http://${HOST}:8001`,
  carbone: `http://${HOST}:8002`,
  mesures: `http://${HOST}:8003`,
  ia: `http://${HOST}:8004`,
  assistant: `http://${HOST}:8005`,
  factory: `http://${HOST}:8006`,
};
const REFRESH_MS = 5000;

const ROLE_LABELS = {
  OPERATOR: "Opérateur",
  LINE_MANAGER: "Chef de ligne",
  ENERGY_RSE_MANAGER: "Responsable énergie / RSE",
  SUPER_ADMIN: "Administrateur",
};
const DEMO_ACCOUNTS = [
  ["operateur@carbonghost.com", "Opérateur", "Vue usine, alarmes, assistant"],
  ["chef.ligne@carbonghost.com", "Chef de ligne", "Suivi de ligne et énergie"],
  ["energie@carbonghost.com", "Responsable énergie", "CO₂, objectifs, rapports"],
  ["admin.demo@carbonghost.com", "Administrateur", "Tous les écrans et la gestion"],
];
const CAUSES = {
  aucune: "Aucune",
  fonctionnement_a_vide: "Marche à vide",
  usure_mecanique: "Usure mécanique",
  surchauffe: "Surchauffe",
  fuite_pneumatique: "Fuite pneumatique",
  reglage_non_optimal: "Réglage non optimal",
  unknown: "Inconnue",
};
const SENSORS = { courant: "courant", temperature: "température", vibration: "vibration", pression: "pression" };
const SEVERITY = { critical: "Critique", high: "Haute", medium: "Moyenne" };
const SEVERITY_RANK = { critical: 3, high: 2, medium: 1 };

// Écrans : titre, permission(s) requise(s), fonction d'affichage
const VIEWS = {
  usine:     { title: "Vue usine",        nav: "Vue usine",        perms: ["machines:read"] },
  machine:   { title: "Machine",          nav: null,               perms: ["machines:read"] },
  alarmes:   { title: "Alarmes",          nav: "Alarmes",          perms: ["machines:read"] },
  energie:   { title: "Énergie et CO₂",   nav: "Énergie et CO₂",   perms: ["carbon:read"] },
  rapports:  { title: "Rapports",         nav: "Rapports",         perms: ["reports:export"] },
  assistant: { title: "Assistant",        nav: "Assistant",        perms: ["llm:use"] },
  admin:     { title: "Administration",   nav: "Administration",   perms: ["machines_config:manage", "users:manage"] },
};

// ═════════════════════════════ État ═════════════════════════════

const state = {
  token: null,
  user: null,           // {username, email, role, permissions}
  machines: [],         // service-factory
  knownAlarmIds: null,  // pour notifier les nouvelles alarmes
  activeAlarms: [],
  stats: null,
  charts: {},           // graphiques Chart.js de l'écran courant
  timer: null,
  chat: [],             // conversation avec l'assistant (session)
};

// ═════════════════════════════ Outils ═════════════════════════════

const $ = (sel, root = document) => root.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = (n, d = 2) => (n === null || n === undefined || Number.isNaN(n) ? "–" : Number(n).toLocaleString("fr-FR", { minimumFractionDigits: d, maximumFractionDigits: d }));
const time = (ts) => new Date(ts).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
const dateTime = (ts) => new Date(ts).toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
const can = (...perms) => perms.some((p) => state.user?.permissions?.includes(p));
const machineName = (id) => state.machines.find((m) => m.id === id)?.name || "";
const prioIcon = (sev, label = true) =>
  `<span class="prio prio-${sev || "none"}" role="img" aria-label="${esc(SEVERITY[sev] || "Normal")}"></span>${label ? ` ${esc(SEVERITY[sev] || "Normal")}` : ""}`;

const store = {
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch { /* stockage indisponible */ } },
  del(k) { try { localStorage.removeItem(k); } catch { /* idem */ } },
};

class ApiError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}

async function api(service, path, { method = "GET", body, raw = false } = {}) {
  const headers = {};
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";
  let res;
  try {
    res = await fetch(API[service] + path, { method, headers, body: body !== undefined ? JSON.stringify(body) : undefined });
  } catch {
    setConnection(false);
    throw new ApiError(0, `Le service ${service} ne répond pas.`);
  }
  setConnection(true);
  if (res.status === 401 && service !== "user") {
    logout("Votre session a expiré. Reconnectez-vous.");
    throw new ApiError(401, "Session expirée");
  }
  if (!res.ok) {
    let detail = `Erreur ${res.status}`;
    try { const d = await res.json(); detail = typeof d.detail === "string" ? d.detail : detail; } catch { /* corps non JSON */ }
    throw new ApiError(res.status, detail);
  }
  if (raw) return res;
  return res.status === 204 ? null : res.json();
}

function setConnection(ok) {
  $("#conn").classList.toggle("down", !ok);
  $("#conn-text").textContent = ok ? "Connecté" : "Service injoignable";
}

function toast(message, kind = "", title = "") {
  const el = document.createElement("div");
  el.className = `toast ${kind}`;
  const icon = kind === "critical" || kind === "high" ? prioIcon(kind, false) : "";
  el.innerHTML = `${icon}<div>${title ? `<strong>${esc(title)}</strong><br>` : ""}${esc(message)}</div>`;
  $("#toasts").appendChild(el);
  setTimeout(() => el.remove(), kind === "critical" ? 12000 : 6000);
}

function destroyCharts() {
  Object.values(state.charts).forEach((c) => c.destroy());
  state.charts = {};
}

const CHART_BASE = {
  responsive: true,
  maintainAspectRatio: false,
  animation: false,
  interaction: { mode: "index", intersect: false },
  plugins: { legend: { labels: { color: "#5b6870", boxWidth: 14, font: { family: "IBM Plex Sans" } } } },
  scales: {
    x: { ticks: { color: "#5b6870", maxTicksLimit: 6, font: { family: "IBM Plex Sans" } }, grid: { color: "#ccd2d6" } },
    y: { ticks: { color: "#5b6870", font: { family: "IBM Plex Sans" } }, grid: { color: "#ccd2d6" } },
  },
};

function lineChart(canvas, labels, datasets, extra = {}) {
  if (!window.Chart) return null;
  return new Chart(canvas, { type: "line", data: { labels, datasets }, options: { ...CHART_BASE, ...extra } });
}

// ═════════════════════════════ Connexion ═════════════════════════════

function decodeToken(token) {
  try {
    const payload = JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
    if (payload.exp * 1000 < Date.now()) return null;
    return payload;
  } catch { return null; }
}

function showLogin(message = "") {
  $("#app").classList.add("hidden");
  $("#login").classList.remove("hidden");
  $("#login-error").textContent = message;
  $("#demo-accounts").innerHTML = DEMO_ACCOUNTS.map(([email, label, scope]) =>
    `<li><button type="button" data-email="${email}"><strong>${label}</strong><span>${scope}</span><span class="demo-email">${email}</span></button></li>`).join("");
  $("#login-email").focus();
}

$("#demo-accounts").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-email]");
  if (!btn) return;
  $("#login-email").value = btn.dataset.email;
  $("#login-password").value = "demo1234";
  $("#login-form").requestSubmit();
});

$("#pw-toggle").addEventListener("click", (e) => {
  const input = $("#login-password");
  const show = input.type === "password";
  input.type = show ? "text" : "password";
  e.currentTarget.textContent = show ? "Masquer" : "Afficher";
  e.currentTarget.setAttribute("aria-pressed", String(show));
});

$("#login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = $("#login-btn");
  if (!$("#login-email").value.trim() || !$("#login-password").value) {
    $("#login-error").textContent = "Saisissez votre adresse email et votre mot de passe.";
    return;
  }
  btn.disabled = true;
  btn.textContent = "Connexion…";
  $("#login-error").textContent = "";
  try {
    const data = await api("user", "/user/login", {
      method: "POST",
      body: { email: $("#login-email").value.trim(), password: $("#login-password").value },
    });
    startSession(data.access_token);
  } catch (err) {
    $("#login-error").textContent = err.status === 401 ? "Email ou mot de passe incorrect." : err.message;
  } finally {
    btn.disabled = false;
    btn.textContent = "Se connecter";
  }
});

function startSession(token) {
  const payload = decodeToken(token);
  if (!payload) return showLogin();
  state.token = token;
  state.user = payload;
  store.set("cg_token", token);
  state.knownAlarmIds = null;
  $("#login").classList.add("hidden");
  $("#app").classList.remove("hidden");
  $("#user-name").textContent = payload.username || payload.email;
  $("#user-role").textContent = ROLE_LABELS[payload.role] || payload.role;
  buildNav();
  loadMachines().then(route);
}

function logout(message = "") {
  clearInterval(state.timer);
  destroyCharts();
  state.token = null;
  state.user = null;
  state.chat = [];
  store.del("cg_token");
  showLogin(message);
}
$("#logout").addEventListener("click", () => logout());

// ═════════════════════════════ Navigation ═════════════════════════════

function allowedViews() {
  return Object.entries(VIEWS).filter(([, v]) => can(...v.perms)).map(([k]) => k);
}

function buildNav() {
  const allowed = allowedViews();
  $("#nav").innerHTML = allowed
    .filter((k) => VIEWS[k].nav)
    .map((k) => `<a href="#/${k}" data-view="${k}">${VIEWS[k].nav}${k === "alarmes" ? '<span class="rail-badge hidden" id="nav-alarm-badge"></span>' : ""}</a>`)
    .join("");
}

function route() {
  if (!state.user) return;
  const [name, param] = (location.hash.replace(/^#\//, "") || "").split("/");
  const allowed = allowedViews();
  const view = allowed.includes(name) ? name : allowed[0];
  if (!view) {
    $("#view").innerHTML = `<div class="panel empty">Votre rôle ne donne accès à aucun écran. Contactez un administrateur.</div>`;
    return;
  }
  if (view !== name) { location.hash = `#/${view}`; return; }

  document.querySelectorAll("#nav a").forEach((a) => a.classList.toggle("active", a.dataset.view === (view === "machine" ? "usine" : view)));
  $("#view-title").textContent = view === "machine" ? `${decodeURIComponent(param || "")}, ${machineName(decodeURIComponent(param || ""))}` : VIEWS[view].title;

  clearInterval(state.timer);
  destroyCharts();
  // Nouveau conteneur à chaque écran : les écouteurs de l'écran précédent disparaissent avec l'ancien
  const old = $("#view");
  const fresh = old.cloneNode(false);
  old.replaceWith(fresh);
  const render = RENDERERS[view];
  render.init(decodeURIComponent(param || ""));
  const tick = async () => {
    await Promise.allSettled([refreshAlarmSummary(), render.refresh?.(decodeURIComponent(param || ""))]);
  };
  tick();
  state.timer = setInterval(tick, REFRESH_MS);
}
window.addEventListener("hashchange", route);

async function loadMachines() {
  try { state.machines = await api("factory", "/factory/machines"); } catch { state.machines = []; }
}

// ═════════════════════════════ Alarmes (barre du haut + notifications) ═════════════════════════════

async function refreshAlarmSummary() {
  if (!can("machines:read")) return;
  const [stats, active] = await Promise.all([
    api("ia", "/ia/alarms/stats"),
    api("ia", "/ia/alarms?status=active&limit=200"),
  ]);
  state.stats = stats;
  state.activeAlarms = active;

  const a = stats.active;
  $("#alarm-summary").innerHTML = ["critical", "high", "medium"].map((s) =>
    `<a href="#/alarmes" title="Alarmes ${SEVERITY[s].toLowerCase()}s actives">${prioIcon(s, false)}<span>${a[s] || 0}</span></a>`).join("");
  const badge = $("#nav-alarm-badge");
  if (badge) {
    badge.textContent = stats.active_total;
    badge.classList.toggle("hidden", !stats.active_total);
  }
  document.title = stats.active_total ? `(${stats.active_total}) CarbonGhost Sentinel` : "CarbonGhost Sentinel, supervision";

  // Notification des nouvelles alarmes critiques ou hautes
  const ids = new Set(active.map((x) => x.id));
  if (state.knownAlarmIds) {
    active
      .filter((x) => !state.knownAlarmIds.has(x.id) && (x.severity === "critical" || x.severity === "high"))
      .slice(0, 3)
      .forEach((x) => toast(`${x.machine_id} ${machineName(x.machine_id)} : ${x.features.map((f) => SENSORS[f] || f).join(", ")} hors norme`,
        x.severity, `Nouvelle alarme ${SEVERITY[x.severity].toLowerCase()}`));
  }
  state.knownAlarmIds = ids;
}

function worstSeverity(alarms) {
  return alarms.reduce((w, a) => (SEVERITY_RANK[a.severity] > (SEVERITY_RANK[w] || 0) ? a.severity : w), null);
}

async function acknowledge(alarmId, comment) {
  await api("ia", `/ia/alarms/${alarmId}/acknowledge`, { method: "POST", body: { comment } });
  toast("Alarme acquittée.", "success");
}

function alarmRows(alarms, { showMachine = true } = {}) {
  if (!alarms.length) return `<tr><td colspan="7" class="empty">Aucune alarme.</td></tr>`;
  const canAck = can("alarms:ack");
  return alarms.map((a) => `
    <tr class="${a.status === "acknowledged" ? "acked" : ""}">
      <td>${prioIcon(a.severity)}</td>
      ${showMachine ? `<td><a href="#/machine/${encodeURIComponent(a.machine_id)}"><b>${esc(a.machine_id)}</b></a> <span class="muted">${esc(machineName(a.machine_id))}</span></td>` : ""}
      <td>${a.features.map((f) => esc(SENSORS[f] || f)).join(", ")}</td>
      <td class="num">${time(a.timestamp)}${a.occurrences > 1 ? `<br><span class="muted">dernière ${time(a.last_seen_at)}</span>` : ""}</td>
      <td class="num">${a.occurrences}</td>
      <td>${a.status === "acknowledged"
        ? `Acquittée par ${esc(a.acknowledged_by)}<br><span class="muted">${dateTime(a.acknowledged_at)}${a.ack_comment ? `<br>« ${esc(a.ack_comment)} »` : ""}</span>`
        : canAck
          ? `<form class="inline ack-form" data-id="${a.id}"><input type="text" name="comment" placeholder="Commentaire (facultatif)" aria-label="Commentaire"><button class="btn btn-small btn-primary" type="submit">Acquitter</button></form>`
          : `<span class="muted">Active</span>`}</td>
    </tr>`).join("");
}

function bindAckForms(root, onDone) {
  root.addEventListener("submit", async (e) => {
    const form = e.target.closest(".ack-form");
    if (!form) return;
    e.preventDefault();
    form.querySelector("button").disabled = true;
    try {
      await acknowledge(form.dataset.id, form.comment.value);
      await refreshAlarmSummary();
      onDone();
    } catch (err) {
      toast(err.message, "error");
      form.querySelector("button").disabled = false;
    }
  });
}

// ═════════════════════════════ Écrans ═════════════════════════════

const RENDERERS = {};

// ───────────── Vue usine (synoptique) ─────────────
RENDERERS.usine = {
  init() {
    const lines = {};
    state.machines.forEach((m) => (lines[m.production_line] ||= []).push(m));
    const lanes = Object.entries(lines).sort(([a], [b]) => a.localeCompare(b));
    $("#view").innerHTML = `
      <div class="grid grid-4" id="usine-kpis"></div>
      <section class="panel">
        <div class="panel-head"><h2>Lignes de production</h2><span class="muted">Gris : fonctionnement normal. Couleur : action requise.</span></div>
        ${lanes.length ? lanes.map(([line, ms]) => `
          <div class="line-lane">
            <div class="lane-head"><h3>${esc(line)}</h3><span class="muted">${ms.length} machine${ms.length > 1 ? "s" : ""}</span></div>
            <div class="lane-track">
              ${ms.map((m) => `
                <button class="equip" type="button" data-machine="${esc(m.id)}" id="equip-${esc(m.id)}">
                  <div class="equip-head"><span class="equip-id">${esc(m.id)}</span><span class="equip-state">${prioIcon(null, false)}</span></div>
                  <div class="equip-name">${esc(m.name)}${m.status !== "active" ? `, ${m.status === "maintenance" ? "en maintenance" : "à l'arrêt"}` : ""}</div>
                  <div class="equip-values"><div><b class="v-courant">–</b><small>A</small></div><div><b class="v-temperature">–</b><small>°C</small></div><div><b class="v-vibration">–</b><small>mm/s</small></div></div>
                  <canvas aria-label="Énergie réelle et attendue, dernières mesures"></canvas>
                  <div class="equip-status"></div>
                </button>`).join("")}
            </div>
          </div>`).join("") : `<div class="empty">Aucune machine déclarée. Un administrateur peut en ajouter dans Administration.</div>`}
      </section>`;
    $("#view").addEventListener("click", (e) => {
      const tile = e.target.closest(".equip");
      if (tile) location.hash = `#/machine/${encodeURIComponent(tile.dataset.machine)}`;
    });
    state.machines.forEach((m) => {
      const canvas = $(`#equip-${CSS.escape(m.id)} canvas`);
      state.charts[m.id] = lineChart(canvas, [], [
        { data: [], borderColor: "#1c262c", borderWidth: 1.5, pointRadius: 0, tension: 0.3 },
        { data: [], borderColor: "#7d8a92", borderWidth: 1, borderDash: [3, 3], pointRadius: 0 },
      ], { plugins: { legend: { display: false }, tooltip: { enabled: false } }, scales: { x: { display: false }, y: { display: false, beginAtZero: true } } });
    });
  },

  async refresh() {
    const [latest, summary] = await Promise.all([
      api("mesures", "/mesures/latest"),
      api("carbone", "/carbone/summary?hours=24"),
    ]);
    const events = await Promise.all(state.machines.map((m) =>
      api("carbone", `/carbone/machines/${encodeURIComponent(m.id)}/events?limit=40`).catch(() => [])));

    // Indicateurs
    const sum = (k) => summary.reduce((t, s) => t + (s[k] || 0), 0);
    const active = state.stats?.active_total ?? 0;
    $("#usine-kpis").innerHTML = `
      <div class="kpi"><div class="label">Machines en alarme</div><div class="value">${Object.keys(state.stats?.active_by_machine || {}).length}<small>/ ${state.machines.length}</small></div><div class="sub">${active} alarme${active > 1 ? "s" : ""} active${active > 1 ? "s" : ""}</div></div>
      <div class="kpi"><div class="label">Énergie consommée, 24 h</div><div class="value">${fmt(sum("actual_kwh"), 1)}<small>kWh</small></div><div class="sub">attendue : ${fmt(sum("expected_kwh"), 1)} kWh</div></div>
      <div class="kpi"><div class="label">Énergie gaspillée, 24 h</div><div class="value">${fmt(sum("wasted_kwh"), 2)}<small>kWh</small></div><div class="sub">${fmt(sum("actual_kwh") ? (sum("wasted_kwh") / sum("actual_kwh")) * 100 : 0, 1)} % de la consommation</div></div>
      <div class="kpi"><div class="label">CO₂ évitable, 24 h</div><div class="value">${fmt(sum("avoidable_co2_kg"), 2)}<small>kg</small></div><div class="sub">${sum("waste_events")} gaspillages détectés</div></div>`;

    state.machines.forEach((m, i) => {
      const tile = $(`#equip-${CSS.escape(m.id)}`);
      if (!tile) return;
      const meas = latest.find((x) => x.machine_id === m.id);
      if (meas) {
        tile.querySelector(".v-courant").textContent = fmt(meas.courant, 1);
        tile.querySelector(".v-temperature").textContent = fmt(meas.temperature, 1);
        tile.querySelector(".v-vibration").textContent = fmt(meas.vibration, 2);
      }
      const alarms = state.activeAlarms.filter((a) => a.machine_id === m.id);
      const worst = worstSeverity(alarms);
      tile.className = `equip${worst ? ` state-${worst}` : ""}`;
      tile.querySelector(".equip-state").innerHTML = prioIcon(worst, false);

      const ev = events[i];
      const status = tile.querySelector(".equip-status");
      const parts = [];
      if (alarms.length) parts.push(`${alarms.length} alarme${alarms.length > 1 ? "s" : ""}`);
      const waste = ev.filter((e) => e.status === "waste_detected");
      if (waste.length) {
        const counts = {};
        waste.forEach((e) => { counts[e.probable_cause] = (counts[e.probable_cause] || 0) + 1; });
        const main = Object.entries(counts).sort((a, b) => b[1] - a[1])[0][0];
        parts.push(`<span class="waste-flag" title="Gaspillage sur ${waste.length} des ${ev.length} dernières mesures">${esc(CAUSES[main] || main)} ${waste.length}/${ev.length}</span>`);
      }
      status.innerHTML = parts.length ? parts.join(" ") : `<span class="muted">${meas ? "Normal" : "Pas de mesure reçue"}</span>`;

      const chart = state.charts[m.id];
      if (chart) {
        const series = [...ev].reverse();
        chart.data.labels = series.map((e) => time(e.timestamp));
        chart.data.datasets[0].data = series.map((e) => e.actual_energy_kwh);
        chart.data.datasets[1].data = series.map((e) => e.expected_energy_kwh);
        chart.update();
      }
    });
  },
};

// ───────────── Fiche machine ─────────────
RENDERERS.machine = {
  init(id) {
    const m = state.machines.find((x) => x.id === id);
    $("#view").innerHTML = `
      <section class="panel machine-head">
        <span class="equip-state" id="m-state">${prioIcon(null, false)}</span>
        <div><h2>${esc(id)}, ${esc(m?.name || "Machine inconnue")}</h2>
        <div class="meta">${esc(m?.production_line || "")}${m?.location ? `, ${esc(m.location)}` : ""}${m ? `, puissance nominale ${fmt(m.nominal_power_kw, 1)} kW` : ""}</div></div>
        <span style="flex:1"></span>
        <a class="btn" href="#/usine">Retour à la vue usine</a>
        ${can("llm:use") ? `<a class="btn btn-primary" href="#/assistant/${encodeURIComponent(id)}">Interroger l'assistant</a>` : ""}
      </section>
      <div class="grid grid-4" id="m-kpis"></div>
      <section class="panel">
        <div class="panel-head"><h2>Tendances</h2><span class="muted">120 dernières mesures</span></div>
        <div class="trend-grid">
          <div><h3>Énergie par mesure (kWh)</h3><div class="trend"><canvas id="t-energy"></canvas></div></div>
          <div><h3>Courant (A)</h3><div class="trend"><canvas id="t-courant"></canvas></div></div>
          <div><h3>Température (°C)</h3><div class="trend"><canvas id="t-temperature"></canvas></div></div>
          <div><h3>Vibration (mm/s)</h3><div class="trend"><canvas id="t-vibration"></canvas></div></div>
        </div>
      </section>
      <div class="grid grid-2">
        <section class="panel"><div class="panel-head"><h2>Alarmes de la machine</h2></div>
          <div class="table-scroll"><table><thead><tr><th>Priorité</th><th>Capteurs</th><th>Début</th><th>Occ.</th><th>État</th></tr></thead><tbody id="m-alarms"></tbody></table></div></section>
        <section class="panel"><div class="panel-head"><h2>Gaspillages et recommandations</h2></div>
          <div class="table-scroll"><table><thead><tr><th>Cause</th><th>Mesures</th><th>Dernière</th><th>Recommandation</th></tr></thead><tbody id="m-waste"></tbody></table></div></section>
      </div>`;
    bindAckForms($("#m-alarms"), () => this.refresh(id));

    const single = (canvasId, color) => lineChart($(canvasId), [], [{ data: [], borderColor: color, borderWidth: 1.5, pointRadius: 0, tension: 0.25 }],
      { plugins: { legend: { display: false } } });
    state.charts.energy = lineChart($("#t-energy"), [], [
      { label: "Réelle", data: [], borderColor: "#1c262c", borderWidth: 1.5, pointRadius: 0, tension: 0.25 },
      { label: "Attendue", data: [], borderColor: "#7d8a92", borderDash: [4, 3], borderWidth: 1.2, pointRadius: 0 },
    ], { scales: { ...CHART_BASE.scales, y: { ...CHART_BASE.scales.y, beginAtZero: true } } });
    state.charts.courant = single("#t-courant", "#1f5e73");
    state.charts.temperature = single("#t-temperature", "#1f5e73");
    state.charts.vibration = single("#t-vibration", "#1f5e73");
  },

  async refresh(id) {
    const q = encodeURIComponent(id);
    const [meas, events, alarms] = await Promise.all([
      api("mesures", `/mesures/machines/${q}?limit=120`),
      api("carbone", `/carbone/machines/${q}/events?limit=120`),
      api("ia", `/ia/alarms?machine_id=${q}&limit=50`),
    ]);
    const m = [...meas].reverse();
    const e = [...events].reverse();
    const labels = m.map((x) => time(x.timestamp));
    ["courant", "temperature", "vibration"].forEach((k) => {
      const c = state.charts[k];
      if (!c) return;
      c.data.labels = labels;
      c.data.datasets[0].data = m.map((x) => x[k]);
      c.update();
    });
    if (state.charts.energy) {
      state.charts.energy.data.labels = e.map((x) => time(x.timestamp));
      state.charts.energy.data.datasets[0].data = e.map((x) => x.actual_energy_kwh);
      state.charts.energy.data.datasets[1].data = e.map((x) => x.expected_energy_kwh);
      state.charts.energy.update();
    }

    const active = alarms.filter((a) => a.status === "active");
    $("#m-state").innerHTML = prioIcon(worstSeverity(active), false);
    const waste = events.filter((x) => x.status === "waste_detected");
    const co2 = events.reduce((t, x) => t + x.avoidable_co2_kg, 0);
    const lastM = meas[0];
    $("#m-kpis").innerHTML = `
      <div class="kpi"><div class="label">Dernière mesure</div><div class="value">${lastM ? time(lastM.timestamp) : "–"}</div><div class="sub">${lastM ? `${lastM.production_count} pièce${lastM.production_count > 1 ? "s" : ""} produite${lastM.production_count > 1 ? "s" : ""}` : "aucune mesure"}</div></div>
      <div class="kpi"><div class="label">Alarmes actives</div><div class="value">${active.length}</div><div class="sub">${alarms.length - active.length} acquittée${alarms.length - active.length > 1 ? "s" : ""}</div></div>
      <div class="kpi"><div class="label">Gaspillages</div><div class="value">${waste.length}<small>/ ${events.length}</small></div><div class="sub">sur les dernières mesures</div></div>
      <div class="kpi"><div class="label">CO₂ évitable</div><div class="value">${fmt(co2, 3)}<small>kg</small></div><div class="sub">sur les dernières mesures</div></div>`;

    if (!document.activeElement?.closest?.(".ack-form")) {
      $("#m-alarms").innerHTML = alarmRows(alarms, { showMachine: false });
    }
    const byCause = {};
    waste.forEach((x) => {
      const g = (byCause[x.probable_cause] ||= { count: 0, last: x.timestamp, co2: 0, reco: x.recommendation });
      g.count += 1;
      g.co2 += x.avoidable_co2_kg;
    });
    const groups = Object.entries(byCause).sort((a, b) => b[1].count - a[1].count);
    $("#m-waste").innerHTML = groups.length ? groups.map(([cause, g]) => `
      <tr><td><span class="waste-flag">${esc(CAUSES[cause] || cause)}</span><br><span class="muted">${fmt(g.co2, 3)} kg CO₂</span></td>
      <td class="num">${g.count}</td><td class="num">${time(g.last)}</td><td>${esc(g.reco)}</td></tr>`).join("")
      : `<tr><td colspan="4" class="empty">Aucun gaspillage sur les dernières mesures.</td></tr>`;
  },
};

// ───────────── Alarmes ─────────────
RENDERERS.alarmes = {
  filter: "active",
  init() {
    $("#view").innerHTML = `
      <section class="panel">
        <div class="panel-head">
          <h2>Journal des alarmes</h2>
          <div class="tabs" role="tablist">
            <button type="button" data-f="active" role="tab">Actives</button>
            <button type="button" data-f="acknowledged" role="tab">Acquittées</button>
            <button type="button" data-f="" role="tab">Toutes</button>
          </div>
        </div>
        <p class="muted" style="margin:0 0 10px">Une alarme reste active tant qu'elle n'est pas acquittée. Les répétitions d'un même défaut sont regroupées (colonne Occ.).</p>
        <div class="table-scroll" style="max-height:none">
          <table><thead><tr><th>Priorité</th><th>Machine</th><th>Capteurs hors norme</th><th>Début</th><th>Occ.</th><th>État</th></tr></thead><tbody id="alarm-rows"></tbody></table>
        </div>
      </section>`;
    $("#view .tabs").addEventListener("click", (e) => {
      const b = e.target.closest("button");
      if (!b) return;
      this.filter = b.dataset.f;
      this.refresh();
    });
    bindAckForms($("#alarm-rows"), () => this.refresh());
  },
  async refresh() {
    document.querySelectorAll("#view .tabs button").forEach((b) => {
      b.classList.toggle("active", b.dataset.f === this.filter);
      b.setAttribute("aria-selected", b.dataset.f === this.filter);
    });
    if (document.activeElement?.closest?.(".ack-form")) return; // ne pas effacer une saisie en cours
    const alarms = await api("ia", `/ia/alarms?limit=300${this.filter ? `&status=${this.filter}` : ""}`);
    if (this.filter === "active") alarms.sort((a, b) => SEVERITY_RANK[b.severity] - SEVERITY_RANK[a.severity] || new Date(b.last_seen_at) - new Date(a.last_seen_at));
    $("#alarm-rows").innerHTML = alarmRows(alarms);
  },
};

// ───────────── Énergie et CO2 ─────────────
RENDERERS.energie = {
  init() {
    const canExport = can("reports:export");
    const canSet = can("reports:export", "machines_config:manage");
    $("#view").innerHTML = `
      <div class="grid grid-4" id="e-kpis"></div>
      <section class="panel">
        <div class="panel-head"><h2>Énergie réelle et attendue, toutes machines</h2>
          <select id="e-hours" aria-label="Période"><option value="1">Dernière heure</option><option value="6">6 heures</option><option value="24">24 heures</option><option value="168">7 jours</option></select></div>
        <div class="trend" style="height:240px"><canvas id="e-series"></canvas></div>
      </section>
      <section class="panel">
        <div class="panel-head"><h2>Objectifs de CO₂ évitable par machine (24 h glissantes)</h2>
          ${canExport ? `<form class="inline" id="export-form"><select name="hours" aria-label="Période de l'export"><option value="24">24 heures</option><option value="168">7 jours</option><option value="720">30 jours</option></select><button class="btn" type="submit">Exporter en CSV</button></form>` : ""}</div>
        <table><thead><tr><th>Machine</th><th>CO₂ évitable</th><th>Objectif</th><th>Progression</th>${canSet ? "<th>Modifier l'objectif</th>" : ""}</tr></thead><tbody id="objectives"></tbody></table>
        <p class="muted" style="margin:10px 0 0">L'objectif est le CO₂ évitable maximum accepté sur 24 heures. Au-delà, la barre passe au rouge.</p>
      </section>`;
    $("#e-hours").addEventListener("change", () => { this.userPicked = true; this.refresh(); });
    this.userPicked = false;
    state.charts.series = lineChart($("#e-series"), [], [
      { label: "Réelle (kWh)", data: [], borderColor: "#1c262c", borderWidth: 1.5, pointRadius: 0, tension: 0.25 },
      { label: "Attendue (kWh)", data: [], borderColor: "#7d8a92", borderDash: [4, 3], borderWidth: 1.2, pointRadius: 0 },
      { label: "CO₂ évitable (kg)", data: [], borderColor: "#c8102e", borderWidth: 1.2, pointRadius: 0, yAxisID: "y2" },
    ], { scales: { ...CHART_BASE.scales, y: { ...CHART_BASE.scales.y, beginAtZero: true },
      y2: { position: "right", beginAtZero: true, ticks: { color: "#c8102e" }, grid: { display: false } } } });

    $("#view").addEventListener("submit", async (e) => {
      if (e.target.id === "export-form") {
        e.preventDefault();
        try {
          const res = await api("carbone", `/carbone/export.csv?hours=${e.target.hours.value}`, { raw: true });
          const url = URL.createObjectURL(await res.blob());
          const a = Object.assign(document.createElement("a"), { href: url, download: `carbonghost_${e.target.hours.value}h.csv` });
          a.click();
          URL.revokeObjectURL(url);
          toast("Export CSV téléchargé.", "success");
        } catch (err) { toast(err.message, "error"); }
      }
      const form = e.target.closest(".objective-form");
      if (form) {
        e.preventDefault();
        try {
          await api("carbone", `/carbone/objectives/${encodeURIComponent(form.dataset.machine)}`, { method: "PUT", body: { daily_co2_target_kg: Number(form.target.value) } });
          toast(`Objectif de ${form.dataset.machine} enregistré.`, "success");
          document.activeElement?.blur();
          this.refresh();
        } catch (err) { toast(err.message, "error"); }
      }
    });
  },
  async refresh() {
    if (!this.userPicked) {
      // Période par défaut : la plus courte qui contient l'historique disponible (au moins 1 h, au plus 7 jours)
      const first = await api("carbone", "/carbone/series?hours=168&bucket_minutes=60");
      const ageH = first.length ? (Date.now() - new Date(first[0].bucket)) / 3.6e6 : 0;
      $("#e-hours").value = ageH <= 1 ? "1" : ageH <= 6 ? "6" : ageH <= 24 ? "24" : "168";
    }
    const hours = Number($("#e-hours")?.value || 24);
    const bucket = hours <= 1 ? 1 : hours <= 6 ? 5 : hours <= 24 ? 15 : 120;
    const [series, objectives, summary] = await Promise.all([
      api("carbone", `/carbone/series?hours=${hours}&bucket_minutes=${bucket}`),
      api("carbone", "/carbone/objectives"),
      api("carbone", "/carbone/summary?hours=24"),
    ]);
    const sum = (k) => summary.reduce((t, s) => t + (s[k] || 0), 0);
    const exceeded = objectives.filter((o) => o.exceeded).length;
    $("#e-kpis").innerHTML = `
      <div class="kpi"><div class="label">CO₂ évitable, 24 h</div><div class="value">${fmt(sum("avoidable_co2_kg"), 2)}<small>kg</small></div><div class="sub">facteur d'émission 0,5 kg/kWh</div></div>
      <div class="kpi"><div class="label">Énergie gaspillée, 24 h</div><div class="value">${fmt(sum("wasted_kwh"), 2)}<small>kWh</small></div><div class="sub">sur ${fmt(sum("actual_kwh"), 1)} kWh consommés</div></div>
      <div class="kpi"><div class="label">Taux de gaspillage</div><div class="value">${fmt(sum("events") ? (sum("waste_events") / sum("events")) * 100 : 0, 1)}<small>%</small></div><div class="sub">des mesures analysées</div></div>
      <div class="kpi"><div class="label">Objectifs dépassés</div><div class="value">${exceeded}<small>/ ${objectives.filter((o) => o.daily_co2_target_kg).length}</small></div><div class="sub">machines avec objectif</div></div>`;

    const c = state.charts.series;
    if (c) {
      c.data.labels = series.map((s) => time(s.bucket).slice(0, 5));
      c.data.datasets[0].data = series.map((s) => s.actual_kwh);
      c.data.datasets[1].data = series.map((s) => s.expected_kwh);
      c.data.datasets[2].data = series.map((s) => s.avoidable_co2_kg);
      c.update();
    }

    if (document.activeElement?.closest?.(".objective-form")) return;
    const canSet = can("reports:export", "machines_config:manage");
    const byId = Object.fromEntries(objectives.map((o) => [o.machine_id, o]));
    const ids = [...new Set([...state.machines.map((m) => m.id), ...objectives.map((o) => o.machine_id)])].sort();
    $("#objectives").innerHTML = ids.map((id) => {
      const o = byId[id] || { avoidable_co2_kg_24h: 0 };
      const pct = o.progress_pct;
      return `<tr>
        <td><b>${esc(id)}</b> <span class="muted">${esc(machineName(id))}</span></td>
        <td class="num">${fmt(o.avoidable_co2_kg_24h, 3)} kg</td>
        <td class="num">${o.daily_co2_target_kg ? `${fmt(o.daily_co2_target_kg, 2)} kg` : '<span class="muted">non défini</span>'}</td>
        <td>${pct !== null && pct !== undefined ? `<div class="bar ${o.exceeded ? "over" : ""}" title="${fmt(pct, 0)} %"><span style="width:${Math.min(pct, 100)}%"></span></div><span class="muted num">${fmt(pct, 0)} %${o.exceeded ? ", dépassé" : ""}</span>` : '<span class="muted">–</span>'}</td>
        ${canSet ? `<td><form class="inline objective-form" data-machine="${esc(id)}"><input type="number" name="target" min="0.01" step="0.01" value="${o.daily_co2_target_kg ?? ""}" style="width:90px" aria-label="Objectif en kg pour ${esc(id)}" required><button class="btn btn-small" type="submit">Enregistrer</button></form></td>` : ""}
      </tr>`;
    }).join("");
  },
};

// ───────────── Rapports ─────────────
RENDERERS.rapports = {
  selected: null,
  init() {
    $("#view").innerHTML = `
      <section class="panel">
        <div class="panel-head"><h2>Rapports</h2>
          <form class="inline" id="report-form"><select name="hours" aria-label="Période du rapport"><option value="1">Dernière heure</option><option value="8">Dernières 8 h (un poste)</option><option value="24" selected>Dernières 24 h</option></select><button class="btn btn-primary" type="submit" id="report-btn">Générer le rapport</button></form></div>
        <p class="muted" style="margin:0 0 12px">Un rapport est généré automatiquement toutes les 24 heures et conservé ici.</p>
        <div class="report-layout">
          <ul class="report-list" id="report-list"></ul>
          <div class="report-body panel" style="background:var(--panel-raised)" id="report-body"><span class="muted">Sélectionnez un rapport.</span></div>
        </div>
      </section>`;
    $("#report-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const btn = $("#report-btn");
      btn.disabled = true;
      btn.textContent = "Génération…";
      try {
        const r = await api("assistant", "/assistant/report", { method: "POST", body: { hours: Number(e.target.hours.value) } });
        this.selected = r.id;
        toast("Rapport généré.", "success");
        await this.refresh();
      } catch (err) { toast(err.message, "error"); }
      finally { btn.disabled = false; btn.textContent = "Générer le rapport"; }
    });
    $("#report-list").addEventListener("click", (e) => {
      const b = e.target.closest("button[data-id]");
      if (b) { this.selected = b.dataset.id; this.render(); }
    });
  },
  reports: [],
  async refresh() {
    this.reports = await api("assistant", "/assistant/reports?limit=50");
    if (!this.selected && this.reports[0]) this.selected = this.reports[0].id;
    this.render();
  },
  render() {
    $("#report-list").innerHTML = this.reports.length ? this.reports.map((r) => `
      <li><button type="button" data-id="${r.id}" class="${r.id === this.selected ? "active" : ""}">
        <b>${dateTime(r.created_at)}</b><br><span class="muted">${r.generated_by === "automatique" ? "Automatique" : `Par ${esc(r.generated_by)}`}, période ${fmt(r.period_hours, 0)} h</span>
      </button></li>`).join("") : `<li class="empty">Aucun rapport pour l'instant. Générez-en un.</li>`;
    const r = this.reports.find((x) => x.id === this.selected);
    $("#report-body").innerHTML = r ? esc(r.content) : '<span class="muted">Sélectionnez un rapport.</span>';
  },
};

// ───────────── Assistant ─────────────
RENDERERS.assistant = {
  init(machineId) {
    const opts = state.machines.map((m) => `<option value="${esc(m.id)}" ${m.id === machineId ? "selected" : ""}>${esc(m.id)}, ${esc(m.name)}</option>`).join("");
    const suggestions = ["Pourquoi cette machine consomme-t-elle trop ?", "Que dois-je faire en priorité ?", "Combien de CO2 aurait-on pu éviter ?", "Y a-t-il des signes d'usure ?", "Cette machine fonctionne-t-elle normalement ?"];
    $("#view").innerHTML = `
      <section class="panel">
        <div class="panel-head"><h2>Questions sur une machine</h2><select id="a-machine" aria-label="Machine">${opts}</select></div>
        <div class="chat" id="chat" aria-live="polite"></div>
        <div class="suggestions" style="margin:12px 0">${suggestions.map((s) => `<button class="btn btn-small" type="button" data-q="${esc(s)}">${esc(s)}</button>`).join("")}</div>
        <form class="inline" id="ask-form" style="flex-wrap:nowrap">
          <input type="text" id="question" placeholder="Votre question" aria-label="Votre question" style="flex:1" required>
          <button class="btn btn-primary" type="submit" id="ask-btn">Envoyer</button>
        </form>
      </section>`;
    this.renderChat();
    $("#view .suggestions").addEventListener("click", (e) => {
      const b = e.target.closest("button[data-q]");
      if (b) this.ask(b.dataset.q);
    });
    $("#ask-form").addEventListener("submit", (e) => { e.preventDefault(); this.ask($("#question").value.trim()); });
  },
  renderChat() {
    const chat = $("#chat");
    chat.innerHTML = state.chat.length ? state.chat.map((m) => `<div class="msg ${m.q ? "q" : "a"}">${esc(m.text)}</div>`).join("")
      : `<div class="muted">Choisissez une machine puis posez une question, ou utilisez une suggestion.</div>`;
    chat.scrollTop = chat.scrollHeight;
  },
  async ask(question) {
    if (!question) return;
    const machine = $("#a-machine").value;
    state.chat.push({ q: true, text: `${machine} : ${question}` });
    this.renderChat();
    $("#question").value = "";
    $("#ask-btn").disabled = true;
    try {
      const r = await api("assistant", "/assistant/ask", { method: "POST", body: { machine_id: machine, question } });
      state.chat.push({ q: false, text: r.answer });
    } catch (err) {
      state.chat.push({ q: false, text: err.message });
    } finally {
      $("#ask-btn").disabled = false;
      this.renderChat();
    }
  },
};

// ───────────── Administration ─────────────
RENDERERS.admin = {
  init() {
    const machines = can("machines_config:manage");
    const users = can("users:manage");
    $("#view").innerHTML = `
      ${machines ? `<section class="panel">
        <div class="panel-head"><h2>Machines</h2></div>
        <table><thead><tr><th>Identifiant</th><th>Nom</th><th>Ligne</th><th>Puissance</th><th>État</th><th></th></tr></thead><tbody id="adm-machines"></tbody></table>
        <h3 style="margin:18px 0 8px">Ajouter une machine</h3>
        <form class="inline" id="add-machine">
          <div class="field"><label for="am-id">Identifiant capteur</label><input id="am-id" name="id" type="text" required placeholder="M5" style="width:90px"></div>
          <div class="field"><label for="am-name">Nom</label><input id="am-name" name="name" type="text" required placeholder="Four de cuisson"></div>
          <div class="field"><label for="am-line">Ligne</label><input id="am-line" name="production_line" type="text" required placeholder="Ligne B"></div>
          <div class="field"><label for="am-power">Puissance (kW)</label><input id="am-power" name="nominal_power_kw" type="number" min="0" step="0.1" value="3" style="width:90px"></div>
          <button class="btn btn-primary" type="submit">Ajouter la machine</button>
        </form>
      </section>` : ""}
      ${users ? `<section class="panel">
        <div class="panel-head"><h2>Utilisateurs</h2></div>
        <table><thead><tr><th>Nom</th><th>Email</th><th>Rôle</th><th>Badge</th><th>Compte</th></tr></thead><tbody id="adm-users"></tbody></table>
      </section>` : ""}`;

    $("#view").addEventListener("submit", async (e) => {
      if (e.target.id !== "add-machine") return;
      e.preventDefault();
      const f = e.target;
      try {
        await api("factory", "/factory/machines", { method: "POST", body: {
          id: f.id.value.trim(), name: f.name.value.trim(), production_line: f.production_line.value.trim(),
          nominal_power_kw: Number(f.nominal_power_kw.value) } });
        toast(`Machine ${f.id.value} ajoutée.`, "success");
        f.reset();
        await loadMachines();
        this.refresh();
      } catch (err) { toast(err.message, "error"); }
    });
    $("#view").addEventListener("change", async (e) => {
      const sel = e.target.closest("select[data-status]");
      if (!sel) return;
      try {
        await api("factory", `/factory/machines/${encodeURIComponent(sel.dataset.status)}`, { method: "PATCH", body: { status: sel.value } });
        toast(`État de ${sel.dataset.status} mis à jour.`, "success");
        await loadMachines();
      } catch (err) { toast(err.message, "error"); }
    });
    $("#view").addEventListener("click", async (e) => {
      const del = e.target.closest("button[data-delete]");
      if (del && confirm(`Supprimer la machine ${del.dataset.delete} ? Son historique de mesures est conservé.`)) {
        try {
          await api("factory", `/factory/machines/${encodeURIComponent(del.dataset.delete)}`, { method: "DELETE" });
          toast(`Machine ${del.dataset.delete} supprimée.`, "success");
          await loadMachines();
          this.refresh();
        } catch (err) { toast(err.message, "error"); }
      }
      const tog = e.target.closest("button[data-user]");
      if (tog) {
        try {
          await api("user", `/user/${tog.dataset.user}/active?active=${tog.dataset.active}`, { method: "PATCH" });
          toast(tog.dataset.active === "true" ? "Compte réactivé." : "Compte désactivé.", "success");
          this.refresh();
        } catch (err) { toast(err.message, "error"); }
      }
    });
  },
  async refresh() {
    if (document.activeElement?.closest?.("form")) return;
    if (can("machines_config:manage")) {
      const ms = await api("factory", "/factory/machines");
      $("#adm-machines").innerHTML = ms.map((m) => `<tr>
        <td><b>${esc(m.id)}</b></td><td>${esc(m.name)}</td><td>${esc(m.production_line)}</td><td class="num">${fmt(m.nominal_power_kw, 1)} kW</td>
        <td><select data-status="${esc(m.id)}" aria-label="État de ${esc(m.id)}">${["active", "maintenance", "stopped"].map((s) =>
          `<option value="${s}" ${m.status === s ? "selected" : ""}>${{ active: "En service", maintenance: "En maintenance", stopped: "À l'arrêt" }[s]}</option>`).join("")}</select></td>
        <td><button class="btn btn-small" type="button" data-delete="${esc(m.id)}">Supprimer</button></td></tr>`).join("");
    }
    if (can("users:manage")) {
      const us = await api("user", "/user/");
      $("#adm-users").innerHTML = us.map((u) => `<tr class="${u.is_active ? "" : "acked"}">
        <td>${esc(u.username)}</td><td>${esc(u.email)}</td><td>${esc(ROLE_LABELS[u.role] || u.role)}</td><td>${esc(u.badge_id || "–")}</td>
        <td>${u.email === state.user.email ? '<span class="muted">Votre compte</span>'
          : `<button class="btn btn-small" type="button" data-user="${u.id}" data-active="${!u.is_active}">${u.is_active ? "Désactiver" : "Réactiver"}</button>`}</td></tr>`).join("");
    }
  },
};

// ═════════════════════════════ Démarrage ═════════════════════════════

setInterval(() => { $("#clock").textContent = new Date().toLocaleTimeString("fr-FR"); }, 1000);
$("#clock").textContent = new Date().toLocaleTimeString("fr-FR");

const saved = store.get("cg_token");
if (saved && decodeToken(saved)) startSession(saved);
else showLogin();
