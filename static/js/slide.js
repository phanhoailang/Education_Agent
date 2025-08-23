// slide-creator.js
class SlideCreator {
    constructor() {
        this.form = document.getElementById('slideForm');
        this.progressSection = document.getElementById('progressSection');
        this.currentStep = 0;
        this.totalSteps = 4;
        this.previewModal = null;
        
        this.init();
    }

    init() {
        this.initEventListeners();
        this.initFileUpload();
        this.initTabs();
        this.initAdvancedToggle();
        this.initColorSchemes();
        this.createPreviewModal();
    }

    initEventListeners() {
        // Form submit
        this.form.addEventListener('submit', (e) => this.handleSubmit(e));
        
        // Preview button
        document.getElementById('previewBtn').addEventListener('click', () => this.handlePreview());
        
        // Create new lesson button
        document.getElementById('createNewLesson').addEventListener('click', () => this.handleCreateNewLesson());
    }

    initFileUpload() {
        const fileUploadZone = document.getElementById('fileUploadZone');
        const fileInput = document.getElementById('slideSourceFiles');
        const fileList = document.getElementById('slideFileList');

        // Click to upload
        fileUploadZone.addEventListener('click', () => fileInput.click());
        
        // Prevent default drag behaviors
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            fileUploadZone.addEventListener(eventName, this.preventDefaults, false);
            document.body.addEventListener(eventName, this.preventDefaults, false);
        });

        // Highlight drop zone when item is dragged over it
        ['dragenter', 'dragover'].forEach(eventName => {
            fileUploadZone.addEventListener(eventName, () => this.highlight(fileUploadZone), false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            fileUploadZone.addEventListener(eventName, () => this.unhighlight(fileUploadZone), false);
        });

        // Handle dropped files
        fileUploadZone.addEventListener('drop', (e) => this.handleDrop(e), false);
        
        // Handle file input change
        fileInput.addEventListener('change', (e) => this.handleFiles(e.target.files));
    }

    initTabs() {
        const tabButtons = document.querySelectorAll('.tab-btn');
        const tabContents = document.querySelectorAll('.tab-content');

        tabButtons.forEach(button => {
            button.addEventListener('click', () => {
                const targetTab = button.dataset.tab;
                
                // Remove active class from all tabs and contents
                tabButtons.forEach(btn => btn.classList.remove('active'));
                tabContents.forEach(content => content.classList.remove('active'));
                
                // Add active class to clicked tab and corresponding content
                button.classList.add('active');
                document.getElementById(targetTab).classList.add('active');
            });
        });
    }

    initAdvancedToggle() {
        const toggleBtn = document.getElementById('toggleAdvanced');
        const advancedSection = document.getElementById('advancedSection');

        toggleBtn.addEventListener('click', () => {
            const isActive = advancedSection.classList.toggle('active');
            toggleBtn.classList.toggle('active', isActive);
            
            // Smooth scroll to advanced section if opening
            if (isActive) {
                setTimeout(() => {
                    advancedSection.scrollIntoView({ 
                        behavior: 'smooth', 
                        block: 'nearest' 
                    });
                }, 100);
            }
        });
    }

    initColorSchemes() {
        const colorInputs = document.querySelectorAll('input[name="colorScheme"]');
        
        colorInputs.forEach(input => {
            input.addEventListener('change', (e) => {
                if (e.target.checked) {
                    // Remove checked class from all labels
                    colorInputs.forEach(inp => {
                        inp.nextElementSibling.classList.remove('checked');
                    });
                    // Add checked class to selected label
                    e.target.nextElementSibling.classList.add('checked');
                }
            });
        });
    }

    preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    highlight(element) {
        element.classList.add('dragover');
    }

    unhighlight(element) {
        element.classList.remove('dragover');
    }

    handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        this.handleFiles(files);
    }

    handleFiles(files) {
        const fileList = document.getElementById('slideFileList');
        const fileArray = Array.from(files);
        
        // Clear existing file list
        fileList.innerHTML = '';
        
        fileArray.forEach((file, index) => {
            const fileItem = this.createFileItem(file, index);
            fileList.appendChild(fileItem);
        });

        // Show file list if there are files
        if (fileArray.length > 0) {
            fileList.style.display = 'block';
        }
    }

    createFileItem(file, index) {
        const div = document.createElement('div');
        div.className = 'file-item';
        
        const icon = this.getFileIcon(file.type);
        const size = this.formatFileSize(file.size);
        
        div.innerHTML = `
            <i class="${icon}"></i>
            <div class="file-info">
                <div class="file-name">${file.name}</div>
                <div class="file-size">${size}</div>
            </div>
            <button type="button" class="file-remove" onclick="this.parentElement.remove()">
                <i class="fas fa-times"></i>
            </button>
        `;
        
        return div;
    }

    getFileIcon(mimeType) {
        if (mimeType.includes('pdf')) return 'fas fa-file-pdf';
        if (mimeType.includes('word') || mimeType.includes('document')) return 'fas fa-file-word';
        if (mimeType.includes('presentation') || mimeType.includes('powerpoint')) return 'fas fa-file-powerpoint';
        if (mimeType.includes('text')) return 'fas fa-file-alt';
        return 'fas fa-file';
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    async handleSubmit(e) {
        e.preventDefault();
        
        // Validate form
        if (!this.validateForm()) {
            return;
        }
        
        // Start progress
        this.startProgress();
        
        try {
            // Collect form data
            const formData = this.collectFormData();
            
            // Submit to backend
            const result = await this.submitSlideCreation(formData);
            
            // Handle success
            this.handleSuccess(result);
            
        } catch (error) {
            console.error('Error creating slides:', error);
            this.handleError(error);
        }
    }

    validateForm() {
        const contentSource = this.getSelectedContentSource();
        
        if (!contentSource) {
            this.showError('Vui lòng chọn nguồn nội dung');
            return false;
        }
        
        // Validate based on selected content source
        if (contentSource === 'manual-input') {
            const manualContent = document.querySelector('textarea[name="manualContent"]').value;
            if (!manualContent.trim()) {
                this.showError('Vui lòng nhập nội dung bài giảng');
                return false;
            }
        }
        
        if (contentSource === 'file-upload') {
            const files = document.getElementById('slideSourceFiles').files;
            if (files.length === 0) {
                this.showError('Vui lòng chọn file để upload');
                return false;
            }
        }
        
        if (contentSource === 'lesson-plan') {
            const selectedPlan = document.getElementById('existingLessonPlan').value;
            if (!selectedPlan) {
                this.showError('Vui lòng chọn kế hoạch bài giảng');
                return false;
            }
        }
        
        return true;
    }

    getSelectedContentSource() {
        const activeTab = document.querySelector('.tab-btn.active');
        return activeTab ? activeTab.dataset.tab : null;
    }

    collectFormData() {
        const formData = new FormData(this.form);
        
        // Add additional data
        formData.append('contentSource', this.getSelectedContentSource());
        
        // Collect export formats
        const exportFormats = [];
        document.querySelectorAll('input[name="exportFormat"]:checked').forEach(input => {
            exportFormats.push(input.value);
        });
        formData.append('exportFormats', JSON.stringify(exportFormats));
        
        // Collect transitions
        const transitions = [];
        document.querySelectorAll('input[name="transitions"]:checked').forEach(input => {
            transitions.push(input.value);
        });
        formData.append('transitions', JSON.stringify(transitions));
        
        return formData;
    }

    async submitSlideCreation(formData) {
        const response = await fetch('/create-slides', {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.message || 'Failed to create slides');
        }
        
        return await response.json();
    }

    startProgress() {
        // Show progress section
        this.progressSection.style.display = 'block';
        this.progressSection.scrollIntoView({ behavior: 'smooth' });
        
        // Hide form
        document.querySelector('.form-section').style.display = 'none';
        
        // Set loading state on button
        const createBtn = document.getElementById('createSlideBtn');
        createBtn.classList.add('loading');
        createBtn.disabled = true;
        
        // Start progress steps
        this.currentStep = 0;
        this.updateProgress();
    }

    updateProgress() {
        const steps = document.querySelectorAll('.step');
        const progressFill = document.getElementById('progressFill');
        
        // Update steps
        steps.forEach((step, index) => {
            step.classList.remove('active', 'completed');
            if (index < this.currentStep) {
                step.classList.add('completed');
            } else if (index === this.currentStep) {
                step.classList.add('active');
            }
        });
        
        // Update progress bar
        const progress = (this.currentStep / this.totalSteps) * 100;
        progressFill.style.width = `${progress}%`;
        
        // Auto advance (simulate processing)
        if (this.currentStep < this.totalSteps) {
            setTimeout(() => {
                this.currentStep++;
                this.updateProgress();
            }, 2000 + Math.random() * 1000); // 2-3 seconds per step
        }
    }

    handleSuccess(result) {
        // Complete all steps
        this.currentStep = this.totalSteps;
        this.updateProgress();
        
        // Show success message and redirect
        setTimeout(() => {
            this.showSuccessMessage(result);
        }, 1000);
    }

    showSuccessMessage(result) {
        const progressContainer = document.querySelector('.progress-container');
        progressContainer.innerHTML = `
            <div class="success-message">
                <div class="success-icon">
                    <i class="fas fa-check-circle"></i>
                </div>
                <h3>Slide đã được tạo thành công!</h3>
                <p>Slide của bạn đã sẵn sàng. Bạn có thể xem trước hoặc tải về.</p>
                <div class="success-actions">
                    ${result.google_slides_url ? `
                        <a href="${result.google_slides_url}" target="_blank" class="btn-primary">
                            <i class="fab fa-google"></i>
                            Mở Google Slides
                        </a>
                    ` : ''}
                    ${result.html_path ? `
                        <a href="${result.html_path}" target="_blank" class="btn-secondary">
                            <i class="fas fa-eye"></i>
                            Xem trước HTML
                        </a>
                    ` : ''}
                    ${result.pptx_path ? `
                        <a href="${result.pptx_path}" download class="btn-secondary">
                            <i class="fas fa-download"></i>
                            Tải PPTX
                        </a>
                    ` : ''}
                    ${result.pdf_path ? `
                        <a href="${result.pdf_path}" download class="btn-secondary">
                            <i class="fas fa-download"></i>
                            Tải PDF
                        </a>
                    ` : ''}
                </div>
                <div class="slide-info">
                    <div class="info-item">
                        <i class="fas fa-layer-group"></i>
                        <span>${result.slide_count || 0} slide</span>
                    </div>
                    ${result.outline_path ? `
                        <div class="info-item">
                            <i class="fas fa-file-alt"></i>
                            <a href="${result.outline_path}" download>Tải outline</a>
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    }

    handleError(error) {
        const progressContainer = document.querySelector('.progress-container');
        progressContainer.innerHTML = `
            <div class="error-message">
                <div class="error-icon">
                    <i class="fas fa-exclamation-triangle"></i>
                </div>
                <h3>Có lỗi xảy ra</h3>
                <p>${error.message || 'Không thể tạo slide. Vui lòng thử lại.'}</p>
                <div class="error-actions">
                    <button type="button" class="btn-primary" onclick="location.reload()">
                        <i class="fas fa-redo"></i>
                        Thử lại
                    </button>
                    <button type="button" class="btn-secondary" onclick="slideCreator.showForm()">
                        <i class="fas fa-arrow-left"></i>
                        Quay lại form
                    </button>
                </div>
            </div>
        `;
    }

    showForm() {
        // Hide progress section
        this.progressSection.style.display = 'none';
        
        // Show form section
        document.querySelector('.form-section').style.display = 'block';
        
        // Reset button state
        const createBtn = document.getElementById('createSlideBtn');
        createBtn.classList.remove('loading');
        createBtn.disabled = false;
        
        // Scroll to form
        document.querySelector('.form-section').scrollIntoView({ behavior: 'smooth' });
    }

    showError(message) {
        // Create error notification
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-notification';
        errorDiv.innerHTML = `
            <i class="fas fa-exclamation-circle"></i>
            <span>${message}</span>
            <button type="button" onclick="this.parentElement.remove()">
                <i class="fas fa-times"></i>
            </button>
        `;
        
        // Add to page
        document.body.appendChild(errorDiv);
        
        // Auto remove after 5 seconds
        setTimeout(() => {
            if (errorDiv.parentNode) {
                errorDiv.remove();
            }
        }, 5000);
    }

    // ===== HOÀN THIỆN CÁC METHOD CÒN THIẾU =====

    createPreviewModal() {
        // Tạo modal preview
        const modal = document.createElement('div');
        modal.id = 'previewModal';
        modal.className = 'preview-modal';
        modal.innerHTML = `
            <div class="modal-overlay" onclick="slideCreator.closePreviewModal()"></div>
            <div class="modal-content">
                <div class="modal-header">
                    <h3><i class="fas fa-eye"></i> Xem trước nội dung</h3>
                    <button class="modal-close" onclick="slideCreator.closePreviewModal()">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                <div class="modal-body">
                    <div class="preview-content"></div>
                </div>
                <div class="modal-footer">
                    <button class="btn-secondary" onclick="slideCreator.closePreviewModal()">
                        <i class="fas fa-times"></i> Đóng
                    </button>
                    <button class="btn-primary" onclick="slideCreator.proceedWithCreation()">
                        <i class="fas fa-check"></i> Tiếp tục tạo slide
                    </button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        this.previewModal = modal;
    }

    handlePreview() {
        // Validate form trước khi preview
        if (!this.validateForm()) {
            return;
        }

        // Collect current form data
        const formData = this.collectFormData();
        const contentSource = this.getSelectedContentSource();
        
        // Tạo preview content dựa trên source
        let previewContent = '';
        
        switch(contentSource) {
            case 'manual-input':
                previewContent = this.generateManualInputPreview(formData);
                break;
            case 'file-upload':
                previewContent = this.generateFileUploadPreview(formData);
                break;
            case 'lesson-plan':
                previewContent = this.generateLessonPlanPreview(formData);
                break;
            default:
                previewContent = '<p>Không thể tạo preview cho nguồn nội dung này.</p>';
        }

        // Hiển thị preview modal
        this.showPreviewModal(previewContent, formData);
    }

    generateManualInputPreview(formData) {
        const manualContent = formData.get('manualContent');
        const slideTitle = formData.get('slideTitle') || 'Bài giảng mới';
        const slideCount = formData.get('slideCount') || 'Tự động';
        const colorScheme = formData.get('colorScheme') || 'blue';

        return `
            <div class="preview-section">
                <h4><i class="fas fa-info-circle"></i> Thông tin cơ bản</h4>
                <div class="info-grid">
                    <div class="info-item">
                        <span class="label">Tiêu đề:</span>
                        <span class="value">${slideTitle}</span>
                    </div>
                    <div class="info-item">
                        <span class="label">Số slide:</span>
                        <span class="value">${slideCount}</span>
                    </div>
                    <div class="info-item">
                        <span class="label">Màu sắc:</span>
                        <span class="value color-preview ${colorScheme}">${this.getColorSchemeName(colorScheme)}</span>
                    </div>
                </div>
            </div>
            <div class="preview-section">
                <h4><i class="fas fa-file-alt"></i> Nội dung bài giảng</h4>
                <div class="content-preview">
                    ${this.formatContentPreview(manualContent)}
                </div>
            </div>
            ${this.generateAdvancedOptionsPreview(formData)}
        `;
    }

    generateFileUploadPreview(formData) {
        const files = document.getElementById('slideSourceFiles').files;
        const slideTitle = formData.get('slideTitle') || 'Bài giảng mới';
        const slideCount = formData.get('slideCount') || 'Tự động';
        const colorScheme = formData.get('colorScheme') || 'blue';

        let filesList = '';
        Array.from(files).forEach(file => {
            const icon = this.getFileIcon(file.type);
            const size = this.formatFileSize(file.size);
            filesList += `
                <div class="file-preview-item">
                    <i class="${icon}"></i>
                    <div class="file-details">
                        <span class="file-name">${file.name}</span>
                        <span class="file-size">${size}</span>
                    </div>
                </div>
            `;
        });

        return `
            <div class="preview-section">
                <h4><i class="fas fa-info-circle"></i> Thông tin cơ bản</h4>
                <div class="info-grid">
                    <div class="info-item">
                        <span class="label">Tiêu đề:</span>
                        <span class="value">${slideTitle}</span>
                    </div>
                    <div class="info-item">
                        <span class="label">Số slide:</span>
                        <span class="value">${slideCount}</span>
                    </div>
                    <div class="info-item">
                        <span class="label">Màu sắc:</span>
                        <span class="value color-preview ${colorScheme}">${this.getColorSchemeName(colorScheme)}</span>
                    </div>
                </div>
            </div>
            <div class="preview-section">
                <h4><i class="fas fa-upload"></i> Files đã tải lên (${files.length} file)</h4>
                <div class="files-preview">
                    ${filesList}
                </div>
            </div>
            ${this.generateAdvancedOptionsPreview(formData)}
        `;
    }

    generateLessonPlanPreview(formData) {
        const selectedPlan = formData.get('existingLessonPlan');
        const slideTitle = formData.get('slideTitle') || 'Bài giảng mới';
        const slideCount = formData.get('slideCount') || 'Tự động';
        const colorScheme = formData.get('colorScheme') || 'blue';

        return `
            <div class="preview-section">
                <h4><i class="fas fa-info-circle"></i> Thông tin cơ bản</h4>
                <div class="info-grid">
                    <div class="info-item">
                        <span class="label">Tiêu đề:</span>
                        <span class="value">${slideTitle}</span>
                    </div>
                    <div class="info-item">
                        <span class="label">Số slide:</span>
                        <span class="value">${slideCount}</span>
                    </div>
                    <div class="info-item">
                        <span class="label">Màu sắc:</span>
                        <span class="value color-preview ${colorScheme}">${this.getColorSchemeName(colorScheme)}</span>
                    </div>
                </div>
            </div>
            <div class="preview-section">
                <h4><i class="fas fa-clipboard-list"></i> Kế hoạch bài giảng</h4>
                <div class="lesson-plan-preview">
                    <div class="selected-plan">
                        <i class="fas fa-check-circle"></i>
                        <span>Đã chọn: ${selectedPlan || 'Chưa chọn kế hoạch'}</span>
                    </div>
                </div>
            </div>
            ${this.generateAdvancedOptionsPreview(formData)}
        `;
    }

    generateAdvancedOptionsPreview(formData) {
        const exportFormats = JSON.parse(formData.get('exportFormats') || '[]');
        const transitions = JSON.parse(formData.get('transitions') || '[]');
        const includeNotes = formData.get('includeNotes');
        const autoGenerate = formData.get('autoGenerate');

        let advancedContent = '<div class="preview-section">';
        advancedContent += '<h4><i class="fas fa-cog"></i> Tùy chọn nâng cao</h4>';

        if (exportFormats.length > 0) {
            advancedContent += `
                <div class="option-group">
                    <span class="option-label">Định dạng xuất:</span>
                    <div class="option-values">
                        ${exportFormats.map(format => `<span class="format-tag">${this.getFormatName(format)}</span>`).join('')}
                    </div>
                </div>
            `;
        }

        if (transitions.length > 0) {
            advancedContent += `
                <div class="option-group">
                    <span class="option-label">Hiệu ứng chuyển slide:</span>
                    <div class="option-values">
                        ${transitions.map(transition => `<span class="transition-tag">${this.getTransitionName(transition)}</span>`).join('')}
                    </div>
                </div>
            `;
        }

        const additionalOptions = [];
        if (includeNotes) additionalOptions.push('Bao gồm ghi chú');
        if (autoGenerate) additionalOptions.push('Tự động tạo nội dung');

        if (additionalOptions.length > 0) {
            advancedContent += `
                <div class="option-group">
                    <span class="option-label">Tùy chọn khác:</span>
                    <div class="option-values">
                        ${additionalOptions.map(option => `<span class="option-tag">${option}</span>`).join('')}
                    </div>
                </div>
            `;
        }

        advancedContent += '</div>';
        return advancedContent;
    }

    formatContentPreview(content) {
        if (!content || content.trim().length === 0) {
            return '<p class="empty-content">Chưa có nội dung</p>';
        }

        // Tách nội dung thành đoạn và hiển thị preview
        const paragraphs = content.split('\n').filter(p => p.trim().length > 0);
        const maxParagraphs = 3;
        const displayParagraphs = paragraphs.slice(0, maxParagraphs);

        let preview = displayParagraphs.map(p => `<p>${p.trim()}</p>`).join('');
        
        if (paragraphs.length > maxParagraphs) {
            preview += `<p class="more-content">... và ${paragraphs.length - maxParagraphs} đoạn khác</p>`;
        }

        return preview;
    }

    getColorSchemeName(scheme) {
        const colorNames = {
            'blue': 'Xanh dương',
            'green': 'Xanh lá',
            'red': 'Đỏ',
            'purple': 'Tím',
            'orange': 'Cam',
            'teal': 'Xanh ngọc'
        };
        return colorNames[scheme] || scheme;
    }

    getFormatName(format) {
        const formatNames = {
            'pptx': 'PowerPoint',
            'pdf': 'PDF',
            'html': 'HTML',
            'google-slides': 'Google Slides'
        };
        return formatNames[format] || format;
    }

    getTransitionName(transition) {
        const transitionNames = {
            'fade': 'Mờ dần',
            'slide': 'Trượt',
            'zoom': 'Phóng to',
            'flip': 'Lật',
            'cube': 'Hình khối'
        };
        return transitionNames[transition] || transition;
    }

    showPreviewModal(content, formData) {
        const previewContent = this.previewModal.querySelector('.preview-content');
        previewContent.innerHTML = content;
        
        // Store form data for later use
        this.previewFormData = formData;
        
        // Show modal
        this.previewModal.style.display = 'flex';
        document.body.classList.add('modal-open');
        
        // Add animation
        setTimeout(() => {
            this.previewModal.classList.add('show');
        }, 10);
    }

    closePreviewModal() {
        this.previewModal.classList.remove('show');
        setTimeout(() => {
            this.previewModal.style.display = 'none';
            document.body.classList.remove('modal-open');
        }, 300);
    }

    proceedWithCreation() {
        // Đóng modal và tiến hành tạo slide
        this.closePreviewModal();
        
        // Trigger form submission
        if (this.previewFormData) {
            this.startProgress();
            this.submitSlideCreation(this.previewFormData)
                .then(result => this.handleSuccess(result))
                .catch(error => this.handleError(error));
        }
    }

    handleCreateNewLesson() {
        // Hiển thị confirmation dialog
        const confirmCreate = confirm('Bạn có muốn mở trang tạo bài giảng mới trong tab mới không?');
        
        if (confirmCreate) {
            // Redirect to lesson creation page
            window.open('/form', '_blank');
        }
    }

    // ===== UTILITY METHODS =====

    showLoading(element, text = 'Đang xử lý...') {
        element.classList.add('loading');
        element.disabled = true;
        element.dataset.originalText = element.textContent;
        element.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${text}`;
    }

    hideLoading(element) {
        element.classList.remove('loading');
        element.disabled = false;
        element.textContent = element.dataset.originalText;
    }

    showNotification(message, type = 'info', duration = 5000) {
        // Remove existing notifications
        const existingNotifications = document.querySelectorAll('.notification');
        existingNotifications.forEach(n => n.remove());

        // Create notification
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        
        const icon = this.getNotificationIcon(type);
        notification.innerHTML = `
            <div class="notification-content">
                <i class="${icon}"></i>
                <span>${message}</span>
            </div>
            <button class="notification-close" onclick="this.parentElement.remove()">
                <i class="fas fa-times"></i>
            </button>
        `;

        // Add to page
        document.body.appendChild(notification);

        // Show with animation
        setTimeout(() => notification.classList.add('show'), 10);

        // Auto remove
        setTimeout(() => {
            if (notification.parentNode) {
                notification.classList.remove('show');
                setTimeout(() => notification.remove(), 300);
            }
        }, duration);
    }

    getNotificationIcon(type) {
        const icons = {
            'success': 'fas fa-check-circle',
            'error': 'fas fa-exclamation-circle',
            'warning': 'fas fa-exclamation-triangle',
            'info': 'fas fa-info-circle'
        };
        return icons[type] || icons.info;
    }

    // Form validation helpers
    validateFileTypes(files) {
        const allowedTypes = [
            'application/pdf',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.ms-powerpoint',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'text/plain',
            'text/html'
        ];

        for (let file of files) {
            if (!allowedTypes.includes(file.type)) {
                return {
                    valid: false,
                    message: `File "${file.name}" không được hỗ trợ. Chỉ chấp nhận PDF, Word, PowerPoint, Text và HTML.`
                };
            }
        }
        return { valid: true };
    }

    validateFileSize(files, maxSizeMB = 50) {
        const maxSize = maxSizeMB * 1024 * 1024; // Convert to bytes

        for (let file of files) {
            if (file.size > maxSize) {
                return {
                    valid: false,
                    message: `File "${file.name}" quá lớn. Kích thước tối đa cho phép là ${maxSizeMB}MB.`
                };
            }
        }
        return { valid: true };
    }

    // Content processing helpers
    extractTextFromContent(content) {
        // Remove HTML tags and clean up text
        const div = document.createElement('div');
        div.innerHTML = content;
        return div.textContent || div.innerText || '';
    }

    estimateSlideCount(content) {
        if (!content) return 0;
        
        const cleanContent = this.extractTextFromContent(content);
        const wordCount = cleanContent.split(/\s+/).filter(word => word.length > 0).length;
        
        // Estimate: ~100-150 words per slide
        const estimatedSlides = Math.ceil(wordCount / 125);
        return Math.max(1, Math.min(estimatedSlides, 50)); // Min 1, max 50 slides
    }

    // Auto-save functionality
    enableAutoSave() {
        const formElements = this.form.querySelectorAll('input, textarea, select');
        
        formElements.forEach(element => {
            element.addEventListener('input', this.debounce(() => {
                this.saveFormData();
            }, 1000));
        });
    }

    saveFormData() {
        try {
            const formData = new FormData(this.form);
            const data = {};
            
            for (let [key, value] of formData.entries()) {
                data[key] = value;
            }
            
            // Add current tab
            data.activeTab = this.getSelectedContentSource();
            
            // Save to sessionStorage (temporary storage)
            const savedData = JSON.stringify(data);
            if (typeof(Storage) !== "undefined") {
                sessionStorage.setItem('slideCreatorFormData', savedData);
            }
        } catch (error) {
            console.warn('Could not save form data:', error);
        }
    }

    loadSavedFormData() {
        try {
            if (typeof(Storage) !== "undefined") {
                const savedData = sessionStorage.getItem('slideCreatorFormData');
                if (savedData) {
                    const data = JSON.parse(savedData);
                    
                    // Restore form values
                    Object.keys(data).forEach(key => {
                        if (key === 'activeTab') {
                            // Restore active tab
                            const tabButton = document.querySelector(`[data-tab="${data[key]}"]`);
                            if (tabButton) {
                                tabButton.click();
                            }
                        } else {
                            const element = this.form.querySelector(`[name="${key}"]`);
                            if (element) {
                                if (element.type === 'checkbox' || element.type === 'radio') {
                                    element.checked = element.value === data[key];
                                } else {
                                    element.value = data[key];
                                }
                            }
                        }
                    });
                    
                    this.showNotification('Đã khôi phục dữ liệu form trước đó', 'info', 3000);
                }
            }
        } catch (error) {
            console.warn('Could not load saved form data:', error);
        }
    }

    clearSavedFormData() {
        try {
            if (typeof(Storage) !== "undefined") {
                sessionStorage.removeItem('slideCreatorFormData');
            }
        } catch (error) {
            console.warn('Could not clear saved form data:', error);
        }
    }

    // Utility function for debouncing
    debounce(func, wait, immediate) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                timeout = null;
                if (!immediate) func.apply(this, args);
            };
            const callNow = immediate && !timeout;
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
            if (callNow) func.apply(this, args);
        };
    }

    // Analytics and tracking (optional)
    trackEvent(eventName, eventData = {}) {
        // Send analytics data if tracking is enabled
        if (typeof gtag !== 'undefined') {
            gtag('event', eventName, eventData);
        }
        
        // Log for debugging
        console.log('Event tracked:', eventName, eventData);
    }

    // Advanced form features
    setupFormValidationStyles() {
        const inputs = this.form.querySelectorAll('input, textarea, select');
        
        inputs.forEach(input => {
            input.addEventListener('blur', () => {
                this.validateField(input);
            });
            
            input.addEventListener('input', () => {
                // Remove error styling on input
                input.classList.remove('error');
                const errorMsg = input.parentNode.querySelector('.error-message');
                if (errorMsg) {
                    errorMsg.remove();
                }
            });
        });
    }

    validateField(field) {
        let isValid = true;
        let errorMessage = '';

        // Remove existing error message
        const existingError = field.parentNode.querySelector('.error-message');
        if (existingError) {
            existingError.remove();
        }

        // Required field validation
        if (field.hasAttribute('required') && !field.value.trim()) {
            isValid = false;
            errorMessage = 'Trường này là bắt buộc';
        }

        // Email validation
        if (field.type === 'email' && field.value) {
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!emailRegex.test(field.value)) {
                isValid = false;
                errorMessage = 'Email không hợp lệ';
            }
        }

        // Number validation
        if (field.type === 'number' && field.value) {
            const min = parseFloat(field.getAttribute('min'));
            const max = parseFloat(field.getAttribute('max'));
            const value = parseFloat(field.value);

            if (!isNaN(min) && value < min) {
                isValid = false;
                errorMessage = `Giá trị phải lớn hơn hoặc bằng ${min}`;
            }
            if (!isNaN(max) && value > max) {
                isValid = false;
                errorMessage = `Giá trị phải nhỏ hơn hoặc bằng ${max}`;
            }
        }

        // Show error if invalid
        if (!isValid) {
            field.classList.add('error');
            const errorDiv = document.createElement('div');
            errorDiv.className = 'error-message';
            errorDiv.textContent = errorMessage;
            field.parentNode.appendChild(errorDiv);
        }

        return isValid;
    }

    // Keyboard shortcuts
    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Ctrl/Cmd + Enter: Submit form
            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                e.preventDefault();
                this.form.dispatchEvent(new Event('submit'));
            }

            // Ctrl/Cmd + P: Preview
            if ((e.ctrlKey || e.metaKey) && e.key === 'p') {
                e.preventDefault();
                this.handlePreview();
            }

            // Escape: Close modal
            if (e.key === 'Escape') {
                if (this.previewModal && this.previewModal.classList.contains('show')) {
                    this.closePreviewModal();
                }
            }
        });
    }

    // Initialize enhanced features
    initEnhancedFeatures() {
        this.enableAutoSave();
        this.loadSavedFormData();
        this.setupFormValidationStyles();
        this.setupKeyboardShortcuts();
        
        // Track page load
        this.trackEvent('slide_creator_loaded');
    }

    // Update the main init method to include enhanced features
    initComplete() {
        this.init();
        this.initEnhancedFeatures();
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.slideCreator = new SlideCreator();
    slideCreator.initComplete();
});

// Export for module use (if needed)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SlideCreator;
}