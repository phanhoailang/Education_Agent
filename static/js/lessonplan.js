// static/js/lessonplan.js
(function () {
  "use strict";

  let LIST = [];
  let CURRENT = null;
  let EDITING = false;

  const $ = (sel) => document.querySelector(sel);
  const byId = (id) => document.getElementById(id);

  function showToast(text, ok = true, type = 'normal') {
    const n = byId("toast");
    if (!n) return;
    n.textContent = text;
    
    // Reset classes
    n.className = "toast";
    
    if (type === 'slide') {
      n.classList.add("slide-toast");
    } else if (!ok) {
      n.classList.add("error");
    }
    
    n.classList.add("show");
    setTimeout(() => n.classList.remove("show"), 3000);
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
      if (CURRENT?.downloadUrl) { 
        dlBtn.href = CURRENT.downloadUrl; 
        dlBtn.style.display = "inline-flex"; 
      } else { 
        dlBtn.removeAttribute("href"); 
        dlBtn.style.display = CURRENT ? "inline-flex" : "none"; 
      }
    }

    // Enable/disable slide button
    const slideBtn = byId("createSlideBtn");
    if (slideBtn) {
      slideBtn.disabled = !CURRENT;
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
    byId("createSlideBtn").disabled = true;
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

  // === SLIDE FUNCTIONALITY ===

  function countEstimatedSlides(markdown) {
    if (!markdown) return 0;
    
    // Count headers (H1, H2, H3) as potential slides
    const headers = (markdown.match(/^#{1,3}\s+/gm) || []).length;
    
    // Count bullet points and numbered lists as content slides
    const bulletPoints = (markdown.match(/^[\s]*[-*+]\s+/gm) || []).length;
    const numberedLists = (markdown.match(/^[\s]*\d+\.\s+/gm) || []).length;
    
    // Each major section gets at least one slide
    const sections = Math.max(1, headers);
    
    // Add content slides based on bullet points (group every 4-6 points as one slide)
    const contentSlides = Math.ceil((bulletPoints + numberedLists) / 5);
    
    return Math.min(Math.max(sections + contentSlides, 3), 20); // Min 3, max 20 slides
  }

  function getContentPreview(markdown) {
    if (!markdown) return "Chưa có nội dung";
    
    // Extract first few lines for preview
    const lines = markdown.split('\n').filter(line => line.trim());
    const preview = lines.slice(0, 3).join(' ').substring(0, 100);
    
    return preview ? preview + '...' : "Nội dung bài giảng";
  }

  function openSlideModal() {
    if (!CURRENT) return;
    
    const modal = byId("slideModal");
    const titleSpan = byId("slideTitle");
    const contentSpan = byId("slideContent");
    const countSpan = byId("slideCount");
    
    if (titleSpan) titleSpan.textContent = CURRENT.title || "Bài giảng";
    if (contentSpan) contentSpan.textContent = getContentPreview(CURRENT.markdown);
    if (countSpan) countSpan.textContent = countEstimatedSlides(CURRENT.markdown) + " slides";
    
    modal.classList.add("show");
  }

  function closeSlideModal() {
    byId("slideModal").classList.remove("show");
  }

  function setButtonLoading(btn, loading = true) {
    const loadingEl = btn.querySelector('.btn-loading');
    const textEl = btn.querySelector('.btn-text');
    
    if (loading) {
      if (loadingEl) loadingEl.style.display = 'flex';
      if (textEl) textEl.style.display = 'none';
      btn.disabled = true;
    } else {
      if (loadingEl) loadingEl.style.display = 'none';
      if (textEl) textEl.style.display = 'flex';
      btn.disabled = false;
    }
  }

  async function generateSlide() {
    if (!CURRENT) return;
    
    const btn = byId("generateSlideBtn");
    const template = byId("slideTemplate").value;
    const format = byId("slideFormat").value;
    const includeIntro = byId("includeIntro").checked;
    const includeConclusion = byId("includeConclusion").checked;
    const includeQA = byId("includeQA").checked;

    setButtonLoading(btn, true);

    try {
      // Simulate slide generation process
      showToast("Đang phân tích nội dung bài giảng...", true, 'slide');
      
      await new Promise(resolve => setTimeout(resolve, 1500));
      
      showToast("Đang tạo slide với template " + template + "...", true, 'slide');
      
      await new Promise(resolve => setTimeout(resolve, 2000));

      // Generate slides based on markdown content
      const slideData = {
        planId: CURRENT.id,
        title: CURRENT.title,
        content: CURRENT.markdown,
        template: template,
        format: format,
        options: {
          includeIntro,
          includeConclusion,
          includeQA
        },
        slideCount: countEstimatedSlides(CURRENT.markdown)
      };

      if (format === 'html') {
        // Generate HTML slide
        const htmlSlide = generateHTMLSlide(slideData);
        downloadSlideFile(htmlSlide, CURRENT.title + '_slides.html', 'text/html');
        showToast("🎉 Đã tạo HTML slide thành công!", true, 'slide');
      } else if (format === 'pptx') {
        // Simulate PowerPoint generation
        showToast("⚠️ Tính năng PowerPoint đang phát triển", false);
      } else if (format === 'pdf') {
        // Simulate PDF generation  
        showToast("⚠️ Tính năng PDF đang phát triển", false);
      }

    } catch (error) {
      console.error('Slide generation error:', error);
      showToast("❌ Có lỗi khi tạo slide: " + error.message, false);
    } finally {
      setButtonLoading(btn, false);
      setTimeout(() => {
        closeSlideModal();
      }, 1500);
    }
  }

  function generateHTMLSlide(slideData) {
    const { title, content, template, options, slideCount } = slideData;
    
    // Parse markdown content into slides
    const slides = parseMarkdownToSlides(content, options);
    
    // Generate HTML with Reveal.js
    const html = `<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>${title} - Slide Presentation</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/reveal.js/4.3.1/reveal.min.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/reveal.js/4.3.1/theme/${getRevealTheme(template)}.min.css">
    <style>
        .reveal .slides section { text-align: left; }
        .reveal h1, .reveal h2, .reveal h3 { text-align: center; }
        .reveal .title-slide { text-align: center; }
        .reveal .intro-slide { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
        .reveal .content-slide { background: #f8f9fa; }
        .reveal .conclusion-slide { background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color: white; }
    </style>
</head>
<body>
    <div class="reveal">
        <div class="slides">
            ${slides.join('\n')}
        </div>
    </div>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/reveal.js/4.3.1/reveal.min.js"></script>
    <script>
        Reveal.initialize({
            hash: true,
            transition: 'slide',
            transitionSpeed: 'default',
            backgroundTransition: 'fade'
        });
    </script>
</body>
</html>`;

    return html;
  }

  function parseMarkdownToSlides(markdown, options) {
    const slides = [];
    const lines = markdown.split('\n');
    let currentSlide = [];
    let slideType = 'content';

    // Title slide
    if (options.includeIntro) {
      const title = CURRENT.title || 'Bài giảng';
      const subject = CURRENT.subject || 'Môn học';
      const grade = CURRENT.grade || 'Lớp';
      
      slides.push(`
        <section class="title-slide intro-slide">
            <h1>${title}</h1>
            <h3>${subject} - ${grade}</h3>
            <p><small>Thời gian: ${CURRENT.duration || '45 phút'}</small></p>
        </section>
      `);
    }

    // Parse content into slides
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();
      
      // New slide on H1, H2
      if (line.match(/^#{1,2}\s+/) && currentSlide.length > 0) {
        slides.push(createContentSlide(currentSlide.join('\n')));
        currentSlide = [];
      }
      
      if (line) {
        currentSlide.push(lines[i]);
      }
    }
    
    // Add remaining content
    if (currentSlide.length > 0) {
      slides.push(createContentSlide(currentSlide.join('\n')));
    }

    // Q&A slide
    if (options.includeQA) {
      slides.push(`
        <section class="conclusion-slide">
            <h2>🤔 Hỏi đáp</h2>
            <div style="text-align: center; margin-top: 100px;">
                <h3>Có câu hỏi nào không?</h3>
                <p>💬 Thảo luận và chia sẻ</p>
            </div>
        </section>
      `);
    }

    // Conclusion slide  
    if (options.includeConclusion) {
      slides.push(`
        <section class="conclusion-slide">
            <h2>🎯 Tóm tắt bài học</h2>
            <div style="text-align: center; margin-top: 50px;">
                <h3>${CURRENT.title}</h3>
                <p>✅ Đã hoàn thành mục tiêu bài học</p>
                <p>📚 Cảm ơn các em đã chú ý lắng nghe!</p>
            </div>
        </section>
      `);
    }

    return slides;
  }

  function createContentSlide(content) {
    const processedContent = content
      .replace(/^#{1,3}\s+(.+)$/gm, '<h2>$1</h2>')
      .replace(/^[-*+]\s+(.+)$/gm, '<li>$1</li>')
      .replace(/^\d+\.\s+(.+)$/gm, '<li>$1</li>')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      .replace(/`(.+?)`/g, '<code>$1</code>');

    // Wrap consecutive <li> in <ul>
    const withLists = processedContent.replace(/(<li>.*<\/li>)/gs, '<ul>$1</ul>');

    return `
      <section class="content-slide">
          ${withLists}
      </section>
    `;
  }

  function getRevealTheme(template) {
    const themes = {
      'modern': 'white',
      'classic': 'serif', 
      'minimal': 'simple',
      'vibrant': 'sky'
    };
    return themes[template] || 'white';
  }

  function downloadSlideFile(content, filename, mimeType) {
    const blob = new Blob([content], { type: mimeType + ';charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = sanitizeFileName(filename);
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  function backToChat() { window.location.href = "/chat"; }

  // === GLOBAL FUNCTIONS ===
  window.toggleEdit = toggleEdit;
  window.save = save;
  window.download = download;
  window.removePlan = removePlan;
  window.openCreate = openCreate;
  window.closeCreate = closeCreate;
  window.openSlideModal = openSlideModal;
  window.closeSlideModal = closeSlideModal;
  window.generateSlide = generateSlide;
  window.backToChat = backToChat;

  // === INITIALIZATION ===
  window.addEventListener("DOMContentLoaded", () => {
    byId("createForm")?.addEventListener("submit", onCreateSubmit);
    load();
  });

})();
