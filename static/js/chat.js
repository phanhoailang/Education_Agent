"use strict";

/**
 * Chat JS – Canvas Plan ở cột phải (Chat:Plan = 40:60 do CSS)
 * - Nhấp card → chia ngang và hiển thị Plan ở bên phải
 * - Cả 2 cột luôn cao bằng nhau theo viewport (kể cả KHI CHƯA mở Plan)
 * - Plan cuộn độc lập trong panel
 * - Chỉnh sửa ngay trong panel (không chuyển trang)
 */

const $ = (sel) => document.querySelector(sel);
const byId = (id) => document.getElementById(id);

/* ===== Utils ===== */
function readJSONFromScript(id, fallback = null) {
  try{
    const el = byId(id); if(!el) return fallback;
    const raw = (el.textContent || "").trim(); if(!raw) return fallback;
    return JSON.parse(raw);
  }catch{ return fallback; }
}
function escapeHTML(str){
  if(str===null || str===undefined) return "";
  return String(str).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}
function renderMarkdownHTML(md){
  if(!md) return "";
  try{
    if(window.marked && window.DOMPurify){
      marked.setOptions({ gfm:true, breaks:true, headerIds:true, mangle:false });
      const raw = marked.parse(md);
      return DOMPurify.sanitize(raw);
    }
  }catch{}
  return "<pre style='white-space:pre-wrap'>" + escapeHTML(md) + "</pre>";
}

/* ===== State + Storage ===== */
let currentPlanData = null;
let PANEL_EDITING = false;

function savePlanToStorage(plan){
  const planToSave = {
    id: plan.id || Date.now().toString(),
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
  if(i>=0) list[i] = planToSave; else list.unshift(planToSave);
  localStorage.setItem("planList", JSON.stringify(list));
  currentPlanData = planToSave;
  return planToSave;
}
function extractPlanInfoFromForm(form){
  const topic = form?.topic || form?.title || form?.lesson || "";
  const subj  = form?.subject || "Chưa xác định";
  const grade = form?.grade ? `Lớp ${form.grade}` : "Chưa xác định";
  const dur   = form?.duration ? `${form.duration} phút` : "45 phút";
  const title = topic ? `Kế hoạch bài giảng: ${topic}` : `Kế hoạch bài giảng: ${subj}`;
  return { title, subject:subj, grade, duration:dur };
}

/* ===== Chat helpers ===== */
function addAIMessage(html){
  const wrap = byId("chatMessages");
  const div = document.createElement("div");
  div.className = "message ai";
  div.innerHTML = `<div class="message-avatar">🤖</div><div class="message-content">${html}</div>`;
  wrap.appendChild(div);
  wrap.scrollTop = wrap.scrollHeight;
  // Giữ chiều cao đầy màn hình kể cả khi thêm tin nhắn
  requestAnimationFrame(sizeColumns);
}
function addUserMessage(html){
  const wrap = byId("chatMessages");
  const div = document.createElement("div");
  div.className = "message user";
  div.innerHTML = `<div class="message-avatar">👤</div><div class="message-content">${html}</div>`;
  wrap.appendChild(div);
  wrap.scrollTop = wrap.scrollHeight;
  requestAnimationFrame(sizeColumns);
}

/* ===== Equal height logic (QUAN TRỌNG) ===== */
function ensurePanelInsideGrid(){
  const page = byId("page");
  const panelCol = byId("panelCol");
  if(page && panelCol && panelCol.parentElement !== page){
    page.appendChild(panelCol);
  }
}
function forceTwoColumns(){
  const page = byId("page");
  if(!page) return;
  document.body.classList.add("panel-open");
  page.classList.add("is-open");
  const cols = getComputedStyle(page).gridTemplateColumns;
  const looksOneCol = !cols || cols.split(" ").length < 2;
  if(looksOneCol){
    page.style.display = "grid";
    page.style.gridTemplateColumns = "minmax(0, 2fr) minmax(0, 3fr)";
  }
}

/* TÍNH CHIỀU CAO KHẢ DỤNG:
   - Lấy mép dưới của header
   - Trừ khỏi window.innerHeight
   - Áp dụng cho: khối chat + panel (nếu đang mở)
   => Giúp: khi CHƯA mở Plan, Chat vẫn cao đầy màn hình */
function sizeColumns(){
  const header = document.querySelector(".header");
  const headerBottom = header ? header.getBoundingClientRect().bottom : 0;
  const avail = Math.max(360, Math.floor(window.innerHeight - headerBottom - 16)); // 16px bottom gap

  const chatBox = document.querySelector(".col-chat .chat-container");
  if(chatBox){
    chatBox.style.height = `${avail}px`;
    chatBox.style.maxHeight = `${avail}px`;
  }

  const panel = byId("planPanel");
  if(panel && panel.getAttribute("aria-hidden") !== "true"){
    panel.style.height = `${avail}px`;
    panel.style.maxHeight = `${avail}px`;
  }
}

/* ===== Right Panel (Canvas) ===== */
function renderPanelViewer(){
  const body = byId("planPanelBody");
  if(!body || !currentPlanData) return;
  body.innerHTML = `
    <article id="panelViewer" class="doc">${renderMarkdownHTML(currentPlanData.markdown)}</article>
    <textarea id="panelEditor" class="panel-editor" style="display:none;width:100%;min-height:60vh;border:1px solid #e5e7eb;border-radius:12px;padding:12px;background:#fff;"></textarea>
  `;
  PANEL_EDITING = false;
  byId("panelSaveBtn")?.style && (byId("panelSaveBtn").style.display = "none");
  byId("panelCancelBtn")?.style && (byId("panelCancelBtn").style.display = "none");
  byId("panelEditBtn")?.style && (byId("panelEditBtn").style.display = "inline-flex");
}
function renderPlanPanelFromCurrent(){
  if(!currentPlanData) return;

  ensurePanelInsideGrid();
  forceTwoColumns();
  byId("planPanel")?.setAttribute("aria-hidden","false");

  const titleEl = byId("planPanelTitle");
  if(titleEl) titleEl.textContent = currentPlanData.title || "Kế hoạch bài giảng";

  const dlEl = byId("panelDownloadLink");
  if(dlEl){
    if(currentPlanData.downloadUrl){
      dlEl.href = currentPlanData.downloadUrl;
      dlEl.style.display = "inline-flex";
    }else{
      dlEl.removeAttribute("href");
      dlEl.style.display = "none";
    }
  }

  renderPanelViewer();
  // đặt chiều cao sau khi render DOM
  requestAnimationFrame(sizeColumns);
}
window.openPlanPanelFromCurrent = renderPlanPanelFromCurrent;

function openPlanPanel(markdownString, downloadUrl){
  if(typeof markdownString === "string" && markdownString.trim().length){
    const formData = readJSONFromScript("eduForm", {});
    const info = extractPlanInfoFromForm(formData);
    savePlanToStorage({ ...info, markdown: markdownString, downloadUrl: downloadUrl || "", formData });
  }
  renderPlanPanelFromCurrent();
}
window.openPlanPanel = openPlanPanel;

function closePlanPanel(){
  const page = byId("page");
  document.body.classList.remove("panel-open");
  page?.classList.remove("is-open");
  if(page){ page.style.gridTemplateColumns = ""; page.style.display = ""; }

  // KHÔNG xoá height của chat — để khi đóng panel, Chat vẫn cao đầy màn hình
  const panel = byId("planPanel");
  if(panel){ panel.style.height=""; panel.style.maxHeight=""; }
  byId("planPanel")?.setAttribute("aria-hidden","true");

  requestAnimationFrame(sizeColumns);
}
window.closePlanPanel = closePlanPanel;

/* ---- Inline Editing in Panel ---- */
function togglePanelEdit(forceState){
  const viewer = byId("panelViewer");
  const editor = byId("panelEditor");
  if(!viewer || !editor || !currentPlanData) return;

  if(typeof forceState === "boolean"){ PANEL_EDITING = forceState; }
  else{ PANEL_EDITING = !PANEL_EDITING; }

  if(PANEL_EDITING){
    editor.value = currentPlanData.markdown || "";
    viewer.style.display = "none";
    editor.style.display = "block";
    byId("panelSaveBtn").style.display = "inline-flex";
    byId("panelCancelBtn").style.display = "inline-flex";
    byId("panelEditBtn").style.display = "none";
  }else{
    viewer.style.display = "block";
    editor.style.display = "none";
    byId("panelSaveBtn").style.display = "none";
    byId("panelCancelBtn").style.display = "none";
    byId("panelEditBtn").style.display = "inline-flex";
  }
  requestAnimationFrame(sizeColumns);
}
window.togglePanelEdit = togglePanelEdit;

function savePanelEdit(){
  const editor = byId("panelEditor");
  if(!currentPlanData || !editor) return;
  currentPlanData.markdown = editor.value || "";

  sessionStorage.setItem("currentPlan", JSON.stringify(currentPlanData));
  const list = JSON.parse(localStorage.getItem("planList") || "[]");
  const i = list.findIndex(p => p.id === currentPlanData.id);
  if(i>=0) list[i] = currentPlanData; else list.unshift(currentPlanData);
  localStorage.setItem("planList", JSON.stringify(list));

  const viewer = byId("panelViewer");
  if(viewer) viewer.innerHTML = renderMarkdownHTML(currentPlanData.markdown);
  togglePanelEdit(false);
  toast("Đã lưu bản chỉnh sửa");
}
window.savePanelEdit = savePanelEdit;

/* ---- Misc ---- */
function switchTab(tab){
  document.querySelectorAll(".nav-tab").forEach(b=>{
    const isActive = b.textContent.trim().toLowerCase().includes(tab);
    b.classList.toggle("active", isActive);
  });
  if(tab==="chat"){
    document.querySelector(".col-chat")?.scrollIntoView({ behavior:"smooth", block:"start" });
  }
}
window.switchTab = switchTab;

function toast(msg, error=false){
  const t = document.createElement("div");
  t.style.cssText = `position:fixed;top:20px;right:20px;background:${error?"#ef4444":"#16a34a"};color:#fff;padding:10px 14px;border-radius:10px;z-index:1000;transform:translateY(-8px);opacity:0;transition:all .2s`;
  t.textContent = msg; document.body.appendChild(t);
  requestAnimationFrame(()=>{ t.style.opacity="1"; t.style.transform="translateY(0)"; });
  setTimeout(()=>{ t.style.opacity="0"; t.style.transform="translateY(-8px)"; setTimeout(()=>t.remove(),180); },1800);
}
window.copyPlanContent = function(){
  if(!currentPlanData?.markdown) return;
  navigator.clipboard.writeText(currentPlanData.markdown)
    .then(()=>toast("Đã sao chép nội dung!"))
    .catch(()=>toast("Không thể sao chép", true));
};
window.openLessonPlanPage = function(){
  const plan = currentPlanData;
  const url = plan?.id ? `/lesson-plan?planId=${encodeURIComponent(plan.id)}` : "/lesson-plan";
  window.open(url, "_blank");
};
function goBack(){ window.history.back(); }
window.goBack = goBack;

/* ===== Card trong chat ===== */
function showLessonCard(markdown, downloadUrl = "", fileName = "", formData = {}){
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
          <button class="chip-btn edit" onclick="event.stopPropagation(); togglePanelEdit(true); openPlanPanelFromCurrent()">✏️ Sửa nhanh</button>
        </div>
      </div>
    </div>
  `;
  addAIMessage(card);
}

/* ===== Init ===== */
function init(){
  const status = document.querySelector(".status-indicator span");
  const input  = byId("userInput");
  const send   = byId("sendBtn");

  const formData      = readJSONFromScript("eduForm", {});
  const markdown      = readJSONFromScript("markdownContent", "");
  const mdDownloadUrl = readJSONFromScript("mdDownload", "");

  if (markdown && markdown.trim()) {
    showLessonCard(markdown, mdDownloadUrl || "", "", formData);
    renderPlanPanelFromCurrent();
  } else {
    try {
      const ss = JSON.parse(sessionStorage.getItem("currentPlan") || "null");
      if (ss && ss.markdown) {
        currentPlanData = ss;
        showLessonCard(ss.markdown, ss.downloadUrl || "", ss.fileName || "", ss.formData || {});
        // chưa mở plan thì vẫn set chiều cao đầy màn hình
        requestAnimationFrame(sizeColumns);
      } else {
        addAIMessage(`<strong>⚠️ Chưa nhận được nội dung Markdown.</strong>`);
        requestAnimationFrame(sizeColumns);
      }
    } catch {
      addAIMessage(`<strong>⚠️ Chưa nhận được nội dung Markdown.</strong>`);
      requestAnimationFrame(sizeColumns);
    }
  }

  if(status) status.textContent = "Sẵn sàng chat";
  if(input){ input.disabled = false; input.placeholder = "Nhập tin nhắn của bạn..."; }
  if(send) send.disabled = false;

  // luôn giữ chiều cao hợp lý
  sizeColumns();
  window.addEventListener("resize", sizeColumns);

  input?.addEventListener("keypress", (e)=>{
    if(e.key === "Enter" && !input.disabled){
      const v = input.value.trim(); if(!v) return;
      addUserMessage(escapeHTML(v));
      input.value = "";
    }
  });
  send?.addEventListener("click", ()=>{
    const v = input.value?.trim(); if(!v) return;
    addUserMessage(escapeHTML(v));
    input.value = "";
  });
}
window.addEventListener("DOMContentLoaded", init);
