# 🤖 Prompt Engineer Automation Assignment

> **Automation pipeline**: Google Sheets → OpenAI/DEMO → Google Drive → Slack/Email → SQLite logs → Daily Report

## 📌 Giới thiệu

Dự án này tự động hoá việc tạo game assets (ảnh/audio) từ mô tả trong Google Sheets, sau đó upload lên Google Drive, thông báo qua Slack/Email, và ghi log để xuất báo cáo hằng ngày.

---

## 📂 Cấu trúc thư mục

```
prompt-engineer-automation-assignment/
│
├── runner.py                 # Code chính (đọc Sheet → sinh output → upload Drive → notify → log)
├── requirements.txt          # Danh sách thư viện Python
├── .env.example              # Mẫu cấu hình môi trường
├── .gitignore                # Bỏ qua file nhạy cảm/không cần commit
├── README.md                 # (file này)
├── outputs/                  # (tạo khi chạy) output local trước khi upload
├── reports/                  # (tạo khi chạy) biểu đồ/báo cáo tổng hợp
├── logs.db                   # (tạo khi chạy) SQLite lưu lịch sử
└── docs/                     # Tài liệu minh hoạ cho README
    ├── banner.png
    ├── pipeline.png
    ├── demo-sheet.png
    ├── demo-drive.png
    └── demo-report.png
```

---

## ⚙️ Cài đặt & Chuẩn bị

### 1️⃣ Clone & tạo môi trường

```bash
git clone https://github.com/vanhai1231/prompt-engineer-automation-assignment.git
cd prompt-engineer-automation-assignment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2️⃣ File cấu hình cần có

- **`.env`**: tạo từ `.env.example` và điền giá trị thật
- **`credentials.json`**: Service Account JSON (dùng cho Sheets)
- **`client_secret.json`**: OAuth Client (Desktop) dùng cho Drive
- Bật Sheets API trong Google Cloud
- Share file Google Sheet cho email của Service Account (quyền Editor)
- Lần chạy đầu script sẽ mở trình duyệt xin quyền → tạo `token.json`

#### 📝 Ví dụ file `.env`:

```env
OPENAI_API_KEY=sk-xxxx
GOOGLE_SHEET_URL=1hcV1NAXLXPj-AeDrnS4qTXgXy0hQvQ81gHNHFeLmV8k
GOOGLE_DRIVE_PARENT_FOLDER_ID=1jBZnYFS6gdavWis2OPJO1TmfrvGpo3rp
SLACK_WEBHOOK_URL=
ADMIN_EMAIL=youremail@gmail.com
SMTP_USER=youremail@gmail.com
SMTP_APP_PASSWORD=

