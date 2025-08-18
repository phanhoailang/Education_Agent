"use strict";

/**
 * Chat JS – dùng chung panel cho Plan & Quiz (Markdown).
 * - Hỗ trợ LaTeX (MathJax) sau khi render.
 * - Quiz có card riêng, mở ra panel y như Plan, có Edit/Sao chép/Tải .md.
 */

const $ = (sel) => document.querySelector(sel);
const byId = (id) => document.getElementById(id);

/* ===== Utils ===== */
function readJSONFromScript(id, fallback = null) {
  try {
    const el = byId(id); if (!el) return fallback;
    const raw = (el.textContent || "").trim(); if (!raw) return fallback;
    return JSON.parse(raw);
  } catch { return fallback; }
}
function escapeHTML(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
function renderMarkdownHTML(md) {
  if (!md) return "";
  try {
    if (window.marked && window.DOMPurify) {
      marked.setOptions({ gfm: true, breaks: true, headerIds: true, mangle: false });
      const raw = marked.parse(md);
      return DOMPurify.sanitize(raw);
    }
  } catch { }
  return "<pre style='white-space:pre-wrap'>" + escapeHTML(md) + "</pre>";
}
function typesetMath(scopeEl) {
  // Gọi MathJax để hiển thị LaTeX sau khi DOM đã render
  try {
    if (window.MathJax && typeof MathJax.typesetPromise === "function") {
      const targets = scopeEl ? [scopeEl] : undefined;
      MathJax.typesetPromise(targets).catch(() => { });
    }
  } catch { }
}

/* ===== State ===== */
let currentPlanData = null;   // { id, title, markdown, downloadUrl, ... }
let currentQuizData = null;   // tương tự, nhưng cho Quiz
let PANEL_EDITING = false;
let PANEL_MODE = "plan";      // "plan" | "quiz"

/* ===== Storage helpers ===== */
function savePlanToStorage(plan) {
  const planToSave = {
    id: plan.id || ("plan_" + Date.now().toString()),
    title: plan.title || "Kế hoạch bài giảng",
    subject: plan.subject || "Chưa xác định",
    grade: plan.grade || "Chưa xác định",
    duration: plan.duration || "45 phút",
    date: plan.date || new Date().toLocaleDateString("vi-VN"),
    status: "completed",
    markdown: plan.markdown || "",
    downloadUrl: plan.downloadUrl || "",
    fileName: plan.fileName || "",
    formData: plan.formData || {}
  };
  sessionStorage.setItem("currentPlan", JSON.stringify(planToSave));
  const list = JSON.parse(localStorage.getItem("planList") || "[]");
  const i = list.findIndex(p => p.id === planToSave.id);
  if (i >= 0) list[i] = planToSave; else list.unshift(planToSave);
  localStorage.setItem("planList", JSON.stringify(list));
  currentPlanData = planToSave;
  return planToSave;
}
function saveQuizMdToStorage(quiz) {
  const q = {
    id: quiz.id || ("quiz_" + Date.now().toString()),
    title: quiz.title || "Quiz",
    subject: quiz.subject || "Chưa xác định",
    grade: quiz.grade || "Chưa xác định",
    date: quiz.date || new Date().toLocaleDateString("vi-VN"),
    status: "completed",
    markdown: quiz.markdown || "",
    downloadUrl: quiz.downloadUrl || "",
    fileName: quiz.fileName || "",
    formData: quiz.formData || {}
  };
  sessionStorage.setItem("currentQuizMd", JSON.stringify(q));
  const list = JSON.parse(localStorage.getItem("quizMdList") || "[]");
  const i = list.findIndex(x => x.id === q.id);
  if (i >= 0) list[i] = q; else list.unshift(q);
  localStorage.setItem("quizMdList", JSON.stringify(list));
  currentQuizData = q;
  return q;
}
function extractPlanInfoFromForm(form) {
  const topic = form?.topic || form?.title || form?.lesson || "";
  const subj = form?.subject || "Chưa xác định";
  const grade = form?.grade ? `Lớp ${form.grade}` : "Chưa xác định";
  const dur = form?.duration ? `${form.duration} phút` : "45 phút";
  const title = topic ? `Kế hoạch bài giảng: ${topic}` : `Kế hoạch bài giảng: ${subj}`;
  return { title, subject: subj, grade, duration: dur };
}
function extractQuizInfoFromForm(form) {
  const topic = form?.topic || form?.title || form?.lesson || "";
  const subj = form?.subject || "Chưa xác định";
  const grade = form?.grade ? `Lớp ${form.grade}` : "Chưa xác định";
  const title = topic ? `Quiz: ${topic}` : `Quiz: ${subj}`;
  return { title, subject: subj, grade };
}

/* ===== Chat helpers ===== */
function addAIMessage(html) {
  const wrap = byId("chatMessages");
  const div = document.createElement("div");
  div.className = "message ai";
  div.innerHTML = `<div class="message-avatar">🤖</div><div class="message-content">${html}</div>`;
  wrap.appendChild(div);
  wrap.scrollTop = wrap.scrollHeight;
  requestAnimationFrame(sizeColumns);
}
function addUserMessage(html) {
  const wrap = byId("chatMessages");
  const div = document.createElement("div");
  div.className = "message user";
  div.innerHTML = `<div class="message-avatar">👤</div><div class="message-content">${html}</div>`;
  wrap.appendChild(div);
  wrap.scrollTop = wrap.scrollHeight;
  requestAnimationFrame(sizeColumns);
}

/* ===== Equal height logic ===== */
function ensurePanelInsideGrid() {
  const page = byId("page");
  const panelCol = byId("panelCol");
  if (page && panelCol && panelCol.parentElement !== page) {
    page.appendChild(panelCol);
  }
}
function forceTwoColumns() {
  const page = byId("page");
  if (!page) return;
  document.body.classList.add("panel-open");
  page.classList.add("is-open");
  const cols = getComputedStyle(page).gridTemplateColumns;
  const looksOneCol = !cols || cols.split(" ").length < 2;
  if (looksOneCol) {
    page.style.display = "grid";
    page.style.gridTemplateColumns = "minmax(0, 2fr) minmax(0, 3fr)";
  }
}
function sizeColumns() {
  const header = document.querySelector(".header");
  const headerBottom = header ? header.getBoundingClientRect().bottom : 0;
  const avail = Math.max(360, Math.floor(window.innerHeight - headerBottom - 16));
  const chatBox = document.querySelector(".col-chat .chat-container");
  if (chatBox) {
    chatBox.style.height = `${avail}px`;
    chatBox.style.maxHeight = `${avail}px`;
  }
  const panel = byId("planPanel");
  if (panel && panel.getAttribute("aria-hidden") !== "true") {
    panel.style.height = `${avail}px`;
    panel.style.maxHeight = `${avail}px`;
  }
}

/* ===== Panel Viewer/Editor (generic cho PLAN/QUIZ) ===== */
function getActiveData() {
  return PANEL_MODE === "quiz" ? currentQuizData : currentPlanData;
}
function setDownloadLinkForActive() {
  const dlEl = byId("panelDownloadLink");
  const data = getActiveData();
  if (!dlEl) return;
  if (data?.downloadUrl) {
    dlEl.href = data.downloadUrl;
    dlEl.style.display = "inline-flex";
    // label: luôn là Markdown
    dlEl.textContent = "⬇️ Tải Markdown";
  } else {
    dlEl.removeAttribute("href");
    dlEl.style.display = "none";
  }
}
function renderPanelViewer() {
  const body = byId("planPanelBody");
  if (!body) return;

  const data = getActiveData();
  const md = data?.markdown || "";

  body.innerHTML = `
    <article id="panelViewer" class="doc">${renderMarkdownHTML(md)}</article>
    <textarea id="panelEditor" class="panel-editor" style="display:none;width:100%;min-height:60vh;border:1px solid #e5e7eb;border-radius:12px;padding:12px;background:#fff;"></textarea>
  `;
  PANEL_EDITING = false;
  byId("panelSaveBtn")?.style && (byId("panelSaveBtn").style.display = "none");
  byId("panelCancelBtn")?.style && (byId("panelCancelBtn").style.display = "none");
  byId("panelEditBtn")?.style && (byId("panelEditBtn").style.display = "inline-flex");

  // Typeset LaTeX sau khi render
  const viewer = byId("panelViewer");
  typesetMath(viewer);
  requestAnimationFrame(sizeColumns);
}
function renderPanelFromCurrent() {
  const data = getActiveData();
  if (!data) return;

  ensurePanelInsideGrid();
  forceTwoColumns();
  byId("planPanel")?.setAttribute("aria-hidden", "false");

  const titleEl = byId("planPanelTitle");
  if (titleEl) titleEl.textContent = data.title || (PANEL_MODE === "quiz" ? "Quiz" : "Kế hoạch bài giảng");

  setDownloadLinkForActive();
  renderPanelViewer();
}
window.openPanelFromCurrent = renderPanelFromCurrent;

function togglePanelEdit(forceState) {
  const viewer = byId("panelViewer");
  const editor = byId("panelEditor");
  const data = getActiveData();
  if (!viewer || !editor || !data) return;

  if (typeof forceState === "boolean") { PANEL_EDITING = forceState; }
  else { PANEL_EDITING = !PANEL_EDITING; }

  if (PANEL_EDITING) {
    editor.value = data.markdown || "";
    viewer.style.display = "none";
    editor.style.display = "block";
    byId("panelSaveBtn").style.display = "inline-flex";
    byId("panelCancelBtn").style.display = "inline-flex";
    byId("panelEditBtn").style.display = "none";
  } else {
    viewer.style.display = "block";
    editor.style.display = "none";
    byId("panelSaveBtn").style.display = "none";
    byId("panelCancelBtn").style.display = "none";
    byId("panelEditBtn").style.display = "inline-flex";
  }
  requestAnimationFrame(sizeColumns);
}
window.togglePanelEdit = togglePanelEdit;

function savePanelEdit() {
  const editor = byId("panelEditor");
  const data = getActiveData();
  if (!data || !editor) return;

  data.markdown = editor.value || "";

  if (PANEL_MODE === "quiz") {
    sessionStorage.setItem("currentQuizMd", JSON.stringify(data));
    const list = JSON.parse(localStorage.getItem("quizMdList") || "[]");
    const i = list.findIndex(x => x.id === data.id);
    if (i >= 0) list[i] = data; else list.unshift(data);
    localStorage.setItem("quizMdList", JSON.stringify(list));
  } else {
    sessionStorage.setItem("currentPlan", JSON.stringify(data));
    const list = JSON.parse(localStorage.getItem("planList") || "[]");
    const i = list.findIndex(p => p.id === data.id);
    if (i >= 0) list[i] = data; else list.unshift(data);
    localStorage.setItem("planList", JSON.stringify(list));
  }

  const viewer = byId("panelViewer");
  if (viewer) viewer.innerHTML = renderMarkdownHTML(data.markdown);
  togglePanelEdit(false);
  typesetMath(viewer);
  toast("Đã lưu bản chỉnh sửa");
}
window.savePanelEdit = savePanelEdit;

/* ---- Misc ---- */
function switchTab(tab) {
  document.querySelectorAll(".nav-tab").forEach(b => {
    const isActive = b.textContent.trim().toLowerCase().includes(tab);
    b.classList.toggle("active", isActive);
  });
  if (tab === "chat") {
    document.querySelector(".col-chat")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}
window.switchTab = switchTab;

function copyPanelContent() {
  const data = getActiveData();
  if (!data?.markdown) return;
  navigator.clipboard.writeText(data.markdown)
    .then(() => toast("Đã sao chép nội dung!"))
    .catch(() => toast("Không thể sao chép", true));
}
window.copyPanelContent = copyPanelContent;

function openLessonPlanPage() {
  const plan = currentPlanData;
  const url = plan?.id ? `/lesson-plan?planId=${encodeURIComponent(plan.id)}` : "/lesson-plan";
  window.open(url, "_blank");
}
window.openLessonPlanPage = openLessonPlanPage;

function closePlanPanel() {
  const page = byId("page");
  document.body.classList.remove("panel-open");
  page?.classList.remove("is-open");
  if (page) { page.style.gridTemplateColumns = ""; page.style.display = ""; }
  const panel = byId("planPanel");
  if (panel) { panel.style.height = ""; panel.style.maxHeight = ""; }
  byId("planPanel")?.setAttribute("aria-hidden", "true");
  requestAnimationFrame(sizeColumns);
}
window.closePlanPanel = closePlanPanel;

function goBack() { window.history.back(); }
window.goBack = goBack;

function toast(msg, error = false) {
  const t = document.createElement("div");
  t.style.cssText = `position:fixed;top:20px;right:20px;background:${error ? "#ef4444" : "#16a34a"};color:#fff;padding:10px 14px;border-radius:10px;z-index:1000;transform:translateY(-8px);opacity:0;transition:all .2s`;
  t.textContent = msg; document.body.appendChild(t);
  requestAnimationFrame(() => { t.style.opacity = "1"; t.style.transform = "translateY(0)"; });
  setTimeout(() => { t.style.opacity = "0"; t.style.transform = "translateY(-8px)"; setTimeout(() => t.remove(), 180); }, 1800);
}

/* ===== Cards trong chat ===== */
function showLessonCard(markdown, downloadUrl = "", fileName = "", formData = {}) {
  const info = extractPlanInfoFromForm(formData);
  const plan = savePlanToStorage({ ...info, markdown, downloadUrl, fileName, formData });
  const preview = (markdown || "").substring(0, 170).replace(/[#*_>\-\|]/g, "").trim() + "...";

  const card = `
    <div class="plan-card" onclick="openPlanPanelFromCurrent()">
      <div class="plan-card__icon">📘</div>
      <div>
        <div class="plan-card__title">Kế hoạch bài giảng đã tạo thành công!</div>
        <ul class="plan-card__meta">
          <li><strong>Môn học:</strong>&nbsp;${escapeHTML(plan.subject)}</li>
          <li><strong>Lớp:</strong>&nbsp;${escapeHTML(plan.grade)}</li>
          <li><strong>Thời gian:</strong>&nbsp;${escapeHTML(plan.duration)}</li>
          <li><strong>Ngày tạo:</strong>&nbsp;${escapeHTML(plan.date)}</li>
        </ul>
        <div style="font-size:12px;color:#6b7280;margin:6px 0 10px 0;border-top:1px solid #e9ecef;padding-top:8px;">
          <strong>Nội dung xem trước:</strong><br>${escapeHTML(preview)}
        </div>
        <div class="plan-card__footer">
          ${downloadUrl ? `<a href="${escapeHTML(downloadUrl)}" target="_blank" rel="noopener" class="chip-btn" onclick="event.stopPropagation()">⬇️ Tải Markdown</a>` : ""}
          <button class="chip-btn view" onclick="event.stopPropagation(); openPlanPanelFromCurrent()">👁 Xem</button>
          <button class="chip-btn edit" onclick="event.stopPropagation(); PANEL_MODE='plan'; togglePanelEdit(true); openPlanPanelFromCurrent()">✏️ Sửa nhanh</button>
        </div>
      </div>
    </div>
  `;
  addAIMessage(card);
}
function showQuizMdCard(markdown, downloadUrl = "", fileName = "", formData = {}) {
  const info = extractQuizInfoFromForm(formData);
  const quiz = saveQuizMdToStorage({ ...info, markdown, downloadUrl, fileName, formData });
  const preview = (markdown || "").substring(0, 160).replace(/[#*_>\-\|]/g, "").trim() + "...";

  const card = `
    <div class="plan-card" onclick="openQuizPanelFromCurrent()">
      <div class="plan-card__icon">📝</div>
      <div>
        <div class="plan-card__title">Quiz đã tạo (Markdown)</div>
        <ul class="plan-card__meta">
          <li><strong>Môn học:</strong>&nbsp;${escapeHTML(quiz.subject)}</li>
          <li><strong>Lớp:</strong>&nbsp;${escapeHTML(quiz.grade)}</li>
          <li><strong>Ngày tạo:</strong>&nbsp;${escapeHTML(quiz.date)}</li>
        </ul>
        <div style="font-size:12px;color:#6b7280;margin:6px 0 10px 0;border-top:1px solid #e9ecef;padding-top:8px;">
          <strong>Nội dung xem trước:</strong><br>${escapeHTML(preview)}
        </div>
        <div class="plan-card__footer">
          ${downloadUrl ? `<a href="${escapeHTML(downloadUrl)}" target="_blank" rel="noopener" class="chip-btn" onclick="event.stopPropagation()">⬇️ Tải Markdown</a>` : ""}
          <button class="chip-btn view" onclick="event.stopPropagation(); openQuizPanelFromCurrent()">👁 Xem</button>
          <button class="chip-btn edit" onclick="event.stopPropagation(); PANEL_MODE='quiz'; togglePanelEdit(true); openQuizPanelFromCurrent()">✏️ Sửa nhanh</button>
        </div>
      </div>
    </div>
  `;
  addAIMessage(card);
}

/* ===== Open panel helpers ===== */
function openPlanPanelFromCurrent() {
  PANEL_MODE = "plan";
  renderPanelFromCurrent();
}
window.openPlanPanelFromCurrent = openPlanPanelFromCurrent;

function openPlanPanel(markdownString, downloadUrl) {
  if (typeof markdownString === "string" && markdownString.trim().length) {
    const formData = readJSONFromScript("eduForm", {});
    const info = extractPlanInfoFromForm(formData);
    savePlanToStorage({ ...info, markdown: markdownString, downloadUrl: downloadUrl || "", formData });
  }
  openPlanPanelFromCurrent();
}
window.openPlanPanel = openPlanPanel;

function openQuizPanelFromCurrent() {
  PANEL_MODE = "quiz";
  renderPanelFromCurrent();
}
window.openQuizPanelFromCurrent = openQuizPanelFromCurrent;

function openQuizPanelMarkdown(markdownString, downloadUrl) {
  if (typeof markdownString === "string" && markdownString.trim().length) {
    const formData = readJSONFromScript("eduForm", {});
    const info = extractQuizInfoFromForm(formData);
    saveQuizMdToStorage({ ...info, markdown: markdownString, downloadUrl: downloadUrl || "", formData });
  }
  openQuizPanelFromCurrent();
}
window.openQuizPanelMarkdown = openQuizPanelMarkdown;


/* ===== Enhanced Init với debug chi tiết ===== */
function init() {
  console.log("🚀 [init] Starting chat initialization...");
  
  const status = document.querySelector(".status-indicator span");
  const input = byId("userInput");
  const send = byId("sendBtn");

  const formData = readJSONFromScript("eduForm", {});
  const markdown = readJSONFromScript("markdownContent", "");
  const mdDownloadUrl = readJSONFromScript("mdDownload", "");
  
  console.log("📊 [init] Data loaded:");
  console.log("  - formData:", formData);
  console.log("  - markdown length:", markdown.length);
  console.log("  - mdDownloadUrl:", mdDownloadUrl);

  // ===== LESSON PLAN PROCESSING =====
  const contentTypes = formData.content_types || [];
  console.log("🎯 [init] Content types:", contentTypes);
  
  if (contentTypes.includes("lesson_plan")) {
    console.log("📘 [init] Processing lesson plan...");
    if (markdown && markdown.trim()) {
      console.log("✅ [init] Showing lesson plan card from server data");
      showLessonCard(markdown, mdDownloadUrl || "", "", formData);
      PANEL_MODE = "plan";
      renderPanelFromCurrent();
    } else {
      console.log("🔄 [init] No server data, checking session storage...");
      try {
        const ss = JSON.parse(sessionStorage.getItem("currentPlan") || "null");
        if (ss && ss.markdown) {
          console.log("✅ [init] Restored lesson plan from session storage");
          currentPlanData = ss;
          showLessonCard(ss.markdown, ss.downloadUrl || "", ss.fileName || "", ss.formData || {});
          requestAnimationFrame(sizeColumns);
        } else {
          console.log("ℹ️ [init] No lesson plan data found");
        }
      } catch (e) {
        console.error("❌ [init] Error loading lesson plan from session:", e);
      }
    }
  } else {
    console.log("⏭️ [init] Lesson plan not selected, skipping");
  }

  // ===== QUIZ PROCESSING =====
  if (contentTypes.includes("quiz")) {
    console.log("📝 [init] Processing quiz...");
    const quizInjected = readJSONFromScript("quizContent", null);
    const quizMd = (quizInjected && typeof quizInjected === "object") ? (quizInjected.markdown || "") : "";
    const quizDl = readJSONFromScript("quizDownload", "");
    
    console.log("📊 [init] Quiz data:");
    console.log("  - quizInjected:", quizInjected);
    console.log("  - quizMd length:", quizMd.length);
    console.log("  - quizDl:", quizDl);
    
    if (quizMd && quizMd.trim()) {
      console.log("✅ [init] Showing quiz card from server data");
      showQuizMdCard(quizMd, quizDl || "", "", formData);
    } else {
      console.log("🔄 [init] No server quiz data, checking session storage...");
      try {
        const ssq = JSON.parse(sessionStorage.getItem("currentQuizMd") || "null");
        if (ssq && ssq.markdown) {
          console.log("✅ [init] Restored quiz from session storage");
          currentQuizData = ssq;
          showQuizMdCard(ssq.markdown, ssq.downloadUrl || "", ssq.fileName || "", ssq.formData || {});
        } else {
          console.log("ℹ️ [init] No quiz data found");
        }
      } catch (e) {
        console.error("❌ [init] Error loading quiz from session:", e);
      }
    }
  } else {
    console.log("⏭️ [init] Quiz not selected, skipping");
  }

  // ===== UI SETUP =====
  if (status) status.textContent = "Sẵn sàng chat";
  if (input) { 
    input.disabled = false; 
    input.placeholder = "Nhập tin nhắn của bạn..."; 
  }
  if (send) send.disabled = false;

  sizeColumns();
  window.addEventListener("resize", sizeColumns);

  // Event listeners
  input?.addEventListener("keypress", (e) => {
    if (e.key === "Enter" && !input.disabled) {
      const v = input.value.trim(); 
      if (!v) return;
      addUserMessage(escapeHTML(v));
      input.value = "";
    }
  });
  
  send?.addEventListener("click", () => {
    const v = input.value?.trim(); 
    if (!v) return;
    addUserMessage(escapeHTML(v));
    input.value = "";
  });

  console.log("✅ [init] Initialization complete");
}

/* ===== Enhanced card functions với debug ===== */
function showLessonCard(markdown, downloadUrl = "", fileName = "", formData = {}) {
  console.log("📘 [showLessonCard] Creating lesson plan card...");
  console.log("  - markdown length:", markdown.length);
  console.log("  - downloadUrl:", downloadUrl);
  console.log("  - formData:", formData);
  
  const info = extractPlanInfoFromForm(formData);
  const plan = savePlanToStorage({ ...info, markdown, downloadUrl, fileName, formData });
  const preview = (markdown || "").substring(0, 170).replace(/[#*_>\-\|]/g, "").trim() + "...";

  const card = `
    <div class="plan-card" onclick="openPlanPanelFromCurrent()">
      <div class="plan-card__icon">📘</div>
      <div>
        <div class="plan-card__title">Kế hoạch bài giảng đã tạo thành công!</div>
        <ul class="plan-card__meta">
          <li><strong>Môn học:</strong>&nbsp;${escapeHTML(plan.subject)}</li>
          <li><strong>Lớp:</strong>&nbsp;${escapeHTML(plan.grade)}</li>
          <li><strong>Thời gian:</strong>&nbsp;${escapeHTML(plan.duration)}</li>
          <li><strong>Ngày tạo:</strong>&nbsp;${escapeHTML(plan.date)}</li>
        </ul>
        <div style="font-size:12px;color:#6b7280;margin:6px 0 10px 0;border-top:1px solid #e9ecef;padding-top:8px;">
          <strong>Nội dung xem trước:</strong><br>${escapeHTML(preview)}
        </div>
        <div class="plan-card__footer">
          ${downloadUrl ? `<a href="${escapeHTML(downloadUrl)}" target="_blank" rel="noopener" class="chip-btn" onclick="event.stopPropagation()">⬇️ Tải Markdown</a>` : ""}
          <button class="chip-btn view" onclick="event.stopPropagation(); openPlanPanelFromCurrent()">👁 Xem</button>
          <button class="chip-btn edit" onclick="event.stopPropagation(); PANEL_MODE='plan'; togglePanelEdit(true); openPlanPanelFromCurrent()">✏️ Sửa nhanh</button>
        </div>
      </div>
    </div>
  `;
  
  addAIMessage(card);
  console.log("✅ [showLessonCard] Card added to chat");
}

function showQuizMdCard(markdown, downloadUrl = "", fileName = "", formData = {}) {
  console.log("📝 [showQuizMdCard] Creating quiz card...");
  console.log("  - markdown length:", markdown.length);
  console.log("  - downloadUrl:", downloadUrl);
  console.log("  - formData:", formData);
  
  const info = extractQuizInfoFromForm(formData);
  const quiz = saveQuizMdToStorage({ ...info, markdown, downloadUrl, fileName, formData });
  const preview = (markdown || "").substring(0, 160).replace(/[#*_>\-\|]/g, "").trim() + "...";

  const card = `
    <div class="plan-card" onclick="openQuizPanelFromCurrent()">
      <div class="plan-card__icon">📝</div>
      <div>
        <div class="plan-card__title">Quiz đã tạo thành công (Markdown)</div>
        <ul class="plan-card__meta">
          <li><strong>Môn học:</strong>&nbsp;${escapeHTML(quiz.subject)}</li>
          <li><strong>Lớp:</strong>&nbsp;${escapeHTML(quiz.grade)}</li>
          <li><strong>Ngày tạo:</strong>&nbsp;${escapeHTML(quiz.date)}</li>
        </ul>
        <div style="font-size:12px;color:#6b7280;margin:6px 0 10px 0;border-top:1px solid #e9ecef;padding-top:8px;">
          <strong>Nội dung xem trước:</strong><br>${escapeHTML(preview)}
        </div>
        <div class="plan-card__footer">
          ${downloadUrl ? `<a href="${escapeHTML(downloadUrl)}" target="_blank" rel="noopener" class="chip-btn" onclick="event.stopPropagation()">⬇️ Tải Markdown</a>` : ""}
          <button class="chip-btn view" onclick="event.stopPropagation(); openQuizPanelFromCurrent()">👁 Xem</button>
          <button class="chip-btn edit" onclick="event.stopPropagation(); PANEL_MODE='quiz'; togglePanelEdit(true); openQuizPanelFromCurrent()">✏️ Sửa nhanh</button>
        </div>
      </div>
    </div>
  `;
  
  addAIMessage(card);
  console.log("✅ [showQuizMdCard] Card added to chat");
}

// Rest of the code remains the same...
window.addEventListener("DOMContentLoaded", init);
