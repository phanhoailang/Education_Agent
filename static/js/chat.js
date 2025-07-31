setTimeout(() => {
    const processingBanner = document.querySelector(".processing-banner");
    const statusIndicator = document.querySelector(".status-indicator span");
    const inputField = document.querySelector(".input-field");
    const sendBtn = document.querySelector(".send-btn");

    // Thêm: Lấy dữ liệu từ thẻ <script id="eduForm">
    const formDataElement = document.getElementById("eduForm");
    const formData = formDataElement ? JSON.parse(formDataElement.textContent) : {};

    // Thêm: In formData ra console
    console.log("Dữ liệu formData:", formData);

    // Kiểm tra nếu formData tồn tại và có dữ liệu
    if (formData && Object.keys(formData).length > 0) {
        let confirmationMessage = `
            <strong>Đã nhận dữ liệu từ form!</strong><br>
            <ul>
                <li><strong>Khối lớp:</strong> ${formData.grade || "Không xác định"}</li>
                <li><strong>Bộ sách giáo khoa:</strong> ${formData.textbook || "Không xác định"}</li>
                <li><strong>Môn học:</strong> ${formData.subject || "Không xác định"}</li>
                <li><strong>Chủ đề:</strong> ${formData.topic || "Không xác định"}</li>
                <li><strong>Thời gian:</strong> ${formData.duration ? formData.duration + " phút" : "Không xác định"}</li>
                <li><strong>Loại nội dung:</strong> ${(formData.content_types && formData.content_types.length > 0) ? formData.content_types.join(", ") : "Không xác định"}</li>
                <li><strong>Phong cách giảng dạy:</strong> ${formData.teaching_style || "Không xác định"}</li>
                <li><strong>Mức độ khó:</strong> ${formData.difficulty || "Không xác định"}</li>
                <li><strong>Yêu cầu bổ sung:</strong> ${formData.additional_requirements || "Không có"}</li>
                <li><strong>File đính kèm:</strong> ${(formData.files && formData.files.length > 0) ? formData.files.join(", ") : "Không có"}</li>
            </ul>
            <strong>Đang xử lý yêu cầu của bạn...</strong>
        `;
        addAIMessage(confirmationMessage);
    } else {
        addAIMessage("Không nhận được dữ liệu từ form. Vui lòng thử lại.");
    }

    statusIndicator.textContent = "Sẵn sàng chat";
    inputField.disabled = false;
    inputField.placeholder = "Nhập tin nhắn của bạn...";
    sendBtn.disabled = false;
}, 3000);

function addAIMessage(content) {
    const chatMessages = document.getElementById("chatMessages");
    const messageDiv = document.createElement("div");
    messageDiv.className = "message ai";
    messageDiv.innerHTML = `
        <div class="message-avatar">🤖</div>
        <div class="message-content">${content}</div>
    `;
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function addUserMessage(content) {
    const chatMessages = document.getElementById("chatMessages");
    const messageDiv = document.createElement("div");
    messageDiv.className = "message user";
    messageDiv.innerHTML = `
        <div class="message-avatar">👤</div>
        <div class="message-content">${content}</div>
    `;
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Handle voice/chat toggle
document.getElementById("voiceBtn")?.addEventListener("click", function () {
    document.getElementById("chatBtn")?.classList.remove("active");
    this.classList.add("active");
    // Thêm chức năng voice tại đây
});

document.getElementById("chatBtn")?.addEventListener("click", function () {
    document.getElementById("voiceBtn")?.classList.remove("active");
    this.classList.add("active");
    // Chuyển sang chế độ chat
});

// Handle gửi tin nhắn
document.querySelector(".input-field")?.addEventListener("keypress", function (e) {
    if (e.key === "Enter" && !this.disabled) {
        sendMessage();
    }
});

document.querySelector(".send-btn")?.addEventListener("click", sendMessage);

function sendMessage() {
    const inputField = document.querySelector(".input-field");
    const message = inputField.value.trim();

    if (message) {
        addUserMessage(message);
        inputField.value = "";

        // Mô phỏng AI suy nghĩ và trả lời
        setTimeout(() => {
            addAIMessage(
                "Cảm ơn bạn đã gửi tin nhắn! Tôi đang xử lý và sẽ trả lời bạn ngay..."
            );
        }, 1000);
    }
}

function goBack() {
    window.history.back();
}

// Thêm animation slide out
const style = document.createElement("style");
style.textContent = `
    @keyframes slideOut {
        from {
            opacity: 1;
            transform: translateY(0);
        }
        to {
            opacity: 0;
            transform: translateY(-20px);
        }
    }
`;
document.head.appendChild(style);