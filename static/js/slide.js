// ===== UPDATED SLIDE GENERATOR JAVASCRIPT FOR GOOGLE SLIDES =====

class SlideGenerator {
  constructor() {
    this.selectedStyle = 'modern';
    this.selectedColor = 'blue';
    this.selectedCount = 'concise';
    this.selectedFormat = 'html'; // html/google_slides
    this.lessonData = null;
    
    this.init();
  }
  
  init() {
    this.bindEvents();
    this.loadLessonData();
  }
  
  bindEvents() {
    // Style selection
    document.querySelectorAll('.style-card').forEach(card => {
      card.addEventListener('click', () => this.selectStyle(card));
    });
    
    // Color selection
    document.querySelectorAll('.color-option').forEach(option => {
      option.addEventListener('click', () => this.selectColor(option));
    });
    
    // Count and format radio buttons
    document.querySelectorAll('input[name="slideCount"]').forEach(input => {
      input.addEventListener('change', () => this.updateSlideCount(input.value));
    });
    
    document.querySelectorAll('input[name="exportFormat"]').forEach(input => {
      input.addEventListener('change', () => this.updateFormat(input.value));
    });
    
    // Modal close events
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') this.closeModal();
    });
  }
  
  selectStyle(card) {
    // Remove active class from all cards
    document.querySelectorAll('.style-card').forEach(c => c.classList.remove('active'));
    // Add active class to selected card
    card.classList.add('active');
    // Update selected style
    this.selectedStyle = card.dataset.style;
    
    // Update preview if needed
    this.updatePreview();
  }
  
  selectColor(option) {
    // Remove active class from all options
    document.querySelectorAll('.color-option').forEach(o => o.classList.remove('active'));
    // Add active class to selected option
    option.classList.add('active');
    // Update selected color
    this.selectedColor = option.dataset.color;
    
    // Update preview
    this.updatePreview();
  }
  
  updateSlideCount(count) {
    this.selectedCount = count;
    this.updateSlideEstimate();
  }
  
  updateFormat(format) {
    this.selectedFormat = format;
    
    // Update format descriptions
    this.updateFormatDescriptions(format);
  }
  
  updateFormatDescriptions(format) {
    const descriptions = {
      'html': 'Slide HTML tương tác, có thể mở bằng trình duyệt',
      'google_slides': 'Tạo presentation trực tiếp trên Google Slides', 
      'pptx': 'File PowerPoint có thể chỉnh sửa'
    };
    
    // Update UI descriptions if needed
    console.log(`Selected format: ${format} - ${descriptions[format]}`);
  }
  
  updateSlideEstimate() {
    const estimates = {
      'concise': '8-12 slides',
      'standard': '12-18 slides', 
      'detailed': '18-25 slides'
    };
    
    const estimateElement = document.getElementById('slideEstimate');
    if (estimateElement) {
      estimateElement.textContent = estimates[this.selectedCount] || '12-15 slides';
    }
  }
  
  updatePreview() {
    // This would update a visual preview if we had one
    console.log('Preview updated:', {
      style: this.selectedStyle,
      color: this.selectedColor
    });
  }
  
  loadLessonData() {
    // Load lesson data from the current lesson plan
    this.lessonData = {
      title: this.extractLessonTitle(),
      subject: this.extractSubject(),
      grade: this.extractGrade(),
      duration: '45 phút',
      content: this.getLessonContent()
    };
    
    // Update UI with lesson data
    this.updateLessonInfo();
  }
  
  extractLessonTitle() {
    // Try multiple selectors to find lesson title
    const selectors = [
      '#lessonTitle',
      'h1',
      '.lesson-title',
      '[data-lesson-title]'
    ];
    
    for (let selector of selectors) {
      const element = document.querySelector(selector);
      if (element && element.textContent.trim()) {
        return element.textContent.trim();
      }
    }
    
    // Fallback to first heading in viewer
    const viewer = document.getElementById('viewer');
    if (viewer) {
      const firstHeading = viewer.querySelector('h1, h2, h3');
      if (firstHeading) {
        return firstHeading.textContent.trim();
      }
    }
    
    return 'Bài giảng EduMate';
  }
  
  extractSubject() {
    // Try to extract subject from form data or content
    const formData = window.eduMateFormData || {};
    return formData.subject || 'Chưa xác định';
  }
  
  extractGrade() {
    const formData = window.eduMateFormData || {};
    return formData.grade || 'Chưa xác định';
  }
  
  getLessonContent() {
    // Get the current lesson plan content
    const viewer = document.getElementById('viewer');
    if (viewer) {
      return viewer.innerText || viewer.textContent || '';
    }
    
    // Try alternative selectors
    const contentSelectors = [
      '.lesson-content',
      '.markdown-content', 
      '.plan-content',
      'main'
    ];
    
    for (let selector of contentSelectors) {
      const element = document.querySelector(selector);
      if (element) {
        return element.innerText || element.textContent || '';
      }
    }
    
    return '';
  }
  
  updateLessonInfo() {
    const titleElement = document.getElementById('lessonTitle');
    if (titleElement && this.lessonData) {
      titleElement.textContent = this.lessonData.title;
    }
    
    // Auto-suggest color based on subject
    this.autoSuggestColor();
  }
  
  autoSuggestColor() {
    if (!this.lessonData?.subject) return;
    
    const subjectColorMap = {
      'toán': 'blue',
      'toán học': 'blue',
      'vật lý': 'purple', 
      'hóa học': 'green',
      'sinh học': 'green',
      'văn': 'orange',
      'văn học': 'orange',
      'lịch sử': 'red',
      'địa lý': 'green',
      'tiếng anh': 'blue'
    };
    
    const subject = this.lessonData.subject.toLowerCase();
    const suggestedColor = subjectColorMap[subject];
    
    if (suggestedColor) {
      const colorOption = document.querySelector(`[data-color="${suggestedColor}"]`);
      if (colorOption) {
        // Only auto-select if no color is currently selected
        const hasActiveColor = document.querySelector('.color-option.active');
        if (!hasActiveColor) {
          colorOption.click();
        }
      }
    }
  }
  
  async generateSlides() {
    const generateBtn = document.getElementById('generateBtn');
    const btnText = generateBtn.querySelector('.btn-text');
    const btnLoading = generateBtn.querySelector('.btn-loading');
    
    // Show loading state
    btnText.style.display = 'none';
    btnLoading.style.display = 'flex';
    generateBtn.disabled = true;
    
    try {
      // Get additional requirements
      const requirements = document.querySelector('.requirements-input').value;
      
      // Prepare slide generation data
      const slideData = {
        lessonContent: this.lessonData?.content || '',
        lessonTitle: this.lessonData?.title || '',
        style: this.selectedStyle,
        color: this.selectedColor,
        count: this.selectedCount,
        format: this.selectedFormat,
        requirements: requirements,
        subject: this.lessonData?.subject || '',
        grade: this.lessonData?.grade || '',
        duration: this.lessonData?.duration || ''
      };
      
      console.log('🎬 Generating slides with data:', slideData);
      
      // Call API to generate slides
      const response = await this.callSlideGeneratorAPI(slideData);
      
      if (response.success) {
        this.showSuccessToast(response);
        this.closeModal();
        
        // Handle different response types
        this.handleSlideResponse(response);
        
      } else {
        throw new Error(response.message || 'Có lỗi xảy ra khi tạo slide');
      }
      
    } catch (error) {
      console.error('Slide generation error:', error);
      this.showErrorToast(error.message);
      
    } finally {
      // Reset button state
      btnText.style.display = 'flex';
      btnLoading.style.display = 'none';
      generateBtn.disabled = false;
    }
  }
  
  handleSlideResponse(response) {
    // Handle HTML slide download
    if (response.downloadUrl && response.filename) {
      setTimeout(() => {
        this.downloadFile(response.downloadUrl, response.filename);
      }, 1000);
    }
    
    // Handle Google Slides URL
    if (response.googleSlidesUrl) {
      setTimeout(() => {
        const openGoogleSlides = confirm(
          `Slide đã được tạo thành công!\n\nBạn có muốn mở Google Slides để xem không?`
        );
        
        if (openGoogleSlides) {
          window.open(response.googleSlidesUrl, '_blank');
        }
      }, 2000);
    }
    
    // Show presentation info
    this.showPresentationInfo(response);
  }
  
  showPresentationInfo(response) {
    if (response.slideCount) {
      console.log(`📊 Đã tạo ${response.slideCount} slides`);
    }
    
    if (response.presentationId) {
      console.log(`🔗 Presentation ID: ${response.presentationId}`);
    }
  }
  
  async callSlideGeneratorAPI(slideData) {
    // API call to your backend slide generator
    const response = await fetch('/api/generate-slides', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(slideData)
    });
    
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`HTTP ${response.status}: ${errorText}`);
    }
    
    return await response.json();
  }
  
  downloadFile(url, filename) {
    const link = document.createElement('a');
    link.href = url;
    link.download = filename || 'slides.html';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    console.log(`📥 Downloaded: ${filename}`);
  }
  
  showSuccessToast(response) {
    const toast = document.getElementById('successToast');
    if (toast) {
      // Update toast message based on response
      const messageElement = toast.querySelector('.toast-message p');
      if (messageElement) {
        let message = 'Slide đã được tạo thành công!';
        
        if (response.googleSlidesUrl && response.downloadUrl) {
          message = 'HTML slide sẽ tải xuống, Google Slides sẽ mở trong tab mới.';
        } else if (response.googleSlidesUrl) {
          message = 'Google Slides sẽ mở trong tab mới.';
        } else if (response.downloadUrl) {
          message = 'Tải xuống sẽ bắt đầu trong giây lát...';
        }
        
        messageElement.textContent = message;
      }
      
      toast.style.display = 'block';
      
      // Auto hide after 5 seconds
      setTimeout(() => {
        toast.style.display = 'none';
      }, 5000);
    }
  }
  
  showErrorToast(message) {
    // Create error toast if it doesn't exist
    let errorToast = document.getElementById('errorToast');
    if (!errorToast) {
      errorToast = document.createElement('div');
      errorToast.id = 'errorToast';
      errorToast.className = 'toast error';
      errorToast.innerHTML = `
        <div class="toast-content">
          <div class="toast-icon">❌</div>
          <div class="toast-message">
            <strong>Có lỗi xảy ra!</strong>
            <p id="errorMessage">${message}</p>
          </div>
        </div>
      `;
      document.body.appendChild(errorToast);
    } else {
      document.getElementById('errorMessage').textContent = message;
    }
    
    errorToast.style.display = 'block';
    
    // Auto hide after 7 seconds
    setTimeout(() => {
      errorToast.style.display = 'none';
    }, 7000);
  }
  
  openModal() {
    const modal = document.getElementById('slideModal');
    if (modal) {
      modal.style.display = 'flex';
      document.body.style.overflow = 'hidden'; // Prevent background scrolling
      
      // Update lesson data when opening
      this.loadLessonData();
    }
  }
  
  closeModal() {
    const modal = document.getElementById('slideModal');
    if (modal) {
      modal.style.display = 'none';
      document.body.style.overflow = ''; // Restore scrolling
    }
  }
}

// Global functions for inline event handlers
function openSlideGenerator() {
  if (window.slideGenerator) {
    window.slideGenerator.openModal();
  }
}

function closeSlideGenerator() {
  if (window.slideGenerator) {
    window.slideGenerator.closeModal();
  }
}

function generateSlides() {
  if (window.slideGenerator) {
    window.slideGenerator.generateSlides();
  }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
  // Initialize slide generator
  window.slideGenerator = new SlideGenerator();
  
  // Auto-detect lesson plan data from existing page
  setTimeout(() => {
    if (window.slideGenerator) {
      window.slideGenerator.loadLessonData();
    }
  }, 500);
  
  // Make form data available globally if it exists
  try {
    const formDataScript = document.querySelector('script[data-form-data]');
    if (formDataScript) {
      window.eduMateFormData = JSON.parse(formDataScript.dataset.formData);
    }
  } catch (e) {
    console.log('No form data found in DOM');
  }
});

// Additional utility functions
function estimateSlideCount(content) {
  if (!content) return '8-12';
  
  // Simple estimation based on content length and structure
  const wordCount = content.split(/\s+/).length;
  const headingCount = (content.match(/^#{1,3}\s/gm) || []).length;
  const listItems = (content.match(/^\s*[-*+]\s/gm) || []).length;
  
  // Basic estimation formula
  let estimatedSlides = Math.ceil(wordCount / 100) + headingCount + Math.ceil(listItems / 5);
  
  // Ensure minimum and maximum bounds
  estimatedSlides = Math.max(8, Math.min(30, estimatedSlides));
  
  return `${estimatedSlides - 2}-${estimatedSlides + 2}`;
}

// Auto-detect and suggest settings based on lesson content
function autoSuggestSettings() {
  if (!window.slideGenerator || !window.slideGenerator.lessonData) return;
  
  const { subject, grade, content } = window.slideGenerator.lessonData;
  
  // Suggest style based on grade level
  if (grade && parseInt(grade) <= 5) {
    const creativeStyle = document.querySelector('[data-style="creative"]');
    if (creativeStyle && !document.querySelector('.style-card.active')) {
      creativeStyle.click();
    }
  } else if (grade && parseInt(grade) >= 10) {
    const academicStyle = document.querySelector('[data-style="academic"]');
    if (academicStyle && !document.querySelector('.style-card.active')) {
      academicStyle.click();
    }
  }
  
  // Update slide estimate based on content
  const estimate = estimateSlideCount(content);
  const estimateElement = document.getElementById('slideEstimate');
  if (estimateElement) {
    estimateElement.textContent = `${estimate} slides`;
  }
}

// Call auto-suggest when modal opens
document.addEventListener('DOMContentLoaded', function() {
  const openButton = document.getElementById('openSlideModal'); 
  if (openButton) {
    openButton.addEventListener('click', function() {
      setTimeout(autoSuggestSettings, 300);
    });
  }
});