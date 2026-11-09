// INHA SEAT MANAGER 화면 스크립트 (외부 라이브러리 없음)
"use strict";

const IS_DEMO = document.body.dataset.demo === "1";
const STATUS_ICON = { available: "○", occupied: "●", away: "◐", disabled: "✕" };
const KIND_LABEL = { query: "조회", query_error: "조회 실패", monitor: "모니터링", watch: "희망 좌석", assign: "배정" };
const state = { rooms: [], roomId: null, lastNoteId: null, sys: null, selectedSeat: null, online: true };

const $ = (sel) => document.querySelector(sel);
function el(tag, attrs = {}, ...children) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") e.className = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v);
  }
  for (const c of children) if (c != null) e.append(c instanceof Node ? c : document.createTextNode(String(c)));
  return e;
}
const fmtTime = (iso) => { if (!iso) return "-"; const d = new Date(iso); return isNaN(d) ? iso : d.toLocaleString("ko-KR"); };
function store(key, val) { try { if (val === undefined) return localStorage.getItem(key); localStorage.setItem(key, val); } catch { return null; } }

let toastTimer;
function toast(msg, isErr = false) {
  const t = $("#toast");
  t.textContent = msg; t.className = "toast" + (isErr ? " err" : ""); t.hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => (t.hidden = true), 3500);
}

async function api(path, opts = {}) {
  const init = { method: opts.method || "GET", headers: {} };
  if (opts.body !== undefined) { init.headers["Content-Type"] = "application/json"; init.body = JSON.stringify(opts.body); }
  let res;
  try { res = await fetch("/api" + path, init); }
  catch (e) { setConn(false, "서버에 연결할 수 없습니다"); throw new Error("서버에 연결할 수 없습니다. 프로그램이 실행 중인지 확인하세요."); }
  let data = null;
  try { data = await res.json(); } catch { /* 빈 응답 */ }
  if (!res.ok) {
    let msg = data && data.detail ? data.detail : `오류 (${res.status})`;
    if (Array.isArray(msg)) msg = "입력값이 올바르지 않습니다.";
    throw new Error(msg);
  }
  return data;
}

function setConn(ok, text) {
  state.online = ok;
  const c = $("#conn"); c.className = "conn " + (ok ? "ok" : "err");
  c.querySelector(".txt").textContent = text;
}

// ---------- 탭 ----------
function showTab(name) {
  document.querySelectorAll(".tabs button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === name)));
  document.querySelectorAll(".panel").forEach((p) => (p.hidden = p.id !== "tab-" + name));
  store("tab", name);
  if (name === "seats") loadSeats();
  if (name === "watches") loadWatches();
  if (name === "notifications") loadNotes();
  if (name === "history") loadHistory();
  if (name === "settings") renderSettings();
}
document.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => showTab(b.dataset.tab)));
document.querySelectorAll("[data-goto]").forEach((b) => b.addEventListener("click", () => showTab(b.dataset.goto)));
const currentTab = () => (document.querySelector('.tabs button[aria-selected="true"]') || {}).dataset?.tab;

// ---------- 시스템 상태 ----------
async function refreshSystem() {
  try {
    const s = await api("/system");
    state.sys = s;
    if (!s.provider_ok) setConn(false, "좌석 정보 조회 불가");
    else if (s.monitor.consecutive_failures > 0) setConn(false, `조회 실패 ${s.monitor.consecutive_failures}회`);
    else setConn(true, s.monitor.running ? "모니터링 중" : "연결됨");
    renderDashboardMonitor();
    const u = $("#unread"); u.hidden = !s.unread; u.textContent = s.unread;
    if (currentTab() === "settings") renderSystem();
  } catch (e) { /* setConn 이미 처리 */ }
}

function renderDashboardMonitor() {
  const m = state.sys.monitor;
  $("#d-monitor").textContent = m.running ? "● 실행 중" : "○ 중지됨";
  let sub = `조회 간격 ${m.interval}초`;
  if (m.running && m.next_delay !== m.interval) sub += ` (실패로 ${m.next_delay}초로 늘어남)`;
  if (m.last_check_at) sub += ` · 마지막 확인 ${fmtTime(m.last_check_at)}`;
  if (!m.running && m.stopped_reason) sub += ` · ${m.stopped_reason}`;
  if (m.last_error) sub += ` · 오류: ${m.last_error}`;
  $("#d-monitor-sub").textContent = sub;
  $("#d-start").disabled = m.running; $("#d-stop").disabled = !m.running;
}

// ---------- 열람실 ----------
async function loadRooms() {
  const box = $("#room-list");
  try {
    const data = await api("/rooms");
    state.rooms = data.rooms;
    box.replaceChildren(...data.rooms.map((r) =>
      el("button", { class: "room-btn", onclick: () => { selectRoom(r.id); showTab("seats"); } },
        el("strong", {}, r.name), el("span", { class: "muted" }, `빈자리 ${r.available} / 전체 ${r.total_seats}`))));
    const sel = $("#room-select");
    sel.replaceChildren(...data.rooms.map((r) => el("option", { value: r.id }, r.name)));
    const saved = store("room");
    selectRoom(data.rooms.some((r) => r.id === saved) ? saved : data.rooms[0]?.id, false);
  } catch (e) {
    box.replaceChildren(el("p", { class: "empty" }, "열람실 정보를 불러오지 못했습니다: " + e.message));
  }
}
function selectRoom(id, load = true) {
  if (!id) return;
  state.roomId = id; $("#room-select").value = id; store("room", id);
  if (load) loadSeats();
}
$("#room-select").addEventListener("change", (e) => selectRoom(e.target.value));

// ---------- 좌석 배치도 ----------
async function loadSeats() {
  if (!state.roomId) return;
  const map = $("#seat-map");
  try {
    const data = await api(`/rooms/${encodeURIComponent(state.roomId)}/seats`);
    const room = data.room;
    const narrow = window.matchMedia("(max-width: 640px)").matches;
    map.style.gridTemplateColumns = `repeat(${room.cols}, minmax(${narrow ? 28 : 44}px, 1fr))`;
    const counts = { available: 0, occupied: 0, away: 0, disabled: 0 };
    const cells = data.seats.map((s) => {
      counts[s.status]++;
      const b = el("button", {
        class: `seat ${s.status}${s.watched ? " watched" : ""}`, role: "gridcell",
        "aria-label": `${s.label} ${s.status_label}${s.watched ? " 희망 좌석" : ""}`,
        style: `grid-row:${s.row + 1};grid-column:${s.col + 1}`,
        onclick: () => openSeat(room, s),
      }, el("span", { class: "ic", "aria-hidden": "true" }, STATUS_ICON[s.status]), el("span", {}, s.label.replace("번", "")),
         el("span", { class: "st" }, s.status_label));
      return b;
    });
    map.replaceChildren(...cells);
    $("#seat-summary").textContent = `${room.name} · 빈자리 ${counts.available} · 사용 중 ${counts.occupied} · 자리비움 ${counts.away} · 사용 불가 ${counts.disabled}`;
    $("#seat-fetched").textContent = "갱신 " + fmtTime(data.fetched_at);
  } catch (e) {
    map.replaceChildren(el("p", { class: "empty" }, "좌석 정보를 불러오지 못했습니다: " + e.message));
  }
}

function openSeat(room, seat) {
  state.selectedSeat = { room, seat };
  $("#sd-title").textContent = `${seat.label} 좌석${IS_DEMO ? " (DEMO)" : ""}`;
  $("#sd-status").textContent = `${STATUS_ICON[seat.status]} ${seat.status_label}`;
  $("#sd-status").className = "status-line " + seat.status;
  $("#sd-room").textContent = room.name;
  const w = $("#sd-watch"); w.disabled = seat.watched; w.textContent = seat.watched ? "★ 이미 희망 좌석입니다" : "★ 희망 좌석에 추가";
  const a = $("#sd-assign"); if (a) a.disabled = seat.status !== "available";
  $("#seat-dialog").showModal();
}
$("#seat-dialog").addEventListener("close", async () => {
  const action = $("#seat-dialog").returnValue; const sel = state.selectedSeat;
  $("#seat-dialog").returnValue = "";
  if (!sel) return;
  if (action === "watch") {
    try { await api("/watches", { method: "POST", body: { room_id: sel.room.id, seat_id: sel.seat.id } }); toast(`${sel.room.name} ${sel.seat.label}을(를) 희망 좌석에 추가했습니다.`); }
    catch (e) { toast(e.message, true); }
    loadSeats(); refreshWatchCount();
  } else if (action === "assign") {
    // 배정 직전 사용자 확인
    const ok = confirm(`[DEMO 시뮬레이션]\n열람실: ${sel.room.name}\n좌석: ${sel.seat.label}\n\n가상 데이터에서 이 좌석을 배정 처리합니다. 실제 학교 시스템에는 아무 요청도 보내지 않습니다. 진행할까요?`);
    if (!ok) return;
    try { await api("/assign", { method: "POST", body: { room_id: sel.room.id, seat_id: sel.seat.id, confirm: true } }); toast("DEMO 배정 완료 (가상)"); }
    catch (e) { toast(e.message, true); }
    loadSeats();
  }
});

// ---------- 희망 좌석 ----------
async function refreshWatchCount() {
  try { const d = await api("/watches"); $("#d-watches").textContent = `${d.watches.length}개`; return d.watches; } catch { return []; }
}
async function loadWatches() {
  const list = $("#watch-list");
  const watches = await refreshWatchCount();
  if (!watches.length) { list.replaceChildren(el("li", { class: "empty" }, "등록된 희망 좌석이 없습니다. 좌석 배치도에서 좌석을 눌러 추가하세요.")); return; }
  list.replaceChildren(...watches.map((w) => el("li", {},
    el("div", {}, el("div", {}, `${w.room_name} ${w.seat_label}`),
      el("div", { class: "time" }, `마지막 상태: ${w.last_status ? { available: "빈자리", occupied: "사용 중", away: "자리비움", disabled: "사용 불가" }[w.last_status] : "미확인"}${w.last_notified_at ? " · 마지막 알림 " + fmtTime(w.last_notified_at) : ""}`)),
    el("button", { class: "btn danger", onclick: async () => {
      if (!confirm(`${w.room_name} ${w.seat_label}을(를) 희망 좌석에서 삭제할까요?`)) return;
      try { await api(`/watches/${w.id}`, { method: "DELETE" }); toast("삭제했습니다."); } catch (e) { toast(e.message, true); }
      loadWatches();
    } }, "삭제"))));
}

// ---------- 모니터링 ----------
$("#d-start").addEventListener("click", async () => {
  try { await api("/monitor/start", { method: "POST" }); toast("모니터링을 시작했습니다."); } catch (e) { toast(e.message, true); }
  refreshSystem();
});
$("#d-stop").addEventListener("click", async () => {
  try { await api("/monitor/stop", { method: "POST" }); toast("모니터링을 중지했습니다."); } catch (e) { toast(e.message, true); }
  refreshSystem();
});
$("#d-check").addEventListener("click", async () => {
  try {
    const d = await api("/monitor/check", { method: "POST" });
    if (d.result.error) toast("조회 실패: " + d.result.error, true);
    else toast(`확인 완료 · 새 알림 ${d.result.notified.length}건`);
  } catch (e) { toast(e.message, true); }
  refreshSystem(); pollNotes();
});

// ---------- 알림 ----------
function noteItem(n) {
  return el("li", { class: (n.is_read ? "" : "unread ") + (n.kind === "system" ? "sys" : "") },
    el("div", { class: "msg" }, n.message), el("div", { class: "time" }, fmtTime(n.created_at)));
}
async function loadNotes() {
  try {
    const d = await api("/notifications?limit=200");
    $("#note-list").replaceChildren(...(d.notifications.length ? d.notifications.map(noteItem) : [el("li", { class: "empty" }, "알림이 없습니다.")]));
  } catch (e) { toast(e.message, true); }
}
$("#mark-read").addEventListener("click", async () => { try { await api("/notifications/read", { method: "POST" }); } catch (e) { toast(e.message, true); } loadNotes(); refreshSystem(); });

async function pollNotes() {
  try {
    if (state.lastNoteId === null) {
      const d = await api("/notifications?limit=5");
      state.lastNoteId = d.notifications[0]?.id || 0;
      renderRecent(d.notifications);
      return;
    }
    const d = await api(`/notifications?after_id=${state.lastNoteId}&limit=50`);
    if (!d.notifications.length) return;
    state.lastNoteId = d.notifications[0].id;
    for (const n of [...d.notifications].reverse()) announce(n);
    const r = await api("/notifications?limit=5"); renderRecent(r.notifications);
    if (currentTab() === "notifications") loadNotes();
    if (currentTab() === "seats") loadSeats();
    refreshSystem();
  } catch { /* 연결 표시로 처리 */ }
}
function renderRecent(notes) {
  $("#d-notes").replaceChildren(...(notes.length ? notes.map(noteItem) : [el("li", { class: "empty" }, "아직 알림이 없습니다.")]));
}
function announce(n) {
  toast(n.message.split("\n")[0], n.kind === "system");
  if (store("sound") === "1") beep();
  if ("Notification" in window && Notification.permission === "granted") {
    try {
      const notif = new Notification(n.kind === "system" ? "INHA SEAT MANAGER 알림" : "빈자리 발생!", { body: n.message, tag: "note-" + n.id });
      notif.onclick = () => { window.focus(); showTab("notifications"); };
    } catch { /* 일부 모바일 브라우저는 페이지 알림 미지원 */ }
  }
}
function beep() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const o = ctx.createOscillator(); const g = ctx.createGain();
    o.connect(g); g.connect(ctx.destination); o.frequency.value = 880; g.gain.value = 0.1;
    o.start(); o.stop(ctx.currentTime + 0.25);
  } catch { /* 무시 */ }
}

