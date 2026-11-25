/* KEREM Spa - cliente PWA */
"use strict";

const API = "";
const TOKEN_KEY = "kerem_token";
const USER_KEY = "kerem_user";
const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);

function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => t.classList.remove("show"), 2800);
}

function setOfflineUI() {
  const off = !navigator.onLine;
  $("#offlineBar")?.classList.toggle("show", off);
}

async function api(path, { method = "GET", body } = {}) {
  if (!navigator.onLine && method !== "GET") {
    throw new Error("Sin conexión. Esta acción requiere internet.");
  }
  const headers = { "Content-Type": "application/json" };
  const token = sessionStorage.getItem(TOKEN_KEY);
  if (token) headers["Authorization"] = `Bearer ${token}`;
  let res;
  try {
    res = await fetch(API + path, { method, headers, body: body ? JSON.stringify(body) : undefined });
  } catch {
    throw new Error("No se pudo conectar con el servidor.");
  }
  if (res.status === 204) return null;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = data && (data.detail || data.message);
    throw new Error(typeof detail === "string" ? detail : "Error del servidor.");
  }
  return data;
}

function setAuth(token) { sessionStorage.setItem(TOKEN_KEY, token); }
function saveUser(user) { sessionStorage.setItem(USER_KEY, JSON.stringify(user)); }
function clearAuth() { sessionStorage.removeItem(TOKEN_KEY); sessionStorage.removeItem(USER_KEY); }
function getToken() { return sessionStorage.getItem(TOKEN_KEY); }
function getUser() { try { return JSON.parse(sessionStorage.getItem(USER_KEY)); } catch { return null; } }

function fmtCurrency(n) { return "$" + Number(n || 0).toFixed(2); }
function dmy(iso) {
  return new Date(iso).toLocaleString("es-MX", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}
function statusBadge(status) {
  const map = {
    pending: ["Pendiente", "badge-pending"],
    approved: ["Aprobada", "badge-approved"],
    cancelled: ["Cancelada", "badge-cancelled"],
    completed: ["Completada", "badge-completed"],
  };
  const [label, cls] = map[status] || [status, "badge-pending"];
  return `<span class="badge ${cls}">${label}</span>`;
}
function escapeHtml(v) {
  return String(v ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
}

function show(el) { $(el)?.classList.remove("hidden"); }
function hide(el) { $(el)?.classList.add("hidden"); }

function showAuth() {
  show("#authView"); hide("#clientView");
  $("#authView").style.display = "";
}
function showApp() {
  if (!getToken()) { showAuth(); return; }
  hide("#authView"); $("#authView").style.display = "none";
  show("#clientView");
  loadClientData();
}

// Auth tabs
function switchTab(which) {
  const login = which === "login";
  $("#loginForm").classList.toggle("hidden", !login);
  $("#registerForm").classList.toggle("hidden", login);
  $("#tabLogin").classList.toggle("active", login);
  $("#tabRegister").classList.toggle("active", !login);
  hide("#loginError"); hide("#registerError");
}

async function handleLogin(e) {
  e.preventDefault();
  hide("#loginError");
  const fd = new FormData(e.target);
  try {
    const data = await api("/auth/login", { method: "POST", body: { email: fd.get("email"), password: fd.get("password") } });
    setAuth(data.access_token);
    const me = await api("/auth/me");
    saveUser(me);
    if (me.role === "admin") { location.href = "/dashboard"; return; }
    showApp();
  } catch (err) {
    $("#loginError").textContent = err.message;
    show("#loginError");
  }
}

async function handleRegister(e) {
  e.preventDefault();
  hide("#registerError");
  const fd = new FormData(e.target);
  try {
    const data = await api("/auth/register", {
      method: "POST",
      body: {
        email: fd.get("email"), password: fd.get("password"),
        full_name: fd.get("full_name"), phone: fd.get("phone") || null,
      },
    });
    setAuth(data.access_token);
    const me = await api("/auth/me");
    saveUser(me);
    showApp();
  } catch (err) {
    $("#registerError").textContent = err.message;
    show("#registerError");
  }
}

// Client tabs
function switchClientTab(tab) {
  const isBook = tab === "book";
  $("#tabBook").classList.toggle("active", isBook);
  $("#tabAppointments").classList.toggle("active", !isBook);
  $("#clientTabBook").classList.toggle("active", isBook);
  $("#clientTabAppointments").classList.toggle("active", !isBook);
  if (!isBook) loadMyAppointments();
}

// Wizard
const STEP_SERVICE = 1, STEP_SCHEDULE = 2, STEP_CONFIRM = 3;
let currentStep = STEP_SERVICE;
let selectedService = null;
let selectedSlot = null;
let slotButtons = [];

function renderStepIndicator() {
  [1, 2, 3].forEach((n) => {
    const item = document.querySelector(`.step-item[data-step="${n}"]`);
    if (!item) return;
    item.classList.toggle("active", n === currentStep);
    item.classList.toggle("done", n < currentStep);
    const dot = $(`#stepDot${n}`);
    if (dot) dot.textContent = n < currentStep ? "✓" : String(n);
  });
  $("#stepLine1")?.classList.toggle("done", currentStep > 1);
  $("#stepLine2")?.classList.toggle("done", currentStep > 2);
}

function goToStep(n) {
  currentStep = n;
  ["#wStep1", "#wStep2", "#wStep3"].forEach((sel, i) => $(sel).classList.toggle("hidden", i + 1 !== n));
  renderStepIndicator();
  if (n === STEP_SCHEDULE && !$("#dateInput").value && !$("#slotsGrid").children.length) {
    $("#dateInput").min = new Date().toISOString().split("T")[0];
    $("#slotHint").textContent = "Elige una fecha para ver horarios.";
    show("#slotHint");
  }
}

function nextStep() {
  if (currentStep === STEP_SERVICE) {
    if (!selectedService) { show("#step1Hint"); return; }
    hide("#step1Hint"); goToStep(STEP_SCHEDULE);
  } else if (currentStep === STEP_SCHEDULE) {
    if (!selectedSlot) { show("#step2Hint"); return; }
    hide("#step2Hint"); renderConfirm(); goToStep(STEP_CONFIRM);
  } else if (currentStep === STEP_CONFIRM) {
    bookAppointment();
  }
}

function prevStep() {
  if (currentStep === STEP_SCHEDULE) { hide("#step2Hint"); goToStep(STEP_SERVICE); }
  else if (currentStep === STEP_CONFIRM) goToStep(STEP_SCHEDULE);
}

function resetWizard() {
  selectedService = null; selectedSlot = null; slotButtons = [];
  $("#slotsGrid").innerHTML = "";
  $("#dateInput").value = "";
  $("#nextBtn1").disabled = true;
  $("#nextBtn2").disabled = true;
  hide("#step1Hint"); hide("#step2Hint"); hide("#slotHint");
  loadServices();
  goToStep(STEP_SERVICE);
}

async function loadClientData() {
  const me = getUser();
  $("#clientName").textContent = me?.full_name ? `Hola, ${me.full_name}` : "Bienvenida";
  await Promise.all([loadServices(), loadMyAppointments(), loadNotifCount()]);
}

async function loadServices() {
  const list = $("#serviceList");
  try {
    const services = await api("/services");
    if (!services.length) {
      list.innerHTML = '<div class="empty-state"><div class="empty-icon">✦</div><p class="empty-title">No hay servicios disponibles</p></div>';
      return;
    }
    list.innerHTML = "";
    services.forEach((svc) => {
      const el = document.createElement("button");
      el.type = "button";
      el.className = "service-card";
      el.innerHTML = `
        <div>
          <p class="service-name">${escapeHtml(svc.name)}</p>
          <p class="service-meta">${svc.duration_minutes} min${svc.description ? " · " + escapeHtml(svc.description) : ""}</p>
        </div>
        <div class="service-price">${fmtCurrency(svc.price)}</div>`;
      el.addEventListener("click", () => selectService(svc, el));
      list.appendChild(el);
    });
  } catch (err) {
    list.innerHTML = `<div class="empty-state"><p class="empty-title">No se pudieron cargar servicios</p><p class="small">${escapeHtml(err.message)}</p></div>`;
  }
}

function selectService(svc, node) {
  selectedService = svc; selectedSlot = null;
  $$("#serviceList .service-card").forEach((b) => b.classList.remove("selected"));
  node.classList.add("selected");
  $("#nextBtn1").disabled = false;
  hide("#step1Hint");
}

async function loadSlots() {
  if (!selectedService || !$("#dateInput").value) return;
  const day = $("#dateInput").value;
  $("#slotHint").textContent = "Cargando horarios…"; show("#slotHint");
  $("#slotsGrid").innerHTML = "";
  slotButtons = []; selectedSlot = null; $("#nextBtn2").disabled = true; hide("#step2Hint");
  try {
    const slots = await api(`/appointments/slots?service_id=${selectedService.id}&day=${day}`);
    hide("#slotHint");
    if (!slots.length) {
      $("#slotsGrid").innerHTML = '<p class="small muted" style="grid-column:1/-1;">No hay horarios disponibles este día.</p>';
      return;
    }
    slots.forEach((s) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "slot-btn";
      b.textContent = new Date(s.starts_at).toLocaleTimeString("es-MX", { hour: "2-digit", minute: "2-digit" });
      b.addEventListener("click", () => {
        selectedSlot = s;
        slotButtons.forEach((x) => x.classList.remove("active"));
        b.classList.add("active");
        $("#nextBtn2").disabled = false; hide("#step2Hint");
      });
      $("#slotsGrid").appendChild(b);
      slotButtons.push(b);
    });
  } catch (err) {
    hide("#slotHint");
    $("#slotsGrid").innerHTML = `<p class="small" style="color:var(--danger);grid-column:1/-1;">${escapeHtml(err.message)}</p>`;
  }
}

function renderConfirm() {
  $("#confirmSummary").innerHTML = `
    <div class="list-row"><span class="muted small">Servicio</span><span class="font-semibold">${escapeHtml(selectedService.name)}</span></div>
    <div class="list-row mt-2"><span class="muted small">Duración</span><span>${selectedService.duration_minutes} min</span></div>
    <div class="list-row mt-2"><span class="muted small">Fecha</span><span>${dmy(selectedSlot.starts_at)}</span></div>
    <div class="divider" style="margin:12px 0;"></div>
    <div class="list-row"><span class="muted small">Total</span><span class="font-bold" style="color:var(--brand);">${fmtCurrency(selectedService.price)}</span></div>`;
}

async function bookAppointment() {
  if (!selectedSlot) return;
  const btn = $("#bookBtn");
  btn.disabled = true;
  try {
    await api("/appointments", { method: "POST", body: { service_id: selectedService.id, starts_at: selectedSlot.starts_at } });
    resetWizard();
    await loadMyAppointments();
    switchClientTab("appointments");
    loadNotifCount();
    toast("Cita agendada. Espera la confirmación del spa.");
  } catch (err) {
    toast(err.message);
  } finally {
    btn.disabled = false;
  }
}

async function loadMyAppointments() {
  const ctn = $("#myAppointments");
  try {
    const appts = await api("/appointments");
    if (!appts.length) {
      ctn.innerHTML = '<div class="empty-state"><div class="empty-icon">📅</div><p class="empty-title">Sin citas todavía</p><p class="small">Agenda tu primer servicio.</p></div>';
      return;
    }
    ctn.innerHTML = appts.map((a) => `
      <div class="list-card">
        <div class="list-row">
          <div>
            <p class="list-title">${escapeHtml(a.service_name || "Servicio")}</p>
            <p class="list-meta">${dmy(a.starts_at)}</p>
          </div>
          ${statusBadge(a.status)}
        </div>
        ${a.status === "pending" || a.status === "approved" ? `<div class="list-actions"><button data-cancel="${a.id}" class="btn btn-danger btn-sm">Cancelar cita</button></div>` : ""}
      </div>`).join("");
    ctn.querySelectorAll("[data-cancel]").forEach((b) => b.addEventListener("click", () => cancelAppointment(b.dataset.cancel)));
  } catch (err) {
    ctn.innerHTML = `<div class="empty-state"><p class="small" style="color:var(--danger);">${escapeHtml(err.message)}</p></div>`;
  }
}

async function cancelAppointment(id) {
  if (!confirm("¿Cancelar esta cita?")) return;
  try {
    await api(`/appointments/${id}/cancel`, { method: "PATCH" });
    toast("Cita cancelada");
    await loadMyAppointments();
    loadNotifCount();
  } catch (err) { toast(err.message); }
}

// Notifications
async function loadNotifCount() {
  const badge = $("#notifBadge");
  if (!getToken()) return;
  try {
    const { count } = await api("/notifications/unread-count");
    badge.textContent = count > 99 ? "99+" : count;
    badge.classList.toggle("hidden", count <= 0);
  } catch { /* ignore */ }
}

async function loadNotifications() {
  const list = $("#notifList");
  try {
    const notes = await api("/notifications");
    if (!notes.length) {
      list.innerHTML = '<div class="empty-state" style="padding:20px;"><p class="small">No hay notificaciones.</p></div>';
      return;
    }
    list.innerHTML = notes.map((n) => `
      <div class="notif-item ${n.is_read ? "" : "unread"}" data-nid="${n.id}">
        <p class="notif-title">${escapeHtml(n.title)}</p>
        <p class="notif-msg">${escapeHtml(n.message)}</p>
        <div class="notif-time">${dmy(n.created_at)}</div>
      </div>`).join("");
  } catch (err) {
    list.innerHTML = `<div class="empty-state" style="padding:20px;"><p class="small" style="color:var(--danger);">${escapeHtml(err.message)}</p></div>`;
  }
}

async function toggleNotifPanel() {
  const panel = $("#notifPanel");
  const opening = panel.classList.contains("hidden");
  panel.classList.toggle("hidden");
  if (opening) await loadNotifications();
}

async function markNotifRead(nid) {
  try { await api(`/notifications/${nid}/read`, { method: "PATCH" }); loadNotifCount(); loadNotifications(); } catch {}
}
async function markAllNotifsRead() {
  try { await api("/notifications/read-all", { method: "PATCH" }); loadNotifCount(); loadNotifications(); } catch (e) { toast(e.message); }
}

document.addEventListener("click", (e) => {
  const panel = $("#notifPanel");
  if (!panel || panel.classList.contains("hidden")) return;
  if (e.target.closest("#notifBtn") || e.target.closest("#notifPanel")) return;
  panel.classList.add("hidden");
});

// Init
function registerSW() {
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  }
}

function init() {
  registerSW();
  setOfflineUI();
  window.addEventListener("online", setOfflineUI);
  window.addEventListener("offline", setOfflineUI);

  $("#tabLogin").addEventListener("click", () => switchTab("login"));
  $("#tabRegister").addEventListener("click", () => switchTab("register"));
  $("#loginForm").addEventListener("submit", handleLogin);
  $("#registerForm").addEventListener("submit", handleRegister);
  $("#logoutBtn").addEventListener("click", () => { clearAuth(); $("#loginForm").reset(); $("#registerForm").reset(); switchTab("login"); showAuth(); });
  $("#dateInput").addEventListener("change", loadSlots);
  $("#nextBtn1").addEventListener("click", nextStep);
  $("#nextBtn2").addEventListener("click", nextStep);
  $("#backBtn2").addEventListener("click", prevStep);
  $("#backBtn3").addEventListener("click", prevStep);
  $("#bookBtn").addEventListener("click", nextStep);
  $("#refreshAppts").addEventListener("click", loadMyAppointments);
  document.querySelectorAll(".step-item").forEach((item) => item.addEventListener("click", () => {
    const n = Number(item.dataset.step);
    if (n < currentStep) goToStep(n);
  }));
  $$("#clientTabBook, #clientTabAppointments").forEach((b) => b.addEventListener("click", () => switchClientTab(b.dataset.tab)));
  $("#notifBtn").addEventListener("click", toggleNotifPanel);
  $("#notifReadAll").addEventListener("click", markAllNotifsRead);
  $("#notifList").addEventListener("click", (e) => {
    const row = e.target.closest("[data-nid]");
    if (row) markNotifRead(row.dataset.nid);
  });

  showApp();
}

document.addEventListener("DOMContentLoaded", init);
