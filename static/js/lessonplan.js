// static/js/lessonplan.js
(function () {
  "use strict";

  let LIST = [];
  let CURRENT = null;
  let EDITING = false;

  const $ = (sel) => document.querySelector(sel);
  const byId = (id) => document.getElementById(id);

  function showToast(text, ok = true) {
    const n = byId("toast");
    if (!n) return;
    n.textContent = text;
    n.style.background = ok ? "#10b981" : "#ef4444";
    n.classList.add("show");
    setTimeout(() => n.classList.remove("show"), 2200);
  }

  function md(markdown) {
    try {
      if (window.marked && window.DOMPurify) {
        marked.setOptions({ gfm:true, breaks:true, headerIds:true, mangle:false });
        const raw = marked.parse(markdown || "");
        return DOMPurify.sanitize(raw);
      }
    } catch (e) {
      console.warn("[LessonPlan] Markdown render fallback:", e);
    }
    return "<pre style='white-space:pre-wrap'>" + (markdown || "") + "</pre>";
  }

  function q(key) {
    const url = new URL(window.location.href);
    return url.searchParams.get(key);
  }
  function readPlansDataFromScript() {
    const el = byId("plansData"); if (!el) return [];
    try { const raw = (el.textContent || "").trim(); if (!raw) return []; const data = JSON.parse(raw); return Array.isArray(data)?data:[]; }
    catch { return []; }
  }
  function loadListFromStorage() {
    try { return JSON.parse(localStorage.getItem("planList") || "[]"); } catch { return []; }
  }
  function saveListToStorage(list) {
    localStorage.setItem("planList", JSON.stringify(list || []));
  }
  function getCurrentFromSession() {
    try { return JSON.parse(sessionStorage.getItem("currentPlan") || "null"); } catch { return null; }
  }

  function renderList() {
    const listEl = byId("list"); listEl.innerHTML = "";
    if (!LIST.length) { listEl.innerHTML = `<div class="item item-empty">Chưa có bài giảng</div>`; return; }
    LIST.forEach((p, idx) => {
      const el = document.createElement("div");
      el.className = "item";
      el.innerHTML = `
        <div class="item-title">${p.title || "Kế hoạch"}</div>
        <div class="meta">
          <span>${p.subject || "Môn"} — ${p.grade || "Lớp"}</span>
          <span>⏱ ${p.duration || "45 phút"}</span>
        </div>
      `;
      el.onclick = () => select(p.id, idx, el);
      listEl.appendChild(el);
    });
  }

  function renderViewerEditor() {
    const wrap = byId("container"); if (!wrap) return;
    wrap.innerHTML = `
      <article id="viewer" class="viewer doc">${md(CURRENT?.markdown || "")}</article>
      <textarea id="editor" class="editor">${CURRENT?.markdown || ""}</textarea>
    `;
    EDITING = false;
    byId("saveBtn").style.display = "none";
    byId("editor").style.display = "none";
    byId("viewer").style.display = "block";

    const dlBtn = byId("downloadBtn");
    if (dlBtn) {
      if (CURRENT?.downloadUrl) { dlBtn.href = CURRENT.downloadUrl; dlBtn.style.display = "inline-flex"; }
      else { dlBtn.removeAttribute("href"); dlBtn.style.display = "none"; }
    }
  }

  function mergeUniquePlans(a = [], b = []) {
    const map = new Map(); [...a, ...b].forEach(p => { if (p && p.id) map.set(p.id, p); });
    return [...map.values()];
  }

  function load() {
    const planId = q("planId");
    let fromLocal = loadListFromStorage();
    const ss = getCurrentFromSession();
    if (ss && !fromLocal.find(x => x.id === ss.id)) fromLocal.unshift(ss);
    const fromServer = readPlansDataFromScript();

    LIST = mergeUniquePlans(fromLocal, fromServer);
    renderList();

    let open = null;
    if (planId) open = LIST.find(x => x.id === planId);
    if (!open && ss) open = LIST.find(x => x.id === ss.id);
    if (!open && LIST.length) open = LIST[0];

    if (open) {
      const idx = LIST.findIndex(x => x.id === open.id);
      const listEl = byId("list");
      const el = listEl && listEl.children[idx];
      select(open.id, idx, el);
    }
  }

  function select(id, idx, el) {
    CURRENT = LIST.find(x => x.id === id);
    document.querySelectorAll(".item").forEach(n => n.classList.remove("active"));
    if (el) el.classList.add("active");

    byId("title").textContent = CURRENT?.title || "Kế hoạch";
    byId("editBtn").disabled = !CURRENT;
    byId("removeBtn").disabled = !CURRENT;

    renderViewerEditor();
  }

  function toggleEdit() {
    if (!CURRENT) return;
    EDITING = !EDITING;
    const v = byId("viewer"); const e = byId("editor");
    if (EDITING) {
      e.value = CURRENT.markdown || "";
      v.style.display = "none"; e.style.display = "block";
      byId("saveBtn").style.display = "inline-flex";
      byId("editBtn").textContent = "Thoát sửa";
    } else {
      v.style.display = "block"; e.style.display = "none";
      byId("saveBtn").style.display = "none";
      byId("editBtn").textContent = "Chỉnh sửa";
    }
  }

  function save() {
    if (!CURRENT) return;
    const txt = (byId("editor").value || "");
    CURRENT.markdown = txt;

    let list = loadListFromStorage();
    const i = list.findIndex(p => p.id === CURRENT.id);
    if (i >= 0) list[i] = CURRENT; else list.unshift(CURRENT);
    saveListToStorage(list);
    sessionStorage.setItem("currentPlan", JSON.stringify(CURRENT));

    byId("viewer").innerHTML = md(CURRENT.markdown);
    toggleEdit();
    showToast("Đã lưu bản chỉnh sửa");
  }

  function sanitizeFileName(name) {
    try { return String(name).replace(/[^\p{L}\p{N}\-_ ]/gu, "").replace(/\s+/g, "_"); }
    catch { return String(name).replace(/[^a-zA-Z0-9\-_ ]/g, "").replace(/\s+/g, "_"); }
  }

  function download() {
    if (!CURRENT) return;
    if (CURRENT.downloadUrl) { window.open(CURRENT.downloadUrl, "_blank", "noopener"); return; }
    const content = CURRENT.markdown || "";
    const a = document.createElement("a");
    const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    a.href = url; a.download = sanitizeFileName(CURRENT.title || "lesson_plan") + ".md";
    document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
    showToast("Đã tải xuống Markdown");
  }

  function removePlan() {
    if (!CURRENT) return;
    if (!confirm("Xoá bài này khỏi danh sách trình duyệt?")) return;
    let list = loadListFromStorage().filter(p => p.id !== CURRENT.id);
    saveListToStorage(list);
    const ss = getCurrentFromSession();
    if (ss && ss.id === CURRENT.id) sessionStorage.removeItem("currentPlan");
    CURRENT = null;
    byId("container").innerHTML = `<div class="empty">Đã xoá. Hãy chọn bài khác hoặc tạo mới.</div>`;
    byId("title").textContent = "Chọn một bài giảng để xem";
    byId("editBtn").disabled = true;
    byId("removeBtn").disabled = true;
    load();
  }

  function openCreate() { byId("modal").classList.add("show"); }
  function closeCreate() { byId("modal").classList.remove("show"); byId("createForm").reset(); }
  function onCreateSubmit(e) {
    e.preventDefault();
    const t = byId("f_title").value.trim();
    const s = byId("f_subject").value.trim();
    const g = byId("f_grade").value.trim();
    const d = byId("f_duration").value.trim();

    const plan = {
      id: Date.now().toString(),
      title: t || "Bài giảng mới",
      subject: s || "Chưa xác định",
      grade: g ? `Lớp ${g}` : "Chưa xác định",
      duration: d ? `${d} phút` : "45 phút",
      date: new Date().toLocaleDateString("vi-VN"),
      status: "completed",
      markdown: `# ${t || "Bài giảng mới"}\n\n> Nhập nội dung tại đây…`,
    };

    const list = loadListFromStorage();
    list.unshift(plan);
    saveListToStorage(list);
    sessionStorage.setItem("currentPlan", JSON.stringify(plan));

    closeCreate();
    load();
    showToast("Đã tạo bài giảng mới");
  }

  function backToChat() { window.location.href = "/chat"; }

  window.toggleEdit = toggleEdit;
  window.save = save;
  window.download = download;
  window.removePlan = removePlan;
  window.openCreate = openCreate;
  window.closeCreate = closeCreate;
  window.backToChat = backToChat;

  window.addEventListener("DOMContentLoaded", () => {
    byId("createForm")?.addEventListener("submit", onCreateSubmit);
    load();
  });
})();
