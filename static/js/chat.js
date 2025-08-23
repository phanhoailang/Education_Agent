"use strict";

/**
 * Chat JS — FIXED VERSION
 * Fixed quiz and slide processing bugs
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
      marked.setOptions({
        gfm: true,
        breaks: true,
        headerIds: true,
        mangle: false,
        sanitize: false
      });
      const raw = marked.parse(md);
      return DOMPurify.sanitize(raw, {});
    }
  } catch (e) {
    console.error("Markdown rendering error:", e);
  }
  return "<pre style='white-space:pre-wrap'>" + escapeHTML(md) + "</pre>";
}

/**
 * OPTIMIZED: Efficient markdown rendering
 */
function renderMarkdownWithMath(markdown, container) {
  if (!markdown || !container) return;

  // Chia markdown thành các phần nhỏ hơn
  const sections = splitMarkdownIntoSections(markdown);

  // Render từng phần một cách bất đồng bộ
  let index = 0;
  const renderNextSection = () => {
    if (index >= sections.length) return;

    const sectionMd = sections[index];
    const htmlContent = renderMarkdownHTML(sectionMd);

    // Tạo một div cho section và append
    const sectionDiv = document.createElement('div');
    sectionDiv.className = 'markdown-section';
    sectionDiv.innerHTML = htmlContent;
    container.appendChild(sectionDiv);

    index++;
    if (index < sections.length) {
      // Thêm setTimeout để yield control về browser, tránh block main thread
      setTimeout(() => {
        requestAnimationFrame(renderNextSection);
      }, 50);
    }
  };

  // Bắt đầu rendering
  container.innerHTML = ''; // Clear trước
  requestAnimationFrame(renderNextSection);
}

/**
 * Hàm helper để chia markdown thành các sections nhỏ
 */
function splitMarkdownIntoSections(markdown) {
  const sections = [];
  const lines = markdown.split('\n');
  let currentSection = [];
  const maxLinesPerSection = 30;

  lines.forEach(line => {
    if (line.startsWith('# ') || line.startsWith('## ') || line.startsWith('### ')) {
      if (currentSection.length > 0) {
        sections.push(currentSection.join('\n'));
        currentSection = [];
      }
    }
    currentSection.push(line);

    if (currentSection.length >= maxLinesPerSection) {
      sections.push(currentSection.join('\n'));
      currentSection = [];
    }
  });

  if (currentSection.length > 0) {
    sections.push(currentSection.join('\n'));
  }

  return sections;
}

/* ===== State ===== */
let currentPlanData = null;
let currentQuizData = null;
let currentSlideData = null;
let PANEL_EDITING = false;
let PANEL_MODE = "plan";

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

function saveSlideToStorage(slide) {
  const s = {
    id: slide.id || ("slide_" + Date.now().toString()),
    title: slide.title || "Kế hoạch slide",
    subject: slide.subject || "Chưa xác định",
    grade: slide.grade || "Chưa xác định",
    duration: slide.duration || "45 phút",
    date: slide.date || new Date().toLocaleDateString("vi-VN"),
    status: "completed",
    markdown: slide.markdown || "",
    downloadUrl: slide.downloadUrl || "",
    fileName: slide.fileName || "",
    formData: slide.formData || {},
    slideCount: countSlides(slide.markdown || "")
  };
  sessionStorage.setItem("currentSlide", JSON.stringify(s));
  const list = JSON.parse(localStorage.getItem("slideList") || "[]");
  const i = list.findIndex(x => x.id === s.id);
  if (i >= 0) list[i] = s; else list.unshift(s);
  localStorage.setItem("slideList", JSON.stringify(list));
  currentSlideData = s;
  return s;
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

function extractSlideInfoFromForm(form) {
  const topic = form?.topic || form?.title || form?.lesson || "";
  const subj = form?.subject || "Chưa xác định";
  const grade = form?.grade ? `Lớp ${form.grade}` : "Chưa xác định";
  const dur = form?.duration ? `${form.duration} phút` : "45 phút";
  const title = topic ? `Kế hoạch slide: ${topic}` : `Kế hoạch slide: ${subj}`;
  return { title, subject: subj, grade, duration: dur };
}

function countSlides(markdown) {
  if (!markdown) return 0;
  const separators = (markdown.match(/^---\s*$/gm) || []).length;
  const slideHeaders = (markdown.match(/^##?\s+Slide\s+\d+/gmi) || []).length;
  return Math.max(separators + 1, slideHeaders, 1);
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

/* ===== Layout functions ===== */
let resizeTimer = null;

function sizeColumns() {
  if (resizeTimer) {
    clearTimeout(resizeTimer);
  }

  resizeTimer = setTimeout(() => {
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
  }, 50); // Debounce resize
}

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

/* ===== Panel functions ===== */
function getActiveData() {
  switch (PANEL_MODE) {
    case "quiz": return currentQuizData;
    case "slide": return currentSlideData;
    default: return currentPlanData;
  }
}

function setDownloadLinkForActive() {
  const dlEl = byId("panelDownloadLink");
  const data = getActiveData();
  if (!dlEl) return;
  if (data?.downloadUrl) {
    dlEl.href = data.downloadUrl;
    dlEl.style.display = "inline-flex";
    dlEl.textContent = "⬇️ Tải Markdown";
  } else {
    dlEl.removeAttribute("href");
    dlEl.style.display = "none";
  }
}

/**
 * FIXED: Render panel viewer
 */
function renderPanelViewer() {
  const body = byId("planPanelBody");
  if (!body) return;

  const data = getActiveData();
  const md = data?.markdown || "";

  let additionalControls = "";
  if (PANEL_MODE === "slide" && md) {
    additionalControls = `
      <div class="slide-controls" style="margin-bottom: 16px; padding: 12px; background: #f8fafc; border-radius: 8px; border-left: 4px solid #3b82f6;">
        <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 8px;">
          <span style="font-weight: 600; color: #1e40af;">📊 Thông tin slide:</span>
          <span style="color: #64748b;">Tổng ${data.slideCount || countSlides(md)} slide</span>
        </div>
        <div style="display: flex; gap: 8px; flex-wrap: wrap;">
          <button onclick="openSlideViewer()" class="chip-btn" style="background: #3b82f6; color: white;">
            🎯 Xem slide đầy đủ
          </button>
          <button onclick="exportToPresentation()" class="chip-btn" style="background: #059669; color: white;">
            📤 Xuất PowerPoint
          </button>
        </div>
      </div>
    `;
  }

  // Use DocumentFragment for better performance
  const fragment = document.createDocumentFragment();
  const tempDiv = document.createElement('div');
  tempDiv.innerHTML = `
    ${additionalControls}
    <article id="panelViewer" class="doc"><div class="loading-placeholder">Đang tải nội dung...</div></article>
    <textarea id="panelEditor" class="panel-editor" style="display:none;width:100%;min-height:60vh;border:1px solid #e5e7eb;border-radius:12px;padding:12px;background:#fff;font-family:monospace;"></textarea>
  `;

  while (tempDiv.firstChild) {
    fragment.appendChild(tempDiv.firstChild);
  }

  body.innerHTML = '';
  body.appendChild(fragment);

  PANEL_EDITING = false;
  const saveBtn = byId("panelSaveBtn");
  const cancelBtn = byId("panelCancelBtn");
  const editBtn = byId("panelEditBtn");

  if (saveBtn) saveBtn.style.display = "none";
  if (cancelBtn) cancelBtn.style.display = "none";
  if (editBtn) editBtn.style.display = "inline-flex";

  // Efficient markdown rendering
  const viewer = byId("panelViewer");
  if (viewer) {
    renderMarkdownWithMath(md, viewer);
  }

  requestAnimationFrame(sizeColumns);
}

function renderPanelFromCurrent() {
  const data = getActiveData();
  if (!data) return;

  ensurePanelInsideGrid();
  forceTwoColumns();

  byId("planPanel")?.setAttribute("aria-hidden", "false");
  byId("slidePanel")?.setAttribute("aria-hidden", "true");

  const titleEl = byId("planPanelTitle");
  if (titleEl) {
    let title = data.title;
    if (PANEL_MODE === "quiz") title = title || "Quiz";
    else if (PANEL_MODE === "slide") title = title || "Kế hoạch slide";
    else title = title || "Kế hoạch bài giảng";
    titleEl.textContent = title;
  }

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
    editor.focus();
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

/**
 * FIXED: Save with batched updates
 */
function savePanelEdit() {
  const editor = byId("panelEditor");
  const data = getActiveData();
  if (!data || !editor) return;

  data.markdown = editor.value || "";

  // Batch storage updates
  requestAnimationFrame(() => {
    if (PANEL_MODE === "quiz") {
      sessionStorage.setItem("currentQuizMd", JSON.stringify(data));
      const list = JSON.parse(localStorage.getItem("quizMdList") || "[]");
      const i = list.findIndex(x => x.id === data.id);
      if (i >= 0) list[i] = data; else list.unshift(data);
      localStorage.setItem("quizMdList", JSON.stringify(list));
    } else if (PANEL_MODE === "slide") {
      data.slideCount = countSlides(data.markdown);
      sessionStorage.setItem("currentSlide", JSON.stringify(data));
      const list = JSON.parse(localStorage.getItem("slideList") || "[]");
      const i = list.findIndex(x => x.id === data.id);
      if (i >= 0) list[i] = data; else list.unshift(data);
      localStorage.setItem("slideList", JSON.stringify(list));
    } else {
      sessionStorage.setItem("currentPlan", JSON.stringify(data));
      const list = JSON.parse(localStorage.getItem("planList") || "[]");
      const i = list.findIndex(p => p.id === data.id);
      if (i >= 0) list[i] = data; else list.unshift(data);
      localStorage.setItem("planList", JSON.stringify(list));
    }

    const viewer = byId("panelViewer");
    if (viewer) {
      renderMarkdownWithMath(data.markdown, viewer);
    }

    togglePanelEdit(false);
    toast("Đã lưu bản chỉnh sửa");

    if (PANEL_MODE === "slide") {
      renderPanelViewer();
    }
  });
}
window.savePanelEdit = savePanelEdit;

/* ===== Slide functions ===== */
function openSlideViewer() {
  const data = currentSlideData;
  if (!data?.markdown) {
    toast("Không có nội dung slide để hiển thị", true);
    return;
  }

  const slideWindow = window.open('', '_blank', 'width=1024,height=768');
  if (slideWindow) {
    slideWindow.document.write(`
      <!DOCTYPE html>
      <html>
      <head>
        <title>${data.title || 'Slide'}</title>
        <style>
          body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
          .slide { 
            background: white; 
            padding: 40px; 
            margin: 20px auto; 
            max-width: 800px; 
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            border-radius: 8px;
            min-height: 500px;
            page-break-after: always;
          }
          h1, h2 { color: #2563eb; border-bottom: 2px solid #e5e7eb; padding-bottom: 8px; }
          h3, h4 { color: #374151; }
          .slide-nav {
            position: fixed; 
            top: 20px; 
            right: 20px; 
            background: #1f2937; 
            color: white; 
            padding: 10px 15px; 
            border-radius: 6px;
            z-index: 1000;
          }
          @media print {
            .slide-nav { display: none; }
            .slide { margin: 0; box-shadow: none; }
          }
        </style>
      </head>
      <body>
        <div class="slide-nav">
          <button onclick="window.print()">🖨️ In</button>
          <button onclick="window.close()">✕ Đóng</button>
        </div>
        ${renderSlidesFromMarkdown(data.markdown)}
      </body>
      </html>
    `);
    slideWindow.document.close();
  }
}
window.openSlideViewer = openSlideViewer;

function renderSlidesFromMarkdown(markdown) {
  if (!markdown) return '<div class="slide">Không có nội dung</div>';

  let slides = [];
  if (markdown.includes('\n---\n')) {
    slides = markdown.split('\n---\n');
  } else {
    const parts = markdown.split(/^##?\s+Slide\s+\d+/gmi);
    if (parts.length > 1) {
      slides = parts.slice(1);
    } else {
      slides = [markdown];
    }
  }

  return slides.map((slide, index) =>
    `<div class="slide">
      <div style="text-align: right; color: #9ca3af; font-size: 0.875rem; margin-bottom: 20px;">
        Slide ${index + 1} / ${slides.length}
      </div>
      ${renderMarkdownHTML(slide.trim())}
    </div>`
  ).join('');
}

function exportToPresentation() {
  toast("Tính năng xuất PowerPoint đang được phát triển", true);
}
window.exportToPresentation = exportToPresentation;

/* ===== FIXED: Process slide content ===== */
function processSlideContentFromServer() {
  console.log("📊 [processSlideContentFromServer] Processing slide content...");

  const slideInjected = readJSONFromScript("slideContent", null);
  const slideDownload = readJSONFromScript("slideDownload", "");

  console.log("📊 Debug slideInjected:", slideInjected, typeof slideInjected);
  console.log("📊 Debug slideDownload:", slideDownload);

  let slideMarkdown = null;

  if (slideInjected) {
    if (typeof slideInjected === "string" && slideInjected.trim() !== "") {
      slideMarkdown = slideInjected;
      console.log("✅ Found slide content as string");
    } else if (typeof slideInjected === "object" && slideInjected !== null) {
      console.log("📊 Slide content is object, keys:", Object.keys(slideInjected));

      // FIXED: Check các key phổ biến để tìm markdown content
      const possibleKeys = ['content', 'markdown', 'slide_content', 'data', 'complete_markdown'];

      for (const key of possibleKeys) {
        const value = slideInjected[key];
        if (value && typeof value === "string" && value.trim() !== "") {
          slideMarkdown = value;
          console.log(`✅ Found slide content in .${key} property`);
          break;
        }
      }

      // Nếu vẫn chưa tìm thấy, thử convert object thành JSON string
      if (!slideMarkdown && Object.keys(slideInjected).length > 0) {
        try {
          slideMarkdown = JSON.stringify(slideInjected, null, 2);
          console.log("⚠️ Using stringified slide object as fallback");
        } catch (e) {
          console.error("❌ Cannot stringify slide object:", e);
        }
      }
    }
  }

  if (slideMarkdown && slideMarkdown.trim() !== "" && slideMarkdown !== "{}") {
    console.log("✅ Valid slide markdown found, length:", slideMarkdown.length);
    return slideMarkdown;
  } else {
    console.log("⚠️ No valid slide content found");
    return null;
  }
}

/* ===== Utility functions ===== */
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

/* ===== Card functions ===== */
function showLessonCard(markdown, downloadUrl = "", fileName = "", formData = {}) {
  console.log("📘 [showLessonCard] Creating lesson plan card...");

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
          <button class="chip-btn edit" onclick="event.stopPropagation(); PANEL_MODE='plan'; togglePanelEdit(true); openPanelFromCurrent()">✏️ Sửa nhanh</button>
        </div>
      </div>
    </div>
  `;

  addAIMessage(card);
}

function showQuizMdCard(markdown, downloadUrl = "", fileName = "", formData = {}) {
  console.log("📝 [showQuizMdCard] Creating quiz card...");

  const info = extractQuizInfoFromForm(formData);
  const quiz = saveQuizMdToStorage({ ...info, markdown, downloadUrl, fileName, formData });
  const preview = (markdown || "").substring(0, 160).replace(/[#*_>\-\|]/g, "").trim() + "...";

  const card = `
    <div class="plan-card" onclick="openQuizPanelFromCurrent()">
      <div class="plan-card__icon">📝</div>
      <div>
        <div class="plan-card__title">Quiz đã tạo thành công</div>
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
          <button class="chip-btn edit" onclick="event.stopPropagation(); PANEL_MODE='quiz'; togglePanelEdit(true); openPanelFromCurrent()">✏️ Sửa nhanh</button>
        </div>
      </div>
    </div>
  `;

  addAIMessage(card);
}

function showSlideCard(markdown, downloadUrl = "", fileName = "", formData = {}) {
  console.log("📊 [showSlideCard] Creating slide card...");

  const info = extractSlideInfoFromForm(formData);
  const slide = saveSlideToStorage({ ...info, markdown, downloadUrl, fileName, formData });
  const preview = (markdown || "").substring(0, 160).replace(/[#*_>\-\|]/g, "").trim() + "...";
  const slideCount = countSlides(markdown);

  const card = `
    <div class="plan-card" onclick="openSlidePanelFromCurrent()">
      <div class="plan-card__icon">📊</div>
      <div>
        <div class="plan-card__title">Kế hoạch slide đã tạo thành công!</div>
        <ul class="plan-card__meta">
          <li><strong>Môn học:</strong>&nbsp;${escapeHTML(slide.subject)}</li>
          <li><strong>Lớp:</strong>&nbsp;${escapeHTML(slide.grade)}</li>
          <li><strong>Thời gian:</strong>&nbsp;${escapeHTML(slide.duration)}</li>
          <li><strong>Số slide:</strong>&nbsp;${slideCount} slide</li>
          <li><strong>Ngày tạo:</strong>&nbsp;${escapeHTML(slide.date)}</li>
        </ul>
        <div style="font-size:12px;color:#6b7280;margin:6px 0 10px 0;border-top:1px solid #e9ecef;padding-top:8px;">
          <strong>Nội dung xem trước:</strong><br>${escapeHTML(preview)}
        </div>
        <div class="plan-card__footer">
          ${downloadUrl ? `<a href="${escapeHTML(downloadUrl)}" target="_blank" rel="noopener" class="chip-btn" onclick="event.stopPropagation()">⬇️ Tải Markdown</a>` : ""}
          <button class="chip-btn view" onclick="event.stopPropagation(); openSlidePanelFromCurrent()">👁 Xem</button>
          <button class="chip-btn edit" onclick="event.stopPropagation(); PANEL_MODE='slide'; togglePanelEdit(true); openPanelFromCurrent()">✏️ Sửa nhanh</button>
          <button class="chip-btn special" onclick="event.stopPropagation(); openSlideViewer()" style="background: #3b82f6; color: white;">🎯 Xem slide</button>
        </div>
      </div>
    </div>
  `;

  addAIMessage(card);
}

/* ===== Panel opening functions ===== */
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

function openSlidePanelFromCurrent() {
  PANEL_MODE = "slide";
  renderPanelFromCurrent();
}
window.openSlidePanelFromCurrent = openSlidePanelFromCurrent;

function openSlidePanel(markdownString, downloadUrl) {
  if (typeof markdownString === "string" && markdownString.trim().length) {
    const formData = readJSONFromScript("eduForm", {});
    const info = extractSlideInfoFromForm(formData);
    saveSlideToStorage({ ...info, markdown: markdownString, downloadUrl: downloadUrl || "", formData });
  }
  openSlidePanelFromCurrent();
}
window.openSlidePanel = openSlidePanel;

/* ===== FIXED Initialization ===== */
function init() {
  console.log("🚀 [init] Starting optimized chat initialization...");

  const status = document.querySelector(".status-indicator span");
  const input = byId("userInput");
  const send = byId("sendBtn");

  // Batch data loading
  const formData = readJSONFromScript("eduForm", {});
  const markdown = readJSONFromScript("markdownContent", "");
  const mdDownloadUrl = readJSONFromScript("mdDownload", "");

  console.log("📊 [init] Data loaded:", { formData, markdownLength: markdown.length, mdDownloadUrl });

  // Process content types efficiently
  const contentTypes = formData.content_types || [];
  console.log("🎯 [init] Content types:", contentTypes);

  // Batch DOM updates
  requestAnimationFrame(() => {
    // Process lesson plan
    if (contentTypes.includes("lesson_plan") && markdown?.trim()) {
      console.log("📘 [init] Processing lesson plan...");
      showLessonCard(markdown, mdDownloadUrl || "", "", formData);
      PANEL_MODE = "plan";
      renderPanelFromCurrent();
    }

    // FIXED: Process quiz
    if (contentTypes.includes("quiz")) {
      console.log("📝 [init] Processing quiz...");
      const quizInjected = readJSONFromScript("quizContent", null);
      const quizDl = readJSONFromScript("quizDownload", "");
      let quizMd = null;

      console.log("📝 [init] Quiz injected data type:", typeof quizInjected);
      console.log("📝 [init] Quiz injected data:", quizInjected);

      if (quizInjected) {
        if (typeof quizInjected === "string" && quizInjected.trim() !== "") {
          quizMd = quizInjected;
          console.log("✅ [init] Quiz data is string, length:", quizMd.length);
        } else if (typeof quizInjected === "object" && quizInjected !== null) {
          console.log("📝 [init] Quiz object keys:", Object.keys(quizInjected));

          // FIXED: Kiểm tra các key phổ biến - sử dụng đúng biến quizInjected
          const possibleKeys = ['content', 'markdown', 'complete_markdown', 'quiz_markdown', 'data'];

          for (const key of possibleKeys) {
            const value = quizInjected[key]; // FIXED: Sử dụng quizInjected thay vì slideInjected
            if (value && typeof value === "string" && value.trim() !== "") {
              quizMd = value;
              console.log(`✅ Found quiz content in .${key} property`);
              break;
            }
          }

          // Nếu vẫn chưa tìm thấy, thử convert object thành JSON string
          if (!quizMd && Object.keys(quizInjected).length > 0) {
            try {
              quizMd = JSON.stringify(quizInjected, null, 2);
              console.log("⚠️ [init] Using stringified quiz object as fallback");
            } catch (e) {
              console.error("❌ [init] Cannot stringify quiz object:", e);
            }
          }
        }
      }

      // FIXED: Kiểm tra quizMd trước khi gọi .trim()
      if (quizMd && typeof quizMd === "string" && quizMd.trim() !== "") {
        console.log("✅ [init] Showing quiz card from server data");
        showQuizMdCard(quizMd, quizDl || "", "", formData);
      } else {
        console.warn("⚠️ [init] No valid quiz markdown found in quizContent script tag.");
        console.warn("⚠️ [init] quizMd type:", typeof quizMd, "value:", quizMd);
      }
    }

    // FIXED: Process slide plan
    if (contentTypes.includes("slide_plan")) {
      console.log("📊 [init] Processing slide plan...");
      const slideMarkdown = processSlideContentFromServer();

      if (slideMarkdown && typeof slideMarkdown === "string" && slideMarkdown.trim() !== "") {
        console.log("✅ [init] Showing slide card with processed data");
        const slideDl = readJSONFromScript("slideDownload", "");
        showSlideCard(slideMarkdown, slideDl, "", formData);

        // Only open slide panel if no lesson plan
        if (!contentTypes.includes("lesson_plan")) {
          console.log("📊 [init] Opening slide panel (no lesson plan present)");
          PANEL_MODE = "slide";
          renderPanelFromCurrent();
        }
      } else {
        console.warn("⚠️ [init] No valid slide content found");
      }
    }

    // UI setup
    if (status) status.textContent = "Sẵn sàng chat";
    if (input) {
      input.disabled = false;
      input.placeholder = "Nhập tin nhắn của bạn...";
    }
    if (send) send.disabled = false;

    sizeColumns();
  });

  // Event listeners with debouncing
  let inputTimer = null;
  input?.addEventListener("keypress", (e) => {
    if (e.key === "Enter" && !input.disabled) {
      if (inputTimer) clearTimeout(inputTimer);
      inputTimer = setTimeout(() => {
        const v = input.value.trim();
        if (!v) return;
        addUserMessage(escapeHTML(v));
        input.value = "";
      }, 50);
    }
  });

  send?.addEventListener("click", () => {
    const v = input.value?.trim();
    if (!v) return;
    addUserMessage(escapeHTML(v));
    input.value = "";
  });

  // Debounced resize listener
  window.addEventListener("resize", sizeColumns);

  console.log("✅ [init] Optimized initialization complete");
}

/* ===== Additional utility functions ===== */
function copySlideContent() {
  const data = currentSlideData;
  if (!data?.markdown) {
    toast("Không có nội dung slide để sao chép", true);
    return;
  }
  navigator.clipboard.writeText(data.markdown)
    .then(() => toast("📋 Đã sao chép nội dung slide!"))
    .catch(() => toast("Không thể sao chép", true));
}
window.copySlideContent = copySlideContent;

function closeSlidePanel() {
  closePlanPanel();
}
window.closeSlidePanel = closeSlidePanel;

// OPTIMIZED DOM ready handler
window.addEventListener("DOMContentLoaded", () => {
  console.log("🎯 [DOMContentLoaded] Starting optimized initialization...");

  // Initialize core functionality immediately
  init();
});

// Export functions for debugging
if (typeof window !== "undefined") {
  window.EduMateChat = {
    showLessonCard,
    showQuizMdCard,
    showSlideCard,
    openPlanPanel,
    openQuizPanelMarkdown,
    openSlidePanel,
    processSlideContentFromServer,
    renderMarkdownWithMath,
    PANEL_MODE,
    currentPlanData: () => currentPlanData,
    currentQuizData: () => currentQuizData,
    currentSlideData: () => currentSlideData
  };
}
