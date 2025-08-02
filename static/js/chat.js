"use strict";

/**
 * chat.js — phiên bản hoàn chỉnh
 * - Đọc formData, markdownContent, mdDownload từ <script type="application/json">.
 * - Render Markdown bằng marked.js + DOMPurify (nếu có), fallback khi thiếu.
 * - Hiển thị card nội dung kế hoạch + link tải file .md.
 * - Cấu trúc code tách rõ: utils, renderers, UI, events.
 */

/* ==========================
 *  UTILS
 * ========================== */
const $ = (sel) => document.querySelector(sel);
const byId = (id) => document.getElementById(id);

function escapeHTML(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function readJSONFromScript(scriptId, fallback = null) {
  const el = byId(scriptId);
  if (!el) return fallback;
  const raw = (el.textContent || "").trim();
  if (!raw) return fallback;
  try {
    return JSON.parse(raw);
  } catch (err) {
    console.error(`[JSON] Parse error @#${scriptId}:`, err);
    console.log(`[JSON] Raw content @#${scriptId}:`, raw);
    return fallback;
  }
}

function addAIMessage(contentHTML) {
  const chatMessages = byId("chatMessages");
  if (!chatMessages) return;
  const messageDiv = document.createElement("div");
  messageDiv.className = "message ai";
  messageDiv.innerHTML = `
    <div class="message-avatar">🤖</div>
    <div class="message-content">${contentHTML}</div>
  `;
  chatMessages.appendChild(messageDiv);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function addUserMessage(contentHTML) {
  const chatMessages = byId("chatMessages");
  if (!chatMessages) return;
  const messageDiv = document.createElement("div");
  messageDiv.className = "message user";
  messageDiv.innerHTML = `
    <div class="message-avatar">👤</div>
    <div class="message-content">${contentHTML}</div>
  `;
  chatMessages.appendChild(messageDiv);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

/* ==========================
 *  MARKDOWN RENDERERS
 * ========================== */

/** Fallback khi không có marked + DOMPurify: render đơn giản nhưng an toàn */
function simpleMarkdownFallback(md) {
  if (!md) return "";
  let out = escapeHTML(md);

  // Code block ```...```
  out = out.replace(/```([\s\S]*?)```/g, (_m, code) => {
    return `<pre style="white-space:pre-wrap;overflow:auto;"><code>${code}</code></pre>`;
  });

  // Headings (h3 -> h1 để tránh đè nhau)
  out = out.replace(/^###\s+(.+)$/gm, `<h3 style="margin:14px 0 8px 0;">$1</h3>`);
  out = out.replace(/^##\s+(.+)$/gm, `<h2 style="margin:16px 0 10px 0;">$1</h2>`);
  out = out.replace(/^#\s+(.+)$/gm, `<h1 style="margin:18px 0 12px 0;">$1</h1>`);

  // Bold / Italic / Link
  out = out.replace(/\*\*(.+?)\*\*/g, `<strong>$1</strong>`);
  out = out.replace(/(^|[^\*])\*(?!\s)(.+?)(?!\s)\*(?!\*)/g, `$1<em>$2</em>`);
  out = out.replace(/\[([^\]]+?)\]\((https?:\/\/[^\s)]+)\)/g, `<a href="$2" target="_blank" rel="noopener">$1</a>`);

  // Bullet list (đơn giản theo dòng)
  const lines = out.split(/\n/);
  let html = [];
  let inList = false;

  for (let i = 0; i < lines.length; i++) {
    const ln = lines[i];
    const bulletMatch = ln.match(/^(?:[\-\*]\s+)(.+)$/);

    if (bulletMatch) {
      if (!inList) {
        html.push(`<ul style="margin:6px 0 10px 18px;padding:0;">`);
        inList = true;
      }
      html.push(`<li>${bulletMatch[1]}</li>`);
    } else {
      if (inList && ln.trim() !== "") {
        html.push(`</ul>`);
        inList = false;
      }
      html.push(ln);
    }
  }
  if (inList) html.push(`</ul>`);

  out = html.join("\n").replace(/\n/g, "<br>");
  return out;
}

/** Render Markdown bằng marked + DOMPurify nếu có, fallback nếu thiếu */
function renderMarkdownHTML(md) {
  if (!md) return "";
  try {
    if (window.marked && window.DOMPurify) {
      marked.setOptions({ gfm: true, breaks: true, headerIds: true, mangle: false });
      const rawHtml = marked.parse(md);
      const safeHtml = DOMPurify.sanitize(rawHtml, {
        ALLOWED_TAGS: [
          "h1","h2","h3","h4","h5","h6","p","ul","ol","li","strong","em",
          "a","code","pre","blockquote","hr","br","table","thead","tbody",
          "tr","th","td","span","div"
        ],
        ALLOWED_ATTR: ["href","name","target","rel","colspan","rowspan","align"]
      });
      return safeHtml;
    }
  } catch (e) {
    console.error("[MD] Lỗi render marked/DOMPurify:", e);
  }
  // Fallback đơn giản
  return simpleMarkdownFallback(md);
}

/* ==========================
 *  UI HELPERS
 * ========================== */
function showLessonCard(markdown, downloadUrl = "", fileName = "") {
  if (!markdown || !markdown.trim()) {
    addAIMessage(`<strong>⚠️ Đã xử lý xong nhưng chưa nhận được nội dung Markdown.</strong><br>Vui lòng thử lại hoặc kiểm tra log.`);
    return;
  }
  const html = renderMarkdownHTML(markdown);
  const meta = fileName
    ? `<div style="font-size:12px;color:#64748b;margin:6px 0 2px;">Nguồn file: ${escapeHTML(fileName)}</div>`
    : "";
  const link = downloadUrl
    ? `<div style="margin-top:8px;">⬇️ <a href="${escapeHTML(downloadUrl)}" target="_blank" rel="noopener">Tải file Markdown</a></div>`
    : "";

  const card = `
    <strong>📘 Kế hoạch bài giảng:</strong>
    ${meta}
    <div style="background:#f8f9fa;padding:18px;border-radius:12px;margin-top:10px;border-left:4px solid #007bff;max-height:420px;overflow:auto;">
      ${html}
    </div>
    ${link}
  `;
  addAIMessage(card);
}

function showFormSummary(formData) {
  if (!formData || !Object.keys(formData).length) {
    addAIMessage("⚠️ Không nhận được dữ liệu từ form. Vui lòng thử lại.");
    return;
  }
  const message = `
    <strong>✅ Đã nhận dữ liệu từ form!</strong><br>
    <ul>
      <li><strong>Khối lớp:</strong> ${escapeHTML(formData.grade || "Không xác định")}</li>
      <li><strong>Bộ sách giáo khoa:</strong> ${escapeHTML(formData.textbook || "Không xác định")}</li>
      <li><strong>Môn học:</strong> ${escapeHTML(formData.subject || "Không xác định")}</li>
      <li><strong>Chủ đề:</strong> ${escapeHTML(formData.topic || "Không xác định")}</li>
      <li><strong>Thời gian:</strong> ${formData.duration ? escapeHTML(formData.duration) + " phút" : "Không xác định"}</li>
      <li><strong>Loại nội dung:</strong> ${
        Array.isArray(formData.content_types) && formData.content_types.length
          ? escapeHTML(formData.content_types.join(", "))
          : "Không xác định"
      }</li>
      <li><strong>Phong cách giảng dạy:</strong> ${escapeHTML(formData.teaching_style || "Không xác định")}</li>
      <li><strong>Mức độ khó:</strong> ${escapeHTML(formData.difficulty || "Không xác định")}</li>
      <li><strong>Yêu cầu bổ sung:</strong> ${escapeHTML(formData.additional_requirements || "Không có")}</li>
      <li><strong>File đính kèm:</strong> ${
        Array.isArray(formData.files) && formData.files.length
          ? escapeHTML(formData.files.join(", "))
          : "Không có"
      }</li>
    </ul>
  `;
  addAIMessage(message);
}

function injectEnhanceStyles() {
  // Một số CSS nhỏ cho bảng/code để đọc dễ hơn (nếu chat.css chưa có)
  const css = `
    .message .message-content table { border-collapse: collapse; width: 100%; margin: 8px 0 12px; }
    .message .message-content th, .message .message-content td { border: 1px solid #e5e7eb; padding: 6px 8px; text-align: left; }
    .message .message-content pre { background: rgba(15,23,42,0.05); padding: 10px; border-radius: 8px; overflow: auto; }
    .message .message-content code { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono","Courier New", monospace; }
    @keyframes slideOut { from {opacity:1;transform:translateY(0);} to {opacity:0;transform:translateY(-20px);} }
  `;
  const style = document.createElement("style");
  style.setAttribute("data-from", "chat-js-enhance");
  style.textContent = css;
  document.head.appendChild(style);
}

/* ==========================
 *  INIT
 * ========================== */
function initUI() {
  const statusIndicator = $(".status-indicator span");
  const inputField = $(".input-field");
  const sendBtn = $(".send-btn");

  // Đọc dữ liệu từ server đã nhúng
  const formData = readJSONFromScript("eduForm", {});
  const markdownContent = readJSONFromScript("markdownContent", "");
  const mdDownloadUrl = readJSONFromScript("mdDownload", "");
  // (tuỳ chọn) nếu bạn có thêm script id="mdMeta" để gửi basename:
  const mdMeta = readJSONFromScript("mdMeta", {}); // { basename: "lesson_plan_..." }
  const mdFileName = (mdMeta && mdMeta.basename) || ""; // sẽ trống nếu không truyền

  console.log("[JS] formData:", formData);
  console.log("[JS] markdown length:", (markdownContent && markdownContent.length) || 0);
  if (mdDownloadUrl) console.log("[JS] download url:", mdDownloadUrl);

  // Hiển thị markdown + link tải
  if (markdownContent) {
    showLessonCard(markdownContent, mdDownloadUrl || "", mdFileName);
  } else {
    addAIMessage(`<strong>⚠️ Chưa nhận được nội dung Markdown.</strong><br>Vui lòng thử lại hoặc kiểm tra log backend.`);
  }

  // Thông tin tóm tắt form
  showFormSummary(formData);

  // Cập nhật trạng thái UI
  if (statusIndicator) statusIndicator.textContent = "Sẵn sàng chat";
  if (inputField) {
    inputField.disabled = false;
    inputField.placeholder = "Nhập tin nhắn của bạn...";
  }
  if (sendBtn) sendBtn.disabled = false;
}

/* ==========================
 *  EVENTS
 * ========================== */
function sendMessage() {
  const inputField = $(".input-field");
  if (!inputField) return;

  const message = inputField.value.trim();
  if (!message) return;

  addUserMessage(escapeHTML(message));
  inputField.value = "";

  // Mô phỏng AI phản hồi
  setTimeout(() => {
    addAIMessage("Cảm ơn bạn! Tôi đang xử lý và sẽ trả lời bạn ngay…");
  }, 700);
}

function attachEventHandlers() {
  byId("voiceBtn")?.addEventListener("click", function () {
    byId("chatBtn")?.classList.remove("active");
    this.classList.add("active");
  });

  byId("chatBtn")?.addEventListener("click", function () {
    byId("voiceBtn")?.classList.remove("active");
    this.classList.add("active");
  });

  $(".input-field")?.addEventListener("keypress", function (e) {
    if (e.key === "Enter" && !this.disabled) sendMessage();
  });

  $(".send-btn")?.addEventListener("click", sendMessage);
}

// Cho nút "Quay lại" trong template
function goBack() {
  window.history.back();
}
window.goBack = goBack;

/* ==========================
 *  BOOT
 * ========================== */
window.addEventListener("DOMContentLoaded", () => {
  // Độ trễ nhỏ để tạo cảm giác "đang xử lý" (tuỳ chỉnh 300 → 3000ms nếu muốn)
  setTimeout(() => {
    try {
      injectEnhanceStyles();
      initUI();
      attachEventHandlers();
    } catch (err) {
      console.error("[INIT] Lỗi khởi tạo UI:", err);
      addAIMessage("⚠️ Có lỗi khi khởi tạo giao diện. Vui lòng kiểm tra console.");
    }
  }, 300);
});
