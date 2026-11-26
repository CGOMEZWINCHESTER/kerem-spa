/* KEREM Spa - admin PWA */
"use strict";

const API = "";
const TOKEN_KEY = "kerem_token";
const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);

function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => t.classList.remove("show"), 2800);
}
function setOfflineUI() { $("#offlineBar")?.classList.toggle("show", !navigator.onLine); }

async function api(path, { method = "GET", body } = {}) {
  if (!navigator.onLine && method !== "GET") throw new Error("Sin conexión. Esta acción requiere internet.");
  const headers = { "Content-Type": "application/json" };
  const token = sessionStorage.getItem(TOKEN_KEY);
  if (token) headers["Authorization"] = `Bearer ${token}`;
  let res;
  try { res = await fetch(API + path, { method, headers, body: body ? JSON.stringify(body) : undefined }); }
  catch { throw new Error("No se pudo conectar con el servidor."); }
  if (res.status === 204) return null;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    let msg = (data && data.detail) || "Error del servidor.";
    if (Array.isArray(msg)) msg = msg.map((e) => String(e.msg || "").replace(/^Value error,\s*/, "") || "Dato inválido").join("; ");
    throw new Error(msg);
  }
  return data;
}

function fmtCurrency(n) { return "$" + Number(n || 0).toFixed(2); }
function dmy(iso) { return new Date(iso).toLocaleString("es-MX", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }); }
function statusBadge(s) {
  const map = { pending: ["Pendiente", "badge-pending"], approved: ["Aprobada", "badge-approved"], cancelled: ["Cancelada", "badge-cancelled"], completed: ["Completada", "badge-completed"] };
  const [l, c] = map[s] || [s, "badge-pending"];
  return `<span class="badge ${c}">${l}</span>`;
}
function esc(v) { return String(v ?? "").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;"); }

function requireAuth() {
  if (!sessionStorage.getItem(TOKEN_KEY)) { location.href = "/"; return false; }
  let user = null; try { user = JSON.parse(sessionStorage.getItem("kerem_user")); } catch {}
  if (!user || user.role !== "admin") { location.href = "/"; return false; }
  $("#adminUserLabel").textContent = user.full_name || "Administrador";
  return true;
}

function showPanel(name) {
  $$(".panel").forEach((p) => p.classList.add("hidden"));
  $(`#panel-${name}`)?.classList.remove("hidden");
  $$(".nav-btn").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
}
function setVersionBadge() { const el = $("#appVersion"); if (el) el.textContent = "v20261125g"; }

// Modal
let modalOkHandler = null;
const modalValues = new Map();
function openModal(title, bodyHtml, onOk, wide = false) {
  modalOkHandler = onOk; modalValues.clear();
  $("#modalTitle").textContent = title;
  $("#modalBody").innerHTML = bodyHtml;
  $("#modal").classList.add("open");
  const card = $(".sheet-modal");
  if (card) card.style.maxWidth = wide ? "920px" : "640px";
}
function closeModal() { $("#modal").classList.remove("open"); modalOkHandler = null; }
function trackModalInput(target) {
  const inBody = target.closest ? target.closest("#modalBody") : null;
  if (!inBody || !target.id) return;
  modalValues.set(target.id, target.type === "checkbox" || target.type === "radio" ? target.checked : target.value);
}
function fRead(id) {
  if (modalValues.has(id)) { const m = modalValues.get(id); return m === true ? "" : String(m ?? "").trim(); }
  const el = document.getElementById(id); return el ? String(el.value ?? "").trim() : "";
}
function fChecked(id) { if (modalValues.has(id)) return modalValues.get(id) === true; const el = document.getElementById(id); return !!(el && el.checked); }
function fNum(id) { const s = fRead(id); const n = Number(s); return s === "" || isNaN(n) || n <= 0 ? null : n; }
function fHasData() { if (modalValues.size) return [...modalValues.values()].some((m) => m === true ? true : String(m ?? "").trim() !== ""); return [...$("#modalBody").querySelectorAll("input,select,textarea")].some((e)=> e.type==="checkbox"?e.checked:!!(e.value||"").trim()); }

// Citas
async function loadAppointments(f = "") {
  const ctn = $("#adminAppointments");
  try {
    const q = f ? `?status_filter=${f}` : "";
    const appts = await api("/admin/appointments" + q);
    if (!appts.length) { ctn.innerHTML = '<div class="empty-state"><div class="empty-icon">📅</div><p class="empty-title">No hay citas</p></div>'; return; }
    ctn.innerHTML = appts.map((a) => `
      <div class="list-card">
        <div class="list-row">
          <div>
            <p class="list-title">${esc(a.service_name || "Servicio")}</p>
            <p class="list-meta"><strong style="color:var(--text)">${esc(a.client_name || "Cliente")}</strong>${a.client_phone ? ` · <a href="tel:${esc(a.client_phone)}" style="color:var(--brand)">${esc(a.client_phone)}</a>` : ""}</p>
            <p class="list-meta">${a.client_email ? esc(a.client_email) + " · " : ""}${dmy(a.starts_at)}</p>
          </div>
          ${statusBadge(a.status)}
        </div>
        <div class="list-actions">
          <button data-appt="${a.id}" data-action="approved" class="btn btn-sm btn-ghost">Aprobar</button>
          <button data-appt="${a.id}" data-action="reschedule" class="btn btn-sm btn-ghost">Reagendar</button>
          <button data-appt="${a.id}" data-action="completed" class="btn btn-sm btn-ghost">Completar</button>
          <button data-appt="${a.id}" data-action="cancelled" class="btn btn-sm btn-danger">Cancelar</button>
        </div>
      </div>`).join("");
    ctn.querySelectorAll("[data-appt]").forEach((b) => b.addEventListener("click", () => appointmentAction(b)));
  } catch (err) { ctn.innerHTML = `<div class="empty-state"><p class="small" style="color:var(--danger)">${esc(err.message)}</p></div>`; }
}

async function appointmentAction(btn) {
  const id = btn.dataset.appt; const action = btn.dataset.action;
  if (action === "reschedule") {
    openModal("Reagendar cita", `
      <div class="field"><label class="label">Nueva fecha y hora</label>
      <input type="datetime-local" id="newStart" class="input" /></div>`, async () => {
        const val = $("#newStart")?.value;
        if (!val) { toast("Selecciona una fecha y hora."); return; }
        await api(`/admin/appointments/${id}`, { method: "PATCH", body: { starts_at: new Date(val).toISOString() } });
        closeModal(); loadAppointments($("#filterStatus").value); toast("Cita reagendada");
      });
    return;
  }
  try {
    await api(`/admin/appointments/${id}`, { method: "PATCH", body: { status: action } });
    loadAppointments($("#filterStatus").value);
    toast("Cita actualizada");
  } catch (err) { toast(err.message); }
}

// Pacientes
async function loadPatients(q = "") {
  const ctn = $("#patientList");
  try {
    const pts = await api("/admin/patients" + (q ? `?q=${encodeURIComponent(q)}` : ""));
    if (!pts.length) { ctn.innerHTML = '<div class="empty-state"><div class="empty-icon">👤</div><p class="empty-title">No hay pacientes</p></div>'; return; }
    ctn.innerHTML = pts.map((p) => `
      <div class="list-card">
        <div class="list-row">
          <div>
            <p class="list-title">${esc(p.full_name)}</p>
            <p class="list-meta">${esc(p.email)}${p.phone ? " · " + esc(p.phone) : ""}</p>
          </div>
        </div>
        <div class="list-actions">
          <button data-pid="${p.id}" data-act="ficha" class="btn btn-sm btn-ghost">Ficha</button>
          <button data-pid="${p.id}" data-act="records" class="btn btn-sm btn-ghost">Evolución</button>
          <button data-pid="${p.id}" data-act="edit" class="btn btn-sm btn-ghost">Editar</button>
          <button data-pid="${p.id}" data-act="del" class="btn btn-sm btn-danger">Eliminar</button>
        </div>
      </div>`).join("");
    ctn.querySelectorAll("[data-pid]").forEach((b) => b.addEventListener("click", () => patientAction(b)));
  } catch (err) { ctn.innerHTML = `<div class="empty-state"><p class="small" style="color:var(--danger)">${esc(err.message)}</p></div>`; }
}

function openPatientForm(patient = null) {
  openModal(patient ? "Editar paciente" : "Nuevo paciente", `
    <div class="field"><label class="label">Nombre completo</label><input id="pName" class="input" value="${patient ? esc(patient.full_name) : ""}" /></div>
    <div class="field"><label class="label">Correo</label><input id="pEmail" type="email" class="input" value="${patient ? esc(patient.email) : ""}" /></div>
    <div class="field"><label class="label">Teléfono</label><input id="pPhone" class="input" value="${patient ? esc(patient.phone || "") : ""}" /></div>
    <div class="field"><label class="label">${patient ? "Nueva contraseña (opcional)" : "Contraseña (mín. 8)"}</label><input id="pPass" type="password" class="input" /></div>
  `, async () => {
    const body = {
      full_name: fRead("pName"), email: fRead("pEmail"),
      phone: fRead("pPhone") || null,
      password: fRead("pPass") || (patient ? undefined : null),
    };
    if (!body.full_name || !body.email) { toast("Nombre y correo son requeridos."); return; }
    if (!patient && !body.password) { toast("La contraseña es requerida."); return; }
    if (patient) await api(`/admin/patients/${patient.id}`, { method: "PATCH", body });
    else await api("/admin/patients", { method: "POST", body });
    closeModal(); loadPatients($("#patientSearch").value); toast(patient ? "Paciente actualizado" : "Paciente creado");
  });
}

// Ficha clínica
function openFicha(p) {
  api(`/admin/patients/${p.id}/ficha`).then((ficha) => ficha || {}).catch(() => ({})).then((ficha) => {
    ficha = ficha || {};
    const v = (k, fb="") => (ficha[k] !== null && ficha[k] !== undefined ? ficha[k] : fb);
    const cb = (k) => !!ficha[k];
    const today = () => new Date().toISOString().slice(0,10);
    const label = (t) => `<label class="label">${t}</label>`;
    const inField = (id, ph="") => `<input id="${id}" class="input" value="${esc(v(id.replace(/^f/,"").replace(/([A-Z])/g,"_$1").toLowerCase(),""))}" placeholder="${ph}" />`;
    // use explicit mappings for reliability
    const val = (k) => esc(v(k,""));
    const chk = (id, text) => `<label class="check-row"><input type="checkbox" id="${id}" ${cb(id.replace(/^f/,"").replace(/([A-Z])/g,"_$1").toLowerCase())?"checked":""}/> ${text}</label>`;
    // direct mapping
    const F = (key) => esc(v(key, ""));
    const B = (key) => cb(key) ? "checked" : "";

    const html = `
    <div style="display:grid;gap:14px;">
      <div><h4 class="section-title">1. Datos personales</h4>
        <div class="grid-2">
          <div class="field" style="grid-column:1/-1">${label("Nombre completo")}<input id="fName" class="input" value="${esc(p.full_name)}"/></div>
          <div class="field">${label("Contacto (teléfono)")}<input id="fPhone" class="input" value="${esc(p.phone||"")}"/></div>
          <div class="field">${label("Fecha de nacimiento")}<input id="fBirth" type="date" class="input" value="${p.birth_date?String(p.birth_date).slice(0,10):""}"/></div>
          <div class="field" style="grid-column:1/-1">${label("Dirección")}<input id="fAddress" class="input" value="${esc(p.address||"")}"/></div>
          <div class="field">${label("Ocupación")}<input id="fOccupation" class="input" value="${esc(p.occupation||"")}"/></div>
          <div class="field">${label("Peso (kg)")}<input id="fWeight" type="number" step="0.1" class="input" value="${F("weight_kg")}"/></div>
          <div class="field">${label("Estatura (cm)")}<input id="fHeight" type="number" step="0.1" class="input" value="${F("height_cm")}"/></div>
          <div class="field"><label class="label">IMC</label><div id="fImc" class="input" style="display:flex;align-items:center;color:var(--muted);"></div></div>
        </div>
      </div>
      <div class="divider"></div>
      <div><h4 class="section-title">2. Historia clínica y evaluación</h4>
        <div class="field">${label("Razón de consulta")}<textarea id="fReason" class="input">${F("reason_for_consultation")}</textarea></div>
        <div class="field">${label("Objetivo del tratamiento")}<textarea id="fObjective" class="input">${F("treatment_objective")}</textarea></div>
        <p class="small muted font-semibold" style="margin:8px 0;">Historia médica</p>
        <div class="grid-2">
          <label class="check-row"><input type="checkbox" id="fSurgeries" ${B("surgeries")}/> Cirugías</label>
          <div class="field"><input id="fSurgeriesDate" type="date" class="input" value="${ficha.surgeries_date?String(ficha.surgeries_date).slice(0,10):""}"/></div>
          <div class="field" style="grid-column:1/-1"><input id="fSurgeriesDetail" class="input" placeholder="¿Cuál cirugía?" value="${F("surgeries_detail")}"/></div>
          <label class="check-row"><input type="checkbox" id="fCesarean" ${B("cesarean")}/> Cesárea</label>
          <div class="field"><input id="fCesareanDate" type="date" class="input" value="${ficha.cesarean_date?String(ficha.cesarean_date).slice(0,10):""}"/></div>
          <div class="field" style="grid-column:1/-1"><input id="fCesareanDetail" class="input" placeholder="Detalle cesárea" value="${F("cesarean_detail")}"/></div>
          <label class="check-row"><input type="checkbox" id="fPregnancy" ${B("pregnancy")}/> Embarazo actual</label>
          <label class="check-row"><input type="checkbox" id="fLactation" ${B("lactation")}/> Lactancia</label>
          <label class="check-row"><input type="checkbox" id="fMenstruation" ${B("menstruation")}/> Menstruación</label>
          <label class="check-row"><input type="checkbox" id="fMenopause" ${B("menopause")}/> Menopausia</label>
        </div>
        <div class="field mt-2">${label("DIU")}<input id="fDiu" class="input" value="${F("diu")}"/></div>
        <p class="small muted font-semibold" style="margin:8px 0;">Enfermedades crónicas</p>
        <div class="grid-2">
          <label class="check-row"><input type="checkbox" id="fDia" ${B("chronic_diabetes")}/> Diabetes</label>
          <label class="check-row"><input type="checkbox" id="fHyp" ${B("chronic_hypertension")}/> Hipertensión</label>
          <label class="check-row"><input type="checkbox" id="fThy" ${B("chronic_thyroid")}/> Tiroides</label>
          <label class="check-row"><input type="checkbox" id="fHrt" ${B("chronic_heart")}/> Corazón</label>
        </div>
        <div class="field mt-2">${label("Otras enfermedades")}<input id="fOtherCond" class="input" value="${F("chronic_other")}"/></div>
        <div class="field">${label("Medicamentos actuales")}<textarea id="fMeds" class="input">${F("current_medications")}</textarea></div>
      </div>
      <div class="divider"></div>
      <div><h4 class="section-title">3. Evaluación de áreas</h4>
        <div class="field">${label("Siluetas corporales (frente / espalda)")}<textarea id="fSilhouette" class="input">${F("silhouette_notes")}</textarea></div>
        <div class="grid-2">
          <label class="check-row"><input type="checkbox" id="fFat" ${B("areas_fat")}/> Grasa localizada</label>
          <label class="check-row"><input type="checkbox" id="fCell" ${B("areas_cellulite")}/> Celulitis</label>
          <label class="check-row"><input type="checkbox" id="fRet" ${B("areas_retention")}/> Retención de líquidos</label>
        </div>
        <div class="field mt-2">${label("Otra área de molestia")}<input id="fOtherArea" class="input" value="${F("areas_other")}"/></div>
        <div class="grid-2 mt-2">
          <div class="field">${label("Abdomen (cm)")}<input id="fAbdomen" type="number" step="0.1" class="input" value="${F("abdomen_cm")}"/></div>
          <div class="field">${label("Cintura (cm)")}<input id="fWaist" type="number" step="0.1" class="input" value="${F("waist_cm")}"/></div>
          <div class="field">${label("Cadera (cm)")}<input id="fHip" type="number" step="0.1" class="input" value="${F("hip_cm")}"/></div>
          <div class="field">${label("Pierna derecha (cm)")}<input id="fLegR" type="number" step="0.1" class="input" value="${F("right_leg_cm")}"/></div>
          <div class="field">${label("Pierna izquierda (cm)")}<input id="fLegL" type="number" step="0.1" class="input" value="${F("left_leg_cm")}"/></div>
        </div>
      </div>
      <div class="divider"></div>
      <div><h4 class="section-title">Control de sesiones</h4>
        <div class="grid-2">
          <div class="field">${label("Sesiones recomendadas")}<input id="fSessionsRec" type="number" min="0" max="100" class="input" value="${v("sessions_recommended",0)}"/></div>
          <div class="field">${label("Sesiones completadas")}<input id="fSessionsDone" type="number" min="0" max="100" class="input" value="${v("sessions_completed",0)}"/></div>
        </div>
        <div id="sessionChecks" class="flex gap-2" style="flex-wrap:wrap;margin-top:8px;"></div>
      </div>
      <div class="divider"></div>
      <div><h4 class="section-title">5. Consentimiento y notas</h4>
        <div class="field">${label("Notas de progreso y recomendaciones")}<textarea id="fProgress" class="input">${F("progress_notes")}</textarea></div>
        <div class="list-card small muted" style="margin:10px 0;">Yo, el/la paciente, declaro que la información proporcionada es verdadera, completa y actualizada. Autorizo la realización del tratamiento de masaje descrito, habiendo sido informado/a sobre el procedimiento, beneficios, riesgos y posibles contraindicaciones.</div>
        <label class="check-row"><input type="checkbox" id="fConsent" ${B("consent_given")}/> Consentimiento informado</label>
        <div class="grid-2 mt-2">
          <div class="field" style="grid-column:1/-1">${label("Firma del paciente")}<input id="fSignature" class="input" value="${F("consent_signature")}"/></div>
          <div class="field">${label("Fecha")}<input id="fConsentDate" type="date" class="input" value="${ficha.consent_date?String(ficha.consent_date).slice(0,10):today()}"/></div>
        </div>
      </div>
    </div>`;

    openModal(`Ficha clínica · ${p.full_name}`, html, async () => {
      if (!fHasData()) { toast("No hay datos para guardar."); return; }
      await api(`/admin/patients/${p.id}`, { method: "PATCH", body: {
        full_name: fRead("fName") || p.full_name, phone: fRead("fPhone") || null,
        birth_date: fRead("fBirth") || null, address: fRead("fAddress") || null, occupation: fRead("fOccupation") || null,
      }});
      await api(`/admin/patients/${p.id}/ficha`, { method: "PUT", body: {
        reason_for_consultation: fRead("fReason") || null, treatment_objective: fRead("fObjective") || null,
        surgeries: fChecked("fSurgeries"), surgeries_detail: fRead("fSurgeriesDetail") || null, surgeries_date: fRead("fSurgeriesDate") || null,
        cesarean: fChecked("fCesarean"), cesarean_detail: fRead("fCesareanDetail") || null, cesarean_date: fRead("fCesareanDate") || null,
        pregnancy: fChecked("fPregnancy"), lactation: fChecked("fLactation"), menstruation: fChecked("fMenstruation"), diu: fRead("fDiu") || null, menopause: fChecked("fMenopause"),
        chronic_diabetes: fChecked("fDia"), chronic_hypertension: fChecked("fHyp"), chronic_thyroid: fChecked("fThy"), chronic_heart: fChecked("fHrt"), chronic_other: fRead("fOtherCond") || null,
        current_medications: fRead("fMeds") || null,
        weight_kg: fNum("fWeight"), height_cm: fNum("fHeight"), waist_cm: fNum("fWaist"), hip_cm: fNum("fHip"), abdomen_cm: fNum("fAbdomen"), right_leg_cm: fNum("fLegR"), left_leg_cm: fNum("fLegL"),
        areas_fat: fChecked("fFat"), areas_cellulite: fChecked("fCell"), areas_retention: fChecked("fRet"), areas_other: fRead("fOtherArea") || null, silhouette_notes: fRead("fSilhouette") || null,
        sessions_recommended: fNum("fSessionsRec") || 0, sessions_completed: fNum("fSessionsDone") || 0,
        progress_notes: fRead("fProgress") || null, consent_given: fChecked("fConsent"), consent_signature: fRead("fSignature") || null, consent_date: fRead("fConsentDate") || null,
      }});
      closeModal(); loadPatients($("#patientSearch").value); toast("Ficha clínica guardada");
    }, true);

    const calcImc = () => {
      const w = Number($("#fWeight")?.value), h = Number($("#fHeight")?.value), el = $("#fImc");
      if (el) el.textContent = w > 0 && h > 0 ? (w / Math.pow(h/100,2)).toFixed(1) : "—";
    };
    $("#fWeight")?.addEventListener("input", calcImc); $("#fHeight")?.addEventListener("input", calcImc); calcImc();
    const doneEl = $("#fSessionsDone"), checksEl = $("#sessionChecks");
    if (doneEl && checksEl) {
      const renderChecks = () => {
        const done = Math.min(Math.max(Number(doneEl.value)||0,0),10);
        checksEl.innerHTML = Array.from({length:10},(_,i)=>`<span class="badge ${i<done?"badge-approved":"badge-pending"}" style="${i<done?"":"opacity:.45"}">${i+1}</span>`).join("");
      };
      doneEl.addEventListener("input", renderChecks); renderChecks();
    }
  });
}

// Evolución
function openRecords(pid, name) {
  api(`/admin/patients/${pid}/records`).then((records) => {
    const fecha = (iso) => { if (!iso) return "—"; const [y,m,d]=String(iso).slice(0,10).split("-"); return y&&m&&d?`${d}/${m}/${y}`:String(iso).slice(0,10); };
    const cell = (label, value) => `<div class="detail-cell"><div class="detail-lbl">${label}</div><div class="detail-val">${value ?? "—"}</div></div>`;
    const rows = records.map((r) => {
      const imc = r.weight_kg && r.height_cm ? (r.weight_kg / Math.pow(r.height_cm/100,2)).toFixed(1) : null;
      return `<div class="list-card">
        <div class="list-row"><p class="list-title">${fecha(r.measurements_date)}</p>${r.session_type?`<span class="badge badge-approved">${esc(r.session_type)}</span>`:""}</div>
        <div class="detail-grid mt-3">
          ${cell("Peso", r.weight_kg? r.weight_kg+" kg":null)}
          ${cell("Estatura", r.height_cm? r.height_cm+" cm":null)}
          ${cell("IMC", imc)}
          ${cell("Cintura", r.waist_cm? r.waist_cm+" cm":null)}
          ${cell("Cadera", r.hip_cm? r.hip_cm+" cm":null)}
          ${cell("Abdomen", r.abdomen_cm? r.abdomen_cm+" cm":null)}
          ${cell("Pierna der.", r.right_leg_cm? r.right_leg_cm+" cm":null)}
          ${cell("Pierna izq.", r.left_leg_cm? r.left_leg_cm+" cm":null)}
          ${cell("Duración", r.duration_minutes? r.duration_minutes+" min":null)}
        </div>
        ${r.techniques?`<p class="small muted mt-2"><b style="color:var(--text)">Técnicas:</b> ${esc(r.techniques)}</p>`:""}
        ${r.oils_lotions?`<p class="small muted"><b style="color:var(--text)">Aceites/lociones:</b> ${esc(r.oils_lotions)}</p>`:""}
        ${r.contraindications?`<p class="small muted"><b style="color:var(--text)">Contraindicaciones:</b> ${esc(r.contraindications)}</p>`:""}
        ${r.clinical_notes?`<p class="small muted" style="font-style:italic;margin-top:6px;">${esc(r.clinical_notes)}</p>`:""}
      </div>`;
    }).join("") || '<div class="empty-state"><p class="small">Sin registros.</p></div>';

    openModal(`Evolución · ${name}`, `
      <div style="display:grid;gap:10px;max-height:35vh;overflow:auto;margin-bottom:14px;">${rows}</div>
      <div class="divider"></div>
      <h4 class="section-title">Nueva medición</h4>
      <div class="field"><label class="label">Tipo de sesión</label><select id="recType" class="input"><option value="">Seleccionar…</option><option>Reductivo</option><option>LipoLaser</option><option>Moldeador</option><option>Relajante</option></select></div>
      <div class="grid-2">
        <div class="field"><label class="label">Peso (kg)</label><input id="recWeight" type="number" step="0.1" class="input"/></div>
        <div class="field"><label class="label">Estatura (cm)</label><input id="recHeight" type="number" step="0.1" class="input"/></div>
      </div>
      <div class="small muted mb-0">IMC: <b id="recImc" style="color:var(--text)">—</b></div>
      <div class="grid-2 mt-2">
        <div class="field"><label class="label">Abdomen (cm)</label><input id="recAbdomen" type="number" step="0.1" class="input"/></div>
        <div class="field"><label class="label">Cintura (cm)</label><input id="recWaist" type="number" step="0.1" class="input"/></div>
        <div class="field"><label class="label">Cadera (cm)</label><input id="recHip" type="number" step="0.1" class="input"/></div>
        <div class="field"><label class="label">Pierna der. (cm)</label><input id="recLegR" type="number" step="0.1" class="input"/></div>
        <div class="field"><label class="label">Pierna izq. (cm)</label><input id="recLegL" type="number" step="0.1" class="input"/></div>
        <div class="field"><label class="label">Duración (min)</label><input id="recDur" type="number" class="input"/></div>
      </div>
      <div class="field"><label class="label">Técnicas utilizadas</label><input id="recTech" class="input"/></div>
      <div class="field"><label class="label">Aceites / lociones</label><input id="recOils" class="input"/></div>
      <div class="field"><label class="label">Contraindicaciones detectadas</label><input id="recContra" class="input"/></div>
      <div class="field"><label class="label">Notas clínicas</label><textarea id="recNotes" class="input"></textarea></div>
    `, async () => {
      if (!fHasData()) { toast("Escribe datos en la nueva medición."); return; }
      await api(`/admin/patients/${pid}/records`, { method: "POST", body: {
        weight_kg: fNum("recWeight"), height_cm: fNum("recHeight"), waist_cm: fNum("recWaist"), hip_cm: fNum("recHip"),
        abdomen_cm: fNum("recAbdomen"), right_leg_cm: fNum("recLegR"), left_leg_cm: fNum("recLegL"), duration_minutes: fNum("recDur"),
        session_type: fRead("recType") || null, techniques: fRead("recTech") || null, oils_lotions: fRead("recOils") || null,
        contraindications: fRead("recContra") || null, clinical_notes: fRead("recNotes") || null,
      }});
      closeModal(); openRecords(pid, name); toast("Medición guardada");
    }, true);

    const calcRecImc = () => { const w=Number($("#recWeight")?.value), h=Number($("#recHeight")?.value), el=$("#recImc"); if(el) el.textContent = w>0&&h>0 ? (w/Math.pow(h/100,2)).toFixed(1) : "—"; };
    $("#recWeight")?.addEventListener("input", calcRecImc); $("#recHeight")?.addEventListener("input", calcRecImc);
  }).catch((err) => toast(err.message));
}

async function patientAction(btn) {
  const pid = Number(btn.dataset.pid); const act = btn.dataset.act;
  try {
    if (act === "ficha" || act === "records" || act === "edit") {
      const p = await api(`/admin/patients/${pid}`);
      if (act === "ficha") openFicha(p);
      else if (act === "records") openRecords(pid, p.full_name);
      else openPatientForm(p);
    } else if (act === "del") {
      if (!confirm("¿Eliminar este paciente y todos sus datos?")) return;
      await api(`/admin/patients/${pid}`, { method: "DELETE" });
      loadPatients($("#patientSearch").value); toast("Paciente eliminado");
    }
  } catch (err) { toast(err.message); }
}

// Reportes
async function loadReports() {
  const period = $("#reportPeriod")?.value || "daily";
  const dateRef = $("#reportDate")?.value || new Date().toISOString().slice(0,10);
  const summary = $("#reportSummary");
  const days = $("#reportDays");
  const range = $("#reportRange");
  summary.innerHTML = '<div class="empty-state"><p class="small muted">Cargando reporte…</p></div>';
  days.innerHTML = "";
  try {
    const r = await api(`/admin/reports?period=${encodeURIComponent(period)}&date_ref=${encodeURIComponent(dateRef)}`);
    range.textContent = `${r.start_date} a ${r.end_date}`;
    const cards = [
      ["Citas totales", r.summary.total_appointments],
      ["Completadas", r.summary.completed_appointments],
      ["Pend./Aprob.", r.summary.pending_appointments + r.summary.approved_appointments],
      ["Canceladas", r.summary.cancelled_appointments],
      ["Ingreso completado", fmtCurrency(r.summary.completed_revenue)],
      ["Ingreso esperado", fmtCurrency(r.summary.expected_revenue)],
    ];
    summary.innerHTML = cards.map(([l,v]) => `<div class="detail-cell"><div class="detail-lbl">${esc(l)}</div><div class="detail-val" style="font-size:1.1rem;">${esc(String(v))}</div></div>`).join("");
    if (!r.days.length) { days.innerHTML = '<div class="empty-state"><p class="small muted">Sin datos en el periodo.</p></div>'; return; }
    days.innerHTML = r.days.map((d) => `
      <div class="list-card" style="margin-bottom:10px;">
        <div class="list-row">
          <div>
            <p class="list-title">${esc(d.date)}</p>
            <p class="list-meta">${d.total_appointments} citas · ${d.completed_appointments} completadas · ${d.cancelled_appointments} canceladas</p>
          </div>
          <div style="text-align:right;">
            <div style="font-weight:700;color:var(--brand);">${fmtCurrency(d.completed_revenue)}</div>
            <div class="small muted">Esperado ${fmtCurrency(d.expected_revenue)}</div>
          </div>
        </div>
      </div>`).join("");
  } catch (err) {
    summary.innerHTML = "";
    days.innerHTML = `<div class="empty-state"><p class="small" style="color:var(--danger)">${esc(err.message)}</p></div>`;
  }
}

// Agenda / horarios
const WEEK_DAYS = [["0","Lun"],["1","Mar"],["2","Mié"],["3","Jue"],["4","Vie"],["5","Sáb"],["6","Dom"]];
function renderAgendaDays(selected = [0,1,2,3,4,5]) {
  const ctn = $("#agendaDays"); if (!ctn) return;
  const set = new Set(selected.map(String));
  ctn.innerHTML = WEEK_DAYS.map(([v,l]) => `<label class="check-row" style="margin:0;"><input type="checkbox" class="agenda-day" value="${v}" ${set.has(v)?"checked":""}/> ${l}</label>`).join("");
}
async function loadAgendaSettings() {
  try {
    const a = await api("/admin/agenda");
    $("#agendaStart").value = a.start_time || "09:00";
    $("#agendaEnd").value = a.end_time || "20:00";
    $("#agendaStep").value = a.step_minutes || 30;
    $("#agendaLunchStart").value = a.lunch_start || "";
    $("#agendaLunchEnd").value = a.lunch_end || "";
    renderAgendaDays(a.working_days || [0,1,2,3,4,5]);
  } catch (err) { toast(err.message); }
}
async function saveAgendaSettings() {
  const days = [...document.querySelectorAll(".agenda-day:checked")].map((e) => Number(e.value));
  const body = {
    start_time: $("#agendaStart").value,
    end_time: $("#agendaEnd").value,
    step_minutes: Number($("#agendaStep").value || 30),
    lunch_start: $("#agendaLunchStart").value || null,
    lunch_end: $("#agendaLunchEnd").value || null,
    working_days: days,
  };
  try {
    await api("/admin/agenda", { method: "PUT", body });
    toast("Horarios guardados");
  } catch (err) { toast(err.message); }
}

// Servicios
async function loadServices() {
  const ctn = $("#serviceGrid");
  try {
    const services = await api("/admin/services");
    if (!services.length) { ctn.innerHTML = '<div class="empty-state" style="grid-column:1/-1;"><div class="empty-icon">✦</div><p class="empty-title">Sin servicios</p></div>'; return; }
    ctn.innerHTML = services.map((s) => `
      <div class="list-card" style="${s.is_active ? "" : "opacity:.55"}">
        <div class="list-row">
          <p class="list-title">${esc(s.name)}</p>
          ${s.is_active ? '<span class="badge badge-approved">Activo</span>' : '<span class="badge badge-cancelled">Inactivo</span>'}
        </div>
        <p class="list-meta">${esc(s.description || "")}</p>
        <p class="small mt-2" style="color:var(--brand);font-weight:700;">${fmtCurrency(s.price)} · ${s.duration_minutes} min</p>
        <div class="list-actions">
          <button data-sid="${s.id}" data-act="edit" class="btn btn-sm btn-ghost">Editar</button>
          <button data-sid="${s.id}" data-act="del" class="btn btn-sm btn-danger">Eliminar</button>
        </div>
      </div>`).join("");
    ctn.querySelectorAll("[data-sid]").forEach((b) => b.addEventListener("click", () => serviceAction(b)));
  } catch (err) { ctn.innerHTML = `<div class="empty-state" style="grid-column:1/-1;"><p class="small" style="color:var(--danger)">${esc(err.message)}</p></div>`; }
}

function openServiceForm(service = null) {
  openModal(service ? "Editar servicio" : "Nuevo servicio", `
    <div class="field"><label class="label">Nombre</label><input id="sName" class="input" value="${service ? esc(service.name) : ""}"/></div>
    <div class="field"><label class="label">Descripción</label><textarea id="sDesc" class="input">${service ? esc(service.description || "") : ""}</textarea></div>
    <div class="grid-2">
      <div class="field"><label class="label">Precio</label><input id="sPrice" type="number" step="0.01" class="input" value="${service ? service.price : ""}"/></div>
      <div class="field"><label class="label">Duración (min)</label><input id="sDur" type="number" class="input" value="${service ? service.duration_minutes : 60}"/></div>
    </div>
    <label class="check-row"><input type="checkbox" id="sActive" ${!service || service.is_active ? "checked" : ""}/> Activo</label>
  `, async () => {
    const body = { name: fRead("sName"), description: fRead("sDesc") || null, price: Number(fRead("sPrice")), duration_minutes: Number(fRead("sDur")), is_active: fChecked("sActive") };
    if (!body.name) { toast("El nombre es requerido."); return; }
    if (service) await api(`/admin/services/${service.id}`, { method: "PATCH", body });
    else await api("/admin/services", { method: "POST", body });
    closeModal(); loadServices(); toast(service ? "Servicio actualizado" : "Servicio creado");
  });
}

async function serviceAction(btn) {
  const sid = btn.dataset.sid; const act = btn.dataset.act;
  try {
    if (act === "edit") {
      const s = (await api("/admin/services")).find((x) => x.id === Number(sid));
      openServiceForm(s);
    } else if (act === "del") {
      if (!confirm("¿Eliminar este servicio?")) return;
      await api(`/admin/services/${sid}`, { method: "DELETE" });
      loadServices(); toast("Servicio eliminado");
    }
  } catch (err) { toast(err.message); }
}

// Notificaciones admin
async function loadAdminNotifCount() {
  try {
    const { count } = await api("/notifications/unread-count");
    ["#adminNotifBadge", "#adminNotifBadgeM"].forEach((sel) => {
      const b = $(sel); if (!b) return;
      b.textContent = count > 99 ? "99+" : count;
      b.classList.toggle("hidden", count <= 0);
    });
  } catch {}
}

async function loadAdminNotifications() {
  const list = $("#adminNotifList");
  try {
    const notes = await api("/notifications");
    if (!notes.length) { list.innerHTML = '<div class="empty-state" style="padding:20px;"><p class="small">No hay notificaciones.</p></div>'; return; }
    list.innerHTML = notes.map((n) => `
      <div class="notif-item ${n.is_read ? "" : "unread"}" data-nid="${n.id}">
        <p class="notif-title">${esc(n.title)}</p>
        <p class="notif-msg">${esc(n.message)}</p>
        <div class="notif-time">${dmy(n.created_at)}</div>
      </div>`).join("");
  } catch (err) { list.innerHTML = `<div class="empty-state" style="padding:20px;"><p class="small" style="color:var(--danger)">${esc(err.message)}</p></div>`; }
}

function toggleAdminNotifPanel() {
  const panel = $("#adminNotifPanel");
  const opening = panel.classList.contains("hidden");
  panel.classList.toggle("hidden");
  if (opening) loadAdminNotifications();
}
async function markAdminNotifRead(nid) { try { await api(`/notifications/${nid}/read`, { method: "PATCH" }); loadAdminNotifCount(); loadAdminNotifications(); } catch {} }
async function markAllAdminNotifsRead() { try { await api("/notifications/read-all", { method: "PATCH" }); loadAdminNotifCount(); loadAdminNotifications(); } catch(e){ toast(e.message); } }
async function clearAllAdminNotifs() {
  if (!confirm("¿Eliminar todas las notificaciones?")) return;
  try { await api("/notifications", { method: "DELETE" }); loadAdminNotifCount(); loadAdminNotifications(); toast("Notificaciones limpiadas"); } catch(e){ toast(e.message); }
}

document.addEventListener("click", (e) => {
  const panel = $("#adminNotifPanel");
  if (!panel || panel.classList.contains("hidden")) return;
  const inside = e.target.closest("#adminNotifPanel") || e.target.closest("#adminNotifBtn") || e.target.closest("#adminNotifBtnM");
  if (!inside) panel.classList.add("hidden");
});

function logout() { sessionStorage.removeItem(TOKEN_KEY); sessionStorage.removeItem("kerem_user"); location.href = "/"; }
function debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }

// Init
function registerSW() { if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {}); }

document.addEventListener("DOMContentLoaded", () => {
  if (!requireAuth()) return;
  registerSW();
  setOfflineUI();
  window.addEventListener("online", setOfflineUI);
  window.addEventListener("offline", setOfflineUI);

  $$(".nav-btn[data-tab]").forEach((b) => b.addEventListener("click", () => {
    const tab = b.dataset.tab; showPanel(tab);
    if (tab === "citas") loadAppointments($("#filterStatus")?.value || "");
    else if (tab === "pacientes") loadPatients($("#patientSearch")?.value || "");
    else if (tab === "reportes") loadReports();
    else if (tab === "servicios") { loadAgendaSettings(); loadServices(); }
  }));
  $("#adminLogout")?.addEventListener("click", logout);
  $("#adminLogoutM")?.addEventListener("click", logout);
  $("#filterStatus").addEventListener("change", (e) => loadAppointments(e.target.value));
  $("#newPatientBtn").addEventListener("click", () => openPatientForm());
  $("#newServiceBtn").addEventListener("click", () => openServiceForm());
  $("#saveAgendaBtn")?.addEventListener("click", saveAgendaSettings);
  renderAgendaDays();
  $("#patientSearch").addEventListener("input", debounce((e) => loadPatients(e.target.value), 300));
  $("#btnLoadReport")?.addEventListener("click", loadReports);
  const rd = $("#reportDate"); if (rd && !rd.value) rd.value = new Date().toISOString().slice(0,10);
  $("#modalCancel").addEventListener("click", closeModal);
  $("#modalCloseX")?.addEventListener("click", closeModal);
  $("#modal").addEventListener("click", (e) => { if (e.target.id === "modal") closeModal(); });
  $("#modalOk").addEventListener("click", async () => {
    if (!modalOkHandler) return;
    const okBtn = $("#modalOk");
    okBtn.disabled = true;
    try { await modalOkHandler(); }
    catch (err) { console.error(err); toast("Error: " + (err?.message || err)); }
    finally { okBtn.disabled = false; }
  });
  document.addEventListener("input", (e) => trackModalInput(e.target));
  document.addEventListener("change", (e) => trackModalInput(e.target));

  $("#adminNotifBtn")?.addEventListener("click", toggleAdminNotifPanel);
  $("#adminNotifBtnM")?.addEventListener("click", toggleAdminNotifPanel);
  $("#adminNotifReadAll")?.addEventListener("click", markAllAdminNotifsRead);
  $("#adminNotifClearAll")?.addEventListener("click", clearAllAdminNotifs);
  $("#adminNotifList")?.addEventListener("click", (e) => { const row = e.target.closest("[data-nid]"); if (row) markAdminNotifRead(row.dataset.nid); });

  showPanel("citas");
  loadAppointments();
  loadPatients();
  loadServices();
  loadAdminNotifCount();
  setVersionBadge();
});
