"use strict";

/* -------------------- Helpers -------------------- */
const $ = (s) => document.querySelector(s);
const byId = (id) => document.getElementById(id);

function readJSONFromScript(id, fallback = null) {
  try {
    const el = byId(id);
    if (!el) return fallback;
    const raw = (el.textContent || "").trim();
    if (!raw) return fallback;
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

/* -------------------- State -------------------- */
let currentQuizDoc = null;     // { id,title,subject,grade,markdown,downloadUrl,date }
let PANEL_EDITING = false;

/* -------------------- Layout utils -------------------- */
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
  if (chatBox) { chatBox.style.height = `${avail}px`; chatBox.style.maxHeight = `${avail}px`; }

  const panel = byId("quizPanel");
  if (panel && panel.getAttribute("aria-hidden") !== "true") {
    panel.style.height = `${avail}px`; panel.style.maxHeight = `${avail}px`;
  }
}

/* -------------------- Chat helpers -------------------- */
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

/* -------------------- Storage -------------------- */
function saveQuizDocToStorage(doc) {
  const toSave = {
    id: doc.id || Date.now().toString(),
    title: doc.title || "Quiz",
    subject: doc.subject || "Chưa xác định",
    grade: doc.grade || "Chưa xác định",
    markdown: doc.markdown || "",
    downloadUrl: doc.downloadUrl || "",
    date: doc.date || new Date().toLocaleDateString("vi-VN"),
    status: "completed",
    formData: doc.formData || {}
  };
  sessionStorage.setItem("currentQuizDoc", JSON.stringify(toSave));
  const list = JSON.parse(localStorage.getItem("quizDocList") || "[]");
  const idx = list.findIndex(q => q.id === toSave.id);
  if (idx >= 0) list[idx] = toSave; else list.unshift(toSave);
  localStorage.setItem("quizDocList", JSON.stringify(list));
  currentQuizDoc = toSave;
  return toSave;
}

/* -------------------- Panel rendering -------------------- */
function renderPanelViewer() {
  const body = byId("quizPanelBody");
  if (!body || !currentQuizDoc) return;
  body.innerHTML = `
    <article id="panelViewer" class="doc">${renderMarkdownHTML(currentQuizDoc.markdown)}</article>
    <textarea id="panelEditor" class="panel-editor" style="display:none;width:100%;min-height:60vh;border:1px solid #e5e7eb;border-radius:12px;padding:12px;background:#fff;"></textarea>
  `;
  // typeset LaTeX
  if (window.MathJax?.typesetPromise) window.MathJax.typesetPromise([body]).catch(() => { });
  PANEL_EDITING = false;
  byId("panelSaveBtn").style.display = "none";
  byId("panelCancelBtn").style.display = "none";
  byId("panelEditBtn").style.display = "inline-flex";
}
function renderQuizPanelFromCurrent() {
  if (!currentQuizDoc) return;
  ensurePanelInsideGrid();
  forceTwoColumns();
  byId("quizPanel")?.setAttribute("aria-hidden", "false");

  const titleEl = byId("quizPanelTitle");
  if (titleEl) titleEl.textContent = currentQuizDoc.title || "Quiz";

  const dlEl = byId("panelDownloadLink");
  if (dlEl) {
    if (currentQuizDoc.downloadUrl) {
      dlEl.href = currentQuizDoc.downloadUrl;
      dlEl.textContent = currentQuizDoc.downloadUrl.endsWith(".md") ? "⬇️ Tải Markdown" : "⬇️ Tải JSON";
      dlEl.style.display = "inline-flex";
    } else {
      dlEl.removeAttribute("href");
      dlEl.style.display = "none";
    }
  }
  renderPanelViewer();
  requestAnimationFrame(sizeColumns);
}
window.openQuizPanelFromCurrent = renderQuizPanelFromCurrent;

function openQuizPanel(markdownString, downloadUrl, formData) {
  if (typeof markdownString === "string" && markdownString.trim()) {
    const topic = formData?.topic || formData?.title || formData?.lesson || "";
    const subj = formData?.subject || "Chưa xác định";
    const grade = formData?.grade ? `Lớp ${formData.grade}` : "Chưa xác định";
    const title = topic ? `Quiz: ${topic}` : `Quiz: ${subj}`;
    saveQuizDocToStorage({ title, subject: subj, grade, markdown: markdownString, downloadUrl: downloadUrl || "", formData });
  }
  renderQuizPanelFromCurrent();
}
window.openQuizPanel = openQuizPanel;

function closeQuizPanel() {
  const page = byId("page");
  document.body.classList.remove("panel-open");
  page?.classList.remove("is-open");
  if (page) { page.style.gridTemplateColumns = ""; page.style.display = ""; }
  const panel = byId("quizPanel");
  if (panel) { panel.style.height = ""; panel.style.maxHeight = ""; }
  byId("quizPanel")?.setAttribute("aria-hidden", "true");
  requestAnimationFrame(sizeColumns);
}
window.closeQuizPanel = closeQuizPanel;

/* ---- Inline Editing ---- */
function togglePanelEdit(forceState) {
  const viewer = byId("panelViewer");
  const editor = byId("panelEditor");
  if (!viewer || !editor || !currentQuizDoc) return;

  if (typeof forceState === "boolean") { PANEL_EDITING = forceState; }
  else { PANEL_EDITING = !PANEL_EDITING; }

  if (PANEL_EDITING) {
    editor.value = currentQuizDoc.markdown || "";
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
  if (!currentQuizDoc || !editor) return;
  currentQuizDoc.markdown = editor.value || "";

  sessionStorage.setItem("currentQuizDoc", JSON.stringify(currentQuizDoc));
  const list = JSON.parse(localStorage.getItem("quizDocList") || "[]");
  const i = list.findIndex(q => q.id === currentQuizDoc.id);
  if (i >= 0) list[i] = currentQuizDoc; else list.unshift(currentQuizDoc);
  localStorage.setItem("quizDocList", JSON.stringify(list));

  const viewer = byId("panelViewer");
  if (viewer) {
    viewer.innerHTML = renderMarkdownHTML(currentQuizDoc.markdown);
    if (window.MathJax?.typesetPromise) window.MathJax.typesetPromise([viewer]).catch(() => { });
  }
  togglePanelEdit(false);
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

function copyQuizContent() {
  if (!currentQuizDoc?.markdown) return;
  navigator.clipboard.writeText(currentQuizDoc.markdown)
    .then(() => toast("Đã sao chép nội dung!"))
    .catch(() => toast("Không thể sao chép", true));
}
window.copyQuizContent = copyQuizContent;

function toast(msg, error = false) {
  const t = document.createElement("div");
  t.style.cssText = `position:fixed;top:20px;right:20px;background:${error ? "#ef4444" : "#16a34a"};color:#fff;padding:10px 14px;border-radius:10px;z-index:1000;transform:translateY(-8px);opacity:0;transition:all .2s`;
  t.textContent = msg; document.body.appendChild(t);
  requestAnimationFrame(() => { t.style.opacity = "1"; t.style.transform = "translateY(0)"; });
  setTimeout(() => { t.style.opacity = "0"; t.style.transform = "translateY(-8px)"; setTimeout(() => t.remove(), 180); }, 1800);
}
function goBack() { window.history.back(); }
window.goBack = goBack;

/* -------------------- Card hiển thị trong chat -------------------- */
function showQuizCard(markdown, downloadUrl = "", fileName = "", formData = {}) {
  const topic = formData?.topic || formData?.title || formData?.lesson || "";
  const subj = formData?.subject || "Chưa xác định";
  const grade = formData?.grade ? `Lớp ${formData.grade}` : "Chưa xác định";
  const title = topic ? `Quiz: ${topic}` : `Quiz: ${subj}`;
  const doc = saveQuizDocToStorage({ title, subject: subj, grade, markdown, downloadUrl, formData });
  const preview = (markdown || "").substring(0, 140).replace(/[#*_>\-\|]/g, "").trim() + "...";

  const card = `
    <div class="plan-card" onclick="openQuizPanelFromCurrent()">
      <div class="plan-card__icon">📝</div>
      <div>
        <div class="plan-card__title">Quiz đã tạo (Markdown)</div>
        <ul class="plan-card__meta">
          <li><strong>Môn học:</strong>&nbsp;${escapeHTML(doc.subject)}</li>
          <li><strong>Lớp:</strong>&nbsp;${escapeHTML(doc.grade)}</li>
          <li><strong>Ngày tạo:</strong>&nbsp;${escapeHTML(doc.date)}</li>
        </ul>
        <div class="plan-card__preview">
          <strong>Nội dung xem trước:</strong><br>${escapeHTML(preview)}
        </div>
        <div class="plan-card__footer">
          ${downloadUrl ? `<a href="${escapeHTML(downloadUrl)}" target="_blank" rel="noopener" class="chip-btn" onclick="event.stopPropagation()">${downloadUrl.endsWith('.md') ? '⬇️ Tải Markdown' : '⬇️ Tải JSON'}</a>` : ""}
          <button class="chip-btn view" onclick="event.stopPropagation(); openQuizPanelFromCurrent()">👁 Xem</button>
          <button class="chip-btn edit" onclick="event.stopPropagation(); togglePanelEdit(true); openQuizPanelFromCurrent()">✏️ Sửa nhanh</button>
        </div>
      </div>
    </div>
  `;
  addAIMessage(card);
}

/* -------------------- Init -------------------- */
function init() {
  const status = document.querySelector(".status-indicator span");
  const input = byId("userInput");
  const send = byId("sendBtn");

  const formData = readJSONFromScript("eduForm", {});
  const quizObj = readJSONFromScript("quizContent", null);
  const quizDl = readJSONFromScript("quizDownload", "");

  // Rút markdown từ object quiz
  let quizMd = "";
  if (quizObj && typeof quizObj === "object") {
    quizMd =
      quizObj.markdown ||
      quizObj.complete_markdown ||
      quizObj.completeMarkdown ||
      "";
    // Fallback: nếu chỉ có các phần text rời
    if (!quizMd && quizObj.quiz_content && typeof quizObj.quiz_content === "object") {
      const order = ["NHẬN BIẾT", "THÔNG HIỂU", "VẬN DỤNG", "VẬN DỤNG CAO"];
      const parts = ["# BỘ CÂU HỎI TRẮC NGHIỆM", ""];
      parts.push("## CÂU HỎI");
      parts.push("");
      order.forEach(k => {
        const c = (quizObj.quiz_content[k] || "").trim();
        if (c) { parts.push(`### ${k}`); parts.push(""); parts.push(c); parts.push(""); }
      });
      quizMd = parts.join("\n");
    }
  }

  if (quizMd && typeof quizMd === "string") {
    showQuizCard(quizMd, quizDl || "", "", formData);
    renderQuizPanelFromCurrent();
  } else {
    try {
      const ss = JSON.parse(sessionStorage.getItem("currentQuizDoc") || "null");
      if (ss && ss.markdown) {
        currentQuizDoc = ss;
        showQuizCard(ss.markdown, ss.downloadUrl || "", ss.fileName || "", ss.formData || {});
        requestAnimationFrame(sizeColumns);
      } else {
        addAIMessage(`<strong>⚠️ Không tìm thấy nội dung quiz hợp lệ.</strong>`);
        requestAnimationFrame(sizeColumns);
      }
    } catch {
      addAIMessage(`<strong>⚠️ Không tìm thấy nội dung quiz hợp lệ.</strong>`);
      requestAnimationFrame(sizeColumns);
    }
  }

  if (status) status.textContent = "Sẵn sàng";
  if (input) { input.disabled = false; input.placeholder = "Nhập tin nhắn của bạn..."; }
  if (send) send.disabled = false;

  sizeColumns();
  window.addEventListener("resize", sizeColumns);

  input?.addEventListener("keypress", (e) => {
    if (e.key === "Enter" && !input.disabled) {
      const v = input.value.trim(); if (!v) return;
      addUserMessage(escapeHTML(v));
      input.value = "";
    }
  });
  send?.addEventListener("click", () => {
    const v = input.value?.trim(); if (!v) return;
    addUserMessage(escapeHTML(v));
    input.value = "";
  });
}
window.addEventListener("DOMContentLoaded", init);
