# 🤖 Google One (Gemini) Student Verification Tool - Web & CLI

Công cụ xác minh sinh viên Google One AI Premium (Gemini Advanced 2TB + Veo + NotebookLM Pro) qua cổng SheerID.

Hỗ trợ **Giao diện Web trực quan**, triển khai lên **Railway** hoặc chạy cục bộ (CLI / Web).

---

## 🌟 Tính năng nổi bật

- 🌐 **Giao diện Web Console hiện đại**:
  - Giao diện Dark mode tối ưu cho cả máy tính và điện thoại.
  - Theo dõi tiến trình xác minh và xem **Terminal Console Live Log** theo thời gian thực (Server-Sent Events).
  - Tự động sinh và hiển thị ảnh xem trước: **Thẻ sinh viên Scan (ID Card)**, **Thời khóa biểu (Class Schedule)**, **Biên lai học phí (Tuition Receipt)**.
  - Hỗ trợ tải về ảnh giấy tờ để tự nộp thủ công nếu muốn.
- 🚀 **Tự động hóa hoàn toàn (Full Automation)**:
  - Tự động sinh danh tính sinh viên Mỹ (Họ tên, DOB, Email EDU, NetID, Mã số SV).
  - Giải CAPTCHA Cloudflare Turnstile qua 2Captcha API.
  - Tự động vượt bước SSO của trường đại học.
  - Upload trực tiếp tài liệu lên S3 của SheerID và kích hoạt quá trình duyệt.
  - **Auto Polling**: Liên tục theo dõi kết quả trả về trong thời gian thực.
- 🛡️ **Anti-Detection & Quản lý IP Dân Cư**:
  - Tự động cấp phát và gán **Sticky Residential Proxy IP** (Proxy-Cheap Mỹ).
  - Kiểm tra và theo dõi IP xuyên suốt phiên xác minh để tránh bị đổi IP giữa chừng.
  - Giả lập vân tay trình duyệt (User-Agent, NewRelic headers, Fingerprint hash).
- 🏫 **Phân chia phong cách trường học (Ivy vs State)**:
  - UC Berkeley (State)
  - MIT - Massachusetts Institute of Technology (Ivy)
  - Harvard University (Ivy)
  - UIUC - University of Illinois (State)
  - UPenn - University of Pennsylvania (Ivy)
  - University of Florida (State)

---

## 🚀 Hướng dẫn Triển khai lên Railway (Deploy to Railway)

### Cách 1: Triển khai qua GitHub (Khuyên dùng)

1. Đưa mã nguồn lên GitHub của bạn:
   ```bash
   cd D:\gem-doc\one-verify-tool
   git init
   git add .
   git commit -m "feat: initial commit for Railway deployment"
   git branch -M main
   git remote add origin https://github.com/<username>/one-verify-tool.git
   git push -u origin main
   ```
2. Đăng nhập vào [Railway.app](https://railway.app/).
3. Nhấn **New Project** ➔ Chọn **Deploy from GitHub repo** ➔ Chọn repository `one-verify-tool`.
4. Railway sẽ tự động phát hiện `Dockerfile` và xây dựng ứng dụng với Chromium headless và Python.
5. Cấu hình biến môi trường (Variables) trên Railway:
   - `PORT`: Railway tự cấp (mặc định 8080).
   - `CAPTCHA_API_KEY`: Key giải Captcha 2Captcha của bạn.
   - `HCTI_USER_ID`: (Tùy chọn) User ID của HCTI API.
   - `HCTI_API_KEY`: (Tùy chọn) API Key của HCTI API.
   - `PROXY_USER`: (Tùy chọn) Username proxy dân cư Proxy-Cheap.
   - `PROXY_PASS_BASE`: (Tùy chọn) Password gốc của proxy dân cư.
   - `PROXY_HOST`: `thehub.proxy-cheap.com`
   - `PROXY_PORT`: `8080`
6. Vào tab **Settings** ➔ Tại mục **Networking**, nhấn **Generate Domain** để nhận đường link truy cập web (ví dụ: `https://one-verify-production.up.railway.app`).

---

## 💻 Hướng dẫn Chạy Cục bộ (Local)

### 1. Cài đặt thư viện

```bash
pip install -r requirements.txt
```

### 2. Khởi chạy Giao diện Web

```bash
python app.py
```
Hoặc:
```bash
python main.py --web
```
Truy cập trình duyệt tại: **http://localhost:8080**

### 3. Khởi chạy giao diện dòng lệnh (CLI)

```bash
# Nhập link tương tác qua terminal:
python main.py

# Hoặc truyền trực tiếp link:
python main.py "https://services.sheerid.com/verify/67c8c14f5f17a83b745e3f82/?verificationId=..."

# Chỉ tạo giấy tờ, không nộp:
python main.py "URL" --docs-only
```

---

## 📡 API Endpoints (Dành cho Bot / Tự động hóa)

Công cụ cung cấp REST API kèm Swagger UI tại `/docs`:

- `GET /health`: Kiểm tra trạng thái máy chủ (Healthcheck).
- `GET /api/stats`: Lấy thống kê tỷ lệ thành công.
- `GET /api/universities`: Danh sách các trường đại học hỗ trợ.
- `POST /api/verify`: Bắt đầu tiến trình xác minh.
- `GET /api/verify/{task_id}/events`: Stream log thời gian thực qua Server-Sent Events (SSE).
- `GET /api/verify/{task_id}/status`: Kiểm tra trạng thái tiến trình qua JSON.
- `GET /api/docs/{dir_name}/{filename}`: Tải về tài liệu đã tạo.