# Tuỳ chọn / tiện ích
DEMO_MODE=1        # 1: sinh output giả lập (bypass billing) | 0: gọi API thật
RETRY_FAILED=1     # chạy lại các dòng status=failed
SKIP_EMAIL=1       # bỏ qua gửi email khi test
SKIP_SLACK=1       # bỏ qua gửi Slack khi test
```

> **💡 Lưu ý quota Drive**: Service Account không có quota Drive cá nhân. Repo này chọn **Cách A**: dùng OAuth người dùng để upload file lên Drive (file thuộc tài khoản của bạn). Vì vậy cần `client_secret.json` (Desktop app) và `token.json` sẽ được tạo sau khi cấp quyền lần đầu.

---

## 🧪 Chuẩn bị Google Sheet

### 📊 Header (hàng 1) phải đúng thứ tự:

| id | description | example_asset_url | output_format | model | status | output_url | error |
|----|-------------|-------------------|---------------|-------|--------|------------|-------|

### 📋 Quy tắc:
- **`output_format`** ∈ `{PNG, JPG, GIF, MP3}`
- **`model`** ∈ `{OpenAI, Claude}`
- Để **`status`** trống cho các dòng cần xử lý

> 💡 Có thể dùng Apps Script (trong menu Extensions) để Seed sample data nhanh (kèm menu Automation Test).

---

## 🚀 Chạy chương trình

```bash
python runner.py
```

### 🔄 Quy trình hoạt động:
1. Script đọc các dòng có `status` trống → tạo output theo `output_format`
2. Upload file lên Google Drive (thư mục `GOOGLE_DRIVE_PARENT_FOLDER_ID`)
3. Cập nhật `status=done`, `output_url` trên Sheet
4. Gửi Slack/Email (nếu không bật SKIP)
5. Lưu log vào `logs.db`

---

## 📊 Báo cáo hằng ngày

### 📈 Tạo báo cáo thủ công:

```bash
python -c "from runner import daily_report; daily_report()"
```

- Ảnh báo cáo lưu tại `reports/summary_*.png` và upload lên Drive

### ⏰ Tự động hoá với cron (macOS):

```bash
crontab -e
# Chạy lúc 20:00 mỗi ngày
0 20 * * * cd /path/to/repo && /path/to/repo/.venv/bin/python -c "from runner import daily_report; daily_report()" >> cron.log 2>&1
```

---

## 💡 DEMO MODE

Nếu hết hạn mức OpenAI hoặc muốn demo nhanh mà không tốn API call:

```env
DEMO_MODE=1
```

### ✨ Tính năng:
- Ảnh sẽ là placeholder có in prompt
- MP3 là sample file 
- Workflow vẫn chạy đủ bước
- Khi sẵn sàng chuyển sang chạy thật: `DEMO_MODE=0` + điền `OPENAI_API_KEY` hợp lệ

---

## 🔔 Thông báo (Email/Slack)

### 📧 Email (SMTP Gmail):
- Cần bật **2-Step Verification** → **App Password** → đặt `SMTP_APP_PASSWORD`

### 📱 Slack:
- Tạo **Incoming Webhook** và điền `SLACK_WEBHOOK_URL`

### 🧪 Check nhanh:
- Nếu chưa muốn cấu hình: đặt `SKIP_EMAIL=1`, `SKIP_SLACK=1`
- Tạo 1 dòng cố ý fail (ví dụ `output_format=SVG`) để kiểm tra đường đi thông báo thất bại

---

## 🛠 Troubleshooting

| 🚨 Triệu chứng | 🔍 Nguyên nhân | ✅ Cách khắc phục |
|----------------|----------------|-------------------|
| Service Accounts do not have storage quota | Upload bằng SA, SA không có quota Drive | Dùng OAuth người dùng (Cách A) hoặc Shared Drive |
| Billing hard limit has been reached | Hết hạn mức OpenAI | Bật `DEMO_MODE=1` hoặc tăng hạn mức/nạp thêm |
| 401 Invalid API key | `OPENAI_API_KEY` sai/expired | Tạo key mới, đảm bảo không có khoảng trắng |
| NoValidUrlKeyFound | `GOOGLE_SHEET_URL` sai | Điền ID thuần hoặc URL chuẩn của Google Sheet |
| Không gửi email | Thiếu App Password | Bật 2FA + App Password, hoặc `SKIP_EMAIL=1` |
| Slack không nhận | Webhook sai/chưa cài app | Tạo lại Incoming Webhook |

---

## 🧱 Kiến trúc & Ghi chú kỹ thuật

### 🏗️ Thành phần chính:
- **Sheets (SA)**: dùng Service Account để đọc/ghi dữ liệu ổn định, không cần người dùng tương tác
- **Drive (OAuth user)**: upload bằng tài khoản của bạn để có quota & sở hữu file
- **OpenAI**: `gpt-image-1` cho ảnh; `gpt-4o-mini-tts` cho TTS (khi `DEMO_MODE=0`)
- **Fallback**: khi gặp lỗi billing, hệ thống tự sinh placeholder để pipeline không gãy
- **Logging**: SQLite `logs.db`, phục vụ báo cáo hằng ngày và audit

### 🔄 Sơ đồ tổng quát:

```
Google Sheets  →  (OpenAI / DEMO)  →  Google Drive (OAuth)  →  Slack/Email
       ↓                             ↑
      SQLite logs  ←  runner.py  ←  daily_report()
```

---

## 📥 Nộp bài (gợi ý)

- 🔗 Link repo GitHub (repo này)
- 🎥 Video demo (3–5 phút) quay flow end-to-end
- 📸 Screenshots: Sheet sau khi chạy, Drive có file, báo cáo, thông báo Slack/Email

---

## 📜 License

MIT