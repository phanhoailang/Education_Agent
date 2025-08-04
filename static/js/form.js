// --- static/js/form.js ---
// Submit thật về /process + validate + UI upload + toast
const DEBUG = true;
const log = (...args) => DEBUG && console.log("[form]", ...args);

// Biến toàn cục lưu file người dùng đã chọn (kéo–thả hoặc input)
let selectedFiles = [];
let isSubmitting = false;

document.addEventListener("DOMContentLoaded", () => {
  log("loaded");
  initializeForm();
  initializeFileUpload();
  initializeFormValidation();
});

/* =========================
 *  INIT FORM + EVENTS
 * ========================= */
function initializeForm() {
  const form = document.getElementById("eduForm");
  if (!form) {
    console.error("#eduForm not found");
    return;
  }

  form.addEventListener("submit", handleFormSubmit);

  // Hiệu ứng focus/blur
  document.querySelectorAll(".input, .select, .textarea").forEach((el) => {
    el.addEventListener("focus", function () {
      this.classList.add("focused");
    });
    el.addEventListener("blur", function () {
      this.classList.remove("focused");
      this.classList.toggle("has-value", !!this.value.trim());
    });
  });
}

/* =========================
 *  SUBMIT HANDLER (REAL)
 * ========================= */
async function handleFormSubmit(e) {
  e.preventDefault();

  if (isSubmitting) return;
  if (!validateForm()) return;

  const form = e.currentTarget;
  const submitBtn = form.querySelector(".submit-btn");
  const originalHTML = submitBtn ? submitBtn.innerHTML : "";

  // Loading state
  if (submitBtn) {
    submitBtn.innerHTML =
      '<i class="fas fa-spinner fa-spin"></i><span>Đang xử lý...</span>';
    submitBtn.disabled = true;
    submitBtn.classList.add("loading");
  }
  isSubmitting = true;

  try {
    // Gom dữ liệu vào FormData
    const fd = new FormData(form);

    // Gỡ file cũ (nếu input đã có) và add từ selectedFiles
    fd.delete("files[]");
    selectedFiles.forEach((f) => fd.append("files[]", f));

    // Debug: in các field (ẩn tên/size file)
    if (DEBUG) {
      const dump = Array.from(fd.entries()).map(([k, v]) =>
        v instanceof File ? [k, `${v.name} (${v.size}B)`] : [k, v]
      );
      log("payload", dump);
    }

    // Gửi lên server
    const resp = await fetch("/process", {
      method: "POST",
      body: fd, // KHÔNG set Content-Type -> để browser tự set multipart/form-data
      redirect: "follow",
    });

    log("response", resp.status, resp.redirected ? "redirected" : "");

    if (resp.redirected) {
      // Flask redirect() -> trình duyệt tự điều hướng
      window.location.href = resp.url;
      return;
    }

    if (resp.ok) {
      // Có thể server đã trả HTML của /chat; để chắc ăn, điều hướng thẳng:
      window.location.href = "/chat";
      return;
    }

    // Lỗi: đọc JSON nếu có
    let errText = `${resp.status} ${resp.statusText}`;
    try {
      const j = await resp.json();
      errText = j.details || j.error || errText;
    } catch (_) {}
    throw new Error(errText);
  } catch (err) {
    console.error("Submit error:", err);
    showErrorMessage("Có lỗi khi gửi form: " + (err?.message || err));
  } finally {
    // Khôi phục nút
    setTimeout(() => {
      if (submitBtn) {
        submitBtn.innerHTML = originalHTML;
        submitBtn.disabled = false;
        submitBtn.classList.remove("loading");
      }
      isSubmitting = false;
    }, 400);
  }
}

/* =========================
 *  VALIDATION
 * ========================= */
function validateForm() {
  let ok = true;

  const required = [
    { id: "grade", name: "Khối lớp" },
    { id: "subject", name: "Môn học" },
    { id: "topic", name: "Chủ đề bài học" },
  ];

  required.forEach(({ id, name }) => {
    const el = document.getElementById(id);
    if (!el || !el.value.trim()) {
      showFieldError(el, `${name} là bắt buộc`);
      ok = false;
    } else {
      clearFieldError(el);
    }
  });

  // Ít nhất một loại nội dung
  const checks = document.querySelectorAll('input[name="content_type[]"]');
  const picked = Array.from(checks).some((c) => c.checked);
  const err = document.getElementById("content-error");
  if (!picked) {
    if (err) {
      err.style.display = "block";
      err.scrollIntoView({ behavior: "smooth", block: "center" });
    }
    ok = false;
  } else if (err) {
    err.style.display = "none";
  }

  return ok;
}

function showFieldError(el, message) {
  if (!el) return;
  el.classList.add("error");
  const old = el.parentNode.querySelector(".field-error");
  if (old) old.remove();

  const n = document.createElement("div");
  n.className = "field-error";
  n.innerHTML = `<i class="fas fa-exclamation-circle"></i> ${message}`;
  n.style.cssText =
    "color: var(--error); font-size:.875rem; margin-top:.5rem; display:flex; align-items:center; gap:.5rem;";
  el.parentNode.appendChild(n);
}

function clearFieldError(el) {
  if (!el) return;
  el.classList.remove("error");
  const n = el.parentNode.querySelector(".field-error");
  if (n) n.remove();
}

function initializeFormValidation() {
  // Ẩn lỗi khi tick checkbox
  document.querySelectorAll('input[name="content_type[]"]').forEach((cb) => {
    cb.addEventListener("change", () => {
      const checks = document.querySelectorAll('input[name="content_type[]"]');
      const picked = Array.from(checks).some((c) => c.checked);
      const err = document.getElementById("content-error");
      if (picked && err) err.style.display = "none";
    });
  });

  // Realtime required
  document.querySelectorAll("#grade, #subject, #topic").forEach((input) => {
    input.addEventListener("blur", function () {
      if (!this.value.trim()) {
        const label =
          (this.previousElementSibling && this.previousElementSibling.textContent) ||
          "Trường này";
        showFieldError(this, `${label.replace("*", "").trim()} là bắt buộc`);
      } else {
        clearFieldError(this);
      }
    });
    input.addEventListener("input", function () {
      if (this.value.trim()) clearFieldError(this);
    });
  });
}

/* =========================
 *  UPLOAD (kéo–thả + input)
 * ========================= */
function initializeFileUpload() {
  const fileInput = document.getElementById("files");
  const fileUpload = document.getElementById("fileUpload");
  const fileList = document.getElementById("fileList");

  if (fileInput) {
    fileInput.addEventListener("change", (e) => {
      if (e.target.files?.length) addFiles(e.target.files);
    });
  }
  if (!fileUpload) return;

  fileUpload.addEventListener("dragover", (e) => {
    e.preventDefault();
    fileUpload.classList.add("drag-over");
  });
  fileUpload.addEventListener("dragleave", (e) => {
    e.preventDefault();
    if (!fileUpload.contains(e.relatedTarget)) fileUpload.classList.remove("drag-over");
  });
  fileUpload.addEventListener("drop", (e) => {
    e.preventDefault();
    fileUpload.classList.remove("drag-over");
    const files = e.dataTransfer?.files;
    if (files?.length) addFiles(files);
  });

  // Helper render list
  function renderList() {
    if (!fileList) return;
    fileList.innerHTML = "";
    if (!selectedFiles.length) return;

    selectedFiles.forEach((f, i) => {
      const div = document.createElement("div");
      div.className = "file-item";
      div.innerHTML = `
        <i class="${getFileIcon(f.type)} file-icon"></i>
        <div class="file-info">
          <div class="file-name">${f.name}</div>
          <div class="file-size">${formatFileSize(f.size)}</div>
        </div>
        <button class="delete-btn" title="Xoá" data-i="${i}">
          <i class="fas fa-times"></i>
        </button>
      `;
      div.querySelector(".delete-btn").addEventListener("click", (ev) => {
        ev.stopPropagation();
        selectedFiles.splice(i, 1);
        renderList();
      });
      fileList.appendChild(div);
    });
  }

  // expose để addFiles gọi
  fileUpload._renderList = renderList;
}

function addFiles(files) {
  const allowed = [".pdf", ".doc", ".docx", ".ppt", ".pptx", ".txt", ".jpg", ".png"];
  const maxSize = 10 * 1024 * 1024;

  const added = [];
  Array.from(files).forEach((f) => {
    const ext = "." + (f.name.split(".").pop() || "").toLowerCase();

    if (!allowed.includes(ext)) {
      showErrorMessage(`File "${f.name}" không được hỗ trợ.`);
      return;
    }
    if (f.size > maxSize) {
      showErrorMessage(`"${f.name}" quá lớn (tối đa 10MB).`);
      return;
    }
    const exists = selectedFiles.some((x) => x.name === f.name && x.size === f.size);
    if (!exists) {
      selectedFiles.push(f);
      added.push(f);
    }
  });

  // Re-render list nếu có
  const fileUpload = document.getElementById("fileUpload");
  if (fileUpload && typeof fileUpload._renderList === "function") {
    fileUpload._renderList();
  }

  if (added.length) showSuccessMessage(`Đã thêm ${added.length} file`);
}

/* =========================
 *  TOAST + UTILITIES
 * ========================= */
function showSuccessMessage(msg = "Thành công!", ms = 2000) {
  showToast(msg, true, ms);
}
function showErrorMessage(msg = "Có lỗi!", ms = 3000) {
  showToast(msg, false, ms);
}
function showToast(message, ok, ms) {
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.style.cssText =
    "position:fixed;top:20px;right:20px;padding:12px 16px;border-radius:10px;color:#fff;font-weight:600;z-index:9999;box-shadow:0 10px 18px rgba(0,0,0,.12);transition:.25s;opacity:0;transform:translateY(-6px);";
  toast.style.background = ok
    ? "linear-gradient(135deg,#10b981,#059669)"
    : "linear-gradient(135deg,#ef4444,#dc2626)";
  toast.innerHTML = ok
    ? `<i class="fas fa-check-circle"></i> ${message}`
    : `<i class="fas fa-exclamation-circle"></i> ${message}`;
  document.body.appendChild(toast);
  requestAnimationFrame(() => {
    toast.style.opacity = "1";
    toast.style.transform = "translateY(0)";
  });
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(-6px)";
    setTimeout(() => toast.remove(), 250);
  }, ms);
}

function getFileIcon(type) {
  if (type === "application/pdf") return "fas fa-file-pdf";
  if (type.includes("msword") || type.includes("officedocument.wordprocessingml"))
    return "fas fa-file-word";
  if (type.includes("powerpoint") || type.includes("presentationml"))
    return "fas fa-file-powerpoint";
  if (type === "text/plain") return "fas fa-file-lines";
  if (type.startsWith("image/")) return "fas fa-file-image";
  return "fas fa-file";
}
function formatFileSize(n) {
  if (!n) return "0 Bytes";
  const k = 1024;
  const u = ["Bytes", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(n) / Math.log(k));
  return `${(n / Math.pow(k, i)).toFixed(2)} ${u[i]}`;
}

// Some minimal helpers for animations
const style = document.createElement("style");
style.textContent = `
  .submit-btn.loading { opacity:.8; cursor:not-allowed; }
  .file-info{flex:1;display:flex;flex-direction:column;gap:.25rem}
  .file-name{font-size:.875rem;word-break:break-all}
  .file-size{font-size:.75rem;opacity:.7}
`;
document.head.appendChild(style);