// ---------- 이력 ----------
async function loadHistory() {
  const kind = $("#history-kind").value;
  try {
    const d = await api("/history?limit=300" + (kind ? "&kind=" + encodeURIComponent(kind) : ""));
    $("#history-list").replaceChildren(...(d.history.length ? d.history.map((h) => el("li", {},
      el("div", {}, el("span", { class: "tag " + h.kind }, KIND_LABEL[h.kind] || h.kind), h.detail),
      el("div", { class: "time" }, fmtTime(h.created_at)))) : [el("li", { class: "empty" }, "기록이 없습니다.")]));
  } catch (e) { toast(e.message, true); }
}
$("#history-kind").addEventListener("change", loadHistory);

// ---------- 설정 ----------
function renderSettings() {
  if (state.sys) {
    $("#interval").value = state.sys.monitor.interval;
    $("#interval").min = state.sys.monitor.min_interval;
    $("#interval-help").textContent = `최소 ${state.sys.monitor.min_interval}초. 학교 시스템에 부담을 주지 않도록 너무 짧게 설정하지 마세요. 연속 ${state.sys.monitor.max_failures}회 실패하면 자동 중지됩니다.`;
  }
  $("#sound").checked = store("sound") === "1";
  renderPerm(); renderSystem();
}
function renderPerm() {
  const p = "Notification" in window ? Notification.permission : "unsupported";
  $("#perm-state").textContent = { granted: "허용됨", denied: "차단됨 (브라우저 설정에서 허용해 주세요)", default: "아직 허용하지 않음", unsupported: "이 브라우저는 지원하지 않음" }[p];
  $("#enable-notify").disabled = p !== "default";
}
function renderSystem() {
  const s = state.sys; if (!s) return;
  const rows = [
    ["데이터", s.is_demo ? "DEMO (모의 데이터)" : "공식 시스템"],
    ["좌석 조회", s.provider_ok ? "정상" : "불가 – " + s.provider_error],
    ["데이터베이스", s.db_ok ? "정상" : "오류"],
    ["자동 배정", s.is_demo ? "DEMO 시뮬레이션만" : (s.supports_assignment ? "지원" : "미지원 (허용 여부 미확인)")],
    ["모니터링", s.monitor.running ? "실행 중" : "중지됨"],
    ["총 조회 횟수", s.monitor.check_count],
    ["연속 실패", `${s.monitor.consecutive_failures} / ${s.monitor.max_failures}`],
    ["마지막 성공", fmtTime(s.monitor.last_success_at)],
    ["마지막 오류", s.monitor.last_error || "없음"],
    ["공식 페이지", s.official_url],
    ["서버 시각", fmtTime(s.server_time)],
    ["버전", s.version],
  ];
  $("#sys").replaceChildren(...rows.flatMap(([k, v]) => [el("dt", {}, k), el("dd", {}, v)]));
}
$("#save-interval").addEventListener("click", async () => {
  const v = parseInt($("#interval").value, 10);
  if (!Number.isFinite(v) || v < 1) { toast("숫자를 입력하세요.", true); return; }
  try {
    const d = await api("/monitor/interval", { method: "PUT", body: { seconds: v } });
    toast(d.interval !== d.requested ? `허용 범위에 맞춰 ${d.interval}초로 저장했습니다.` : `${d.interval}초로 저장했습니다.`);
  } catch (e) { toast(e.message, true); }
  await refreshSystem(); renderSettings();
});
$("#enable-notify").addEventListener("click", async () => {
  if (!("Notification" in window)) return;
  await Notification.requestPermission(); renderPerm();
});
$("#sound").addEventListener("change", (e) => store("sound", e.target.checked ? "1" : "0"));
const demoFail = $("#demo-fail");
if (demoFail) demoFail.addEventListener("click", async () => {
  try { await api("/demo/fail", { method: "POST", body: { count: 3 } }); toast("다음 조회 3회가 실패하도록 설정했습니다."); } catch (e) { toast(e.message, true); }
});

// ---------- 시작 ----------
(async function init() {
  await refreshSystem();
  await loadRooms();
  refreshWatchCount();
  pollNotes();
  const saved = store("tab");
  if (saved && document.getElementById("tab-" + saved)) showTab(saved);
  setInterval(refreshSystem, 5000);
  setInterval(pollNotes, 4000);
  setInterval(() => { if (currentTab() === "seats" && !document.hidden) loadSeats(); }, 10000);
  setInterval(() => { if (currentTab() === "dashboard" && !document.hidden) loadRooms(); }, 15000);
})();
