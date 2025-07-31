// Biến toàn cục để lưu trữ file
let selectedFiles = [];

document.getElementById("eduForm")?.addEventListener("submit", async function (e) {
    e.preventDefault();

    // Kiểm tra xem có ít nhất một checkbox content_type được chọn
    const checkboxes = document.querySelectorAll('input[name="content_type[]"]');
    const isChecked = Array.from(checkboxes).some(checkbox => checkbox.checked);
    const errorMessage = document.getElementById("content-error");

    if (!isChecked) {
        errorMessage.style.display = "block";
        errorMessage.scrollIntoView({ behavior: "smooth", block: "center" });
        return;
    }

    // Ẩn thông báo lỗi nếu vượt qua kiểm tra
    errorMessage.style.display = "none";

    // Hiệu ứng loading
    const submitBtn = document.querySelector(".submit-btn");
    const originalText = submitBtn.textContent;
    submitBtn.textContent = "⏳ Đang xử lý...";
    submitBtn.disabled = true;

    try {
        // Thu thập dữ liệu form
        const formData = new FormData(this);
        
        // Xóa file input cũ và thêm file từ selectedFiles
        formData.delete('files[]');
        selectedFiles.forEach(file => {
            formData.append('files[]', file);
        });

        // Gửi dữ liệu tới server
        const response = await fetch('/process', {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            console.log("Form submitted successfully, redirecting to /chat...");
            window.location.href = '/chat';
        } else {
            const errorData = await response.json();
            console.error("Lỗi khi gửi form:", response.status, response.statusText, errorData);
            alert(`Có lỗi xảy ra khi gửi form: ${response.statusText}\nChi tiết: ${errorData.details || 'Không có chi tiết'}`);
        }
    } catch (error) {
        console.error("Lỗi xử lý form:", error);
        alert("Có lỗi xảy ra khi xử lý form: " + error.message);
    } finally {
        // Khôi phục nút submit
        submitBtn.textContent = originalText;
        submitBtn.disabled = false;
    }
});

// Hàm cập nhật hiển thị file
function updateFileDisplay() {
    const fileList = document.getElementById("fileList");
    const label = document.querySelector(".file-upload-label span");
    
    fileList.innerHTML = "";
    
    if (selectedFiles.length > 0) {
        label.textContent = `Đã chọn ${selectedFiles.length} file`;
        
        selectedFiles.forEach((file, index) => {
            const fileItem = document.createElement("div");
            fileItem.classList.add("file-item");

            // Xác định biểu tượng theo loại file
            let iconClass;
            if (file.type === "application/pdf") {
                iconClass = "fa-solid fa-file-pdf";
            } else if (file.type.includes("msword") || file.type.includes("officedocument.wordprocessingml")) {
                iconClass = "fa-solid fa-file-word";
            } else if (file.type.includes("powerpoint") || file.type.includes("presentationml")) {
                iconClass = "fa-solid fa-file-powerpoint";
            } else if (file.type === "text/plain") {
                iconClass = "fa-solid fa-file-lines";
            } else if (file.type.startsWith("image/")) {
                iconClass = "fa-solid fa-file-image";
            } else {
                iconClass = "fa-solid fa-file";
            }

            const fileType = file.type.split("/").pop().toUpperCase() || "Không xác định";
            const fileSize = (file.size / 1024 / 1024).toFixed(2) + " MB";

            fileItem.innerHTML = `
                <i class="${iconClass} file-icon"></i>
                <span>${file.name} (${fileType} - ${fileSize})</span>
                <button class="delete-btn" title="Xóa file" data-index="${index}">
                    <i class="fa-solid fa-times"></i>
                </button>
            `;

            // Thêm sự kiện xóa file
            fileItem.querySelector(".delete-btn").addEventListener("click", function () {
                selectedFiles.splice(index, 1);
                updateFileDisplay();
            });

            fileList.appendChild(fileItem);
        });
    } else {
        label.textContent = "Kéo thả file vào đây hoặc click để chọn";
    }
}

// Hàm thêm file
function addFiles(files) {
    const allowedTypes = ['.pdf', '.doc', '.docx', '.ppt', '.pptx', '.txt', '.jpg', '.png'];
    const newFiles = Array.from(files).filter(file => {
        const extension = '.' + file.name.split('.').pop().toLowerCase();
        return allowedTypes.includes(extension);
    });

    // Thêm file mới vào danh sách (tránh trùng lặp)
    newFiles.forEach(file => {
        const exists = selectedFiles.some(existingFile => 
            existingFile.name === file.name && existingFile.size === file.size
        );
        if (!exists) {
            selectedFiles.push(file);
        }
    });

    updateFileDisplay();
}

// Xử lý file input change
document.getElementById("files")?.addEventListener("change", function (e) {
    if (e.target.files.length > 0) {
        addFiles(e.target.files);
    }
});

// Xử lý drag and drop
const fileUpload = document.getElementById("fileUpload");

fileUpload?.addEventListener("dragover", function (e) {
    e.preventDefault();
    fileUpload.classList.add("drag-over");
});

fileUpload?.addEventListener("dragleave", function (e) {
    e.preventDefault();
    fileUpload.classList.remove("drag-over");
});

fileUpload?.addEventListener("drop", function (e) {
    e.preventDefault();
    fileUpload.classList.remove("drag-over");
    
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        addFiles(files);
    }
});

// Hide error message when user selects a checkbox
document.querySelectorAll('input[name="content_type[]"]').forEach(checkbox => {
    checkbox.addEventListener("change", function () {
        const checkboxes = document.querySelectorAll('input[name="content_type[]"]');
        const isChecked = Array.from(checkboxes).some(checkbox => checkbox.checked);
        const errorMessage = document.getElementById("content-error");

        if (isChecked) {
            errorMessage.style.display = "none";
        }
    });
});