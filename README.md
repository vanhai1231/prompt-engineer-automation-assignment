Prompt‑Engineer Automation Assignment

Automation pipeline: Google Sheets → (OpenAI / DEMO mode) → Google Drive → Slack / Email → SQLite logs → Daily Report.

📌 Giới thiệu

Dự án này tự động hoá việc tạo game assets (ảnh/audio) từ mô tả trong Google Sheets, sau đó upload lên Google Drive, thông báo qua Slack/Email, và ghi log để xuất báo cáo hằng ngày.


⸻

📂 Cấu trúc thư mục

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


⸻

⚙️ Cài đặt & Chuẩn bị

1) Clone & tạo môi trường

git clone https://github.com/vanhai1231/prompt-engineer-automation-assignment.git
cd prompt-engineer-automation-assignment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

2) File cấu hình cần có
	•	.env: tạo từ .env.example và điền giá trị thật (xem ví dụ bên dưới)
	•	credentials.json: Service Account JSON (dùng cho Sheets)
	•	Bật Sheets API trong Google Cloud.
	•	Share file Google Sheet cho email của Service Account (quyền Editor).
	•	client_secret.json: OAuth Client (Desktop) dùng cho Drive (Cách A – để có quota cá nhân)
	•	Lần chạy đầu script sẽ mở trình duyệt xin quyền → tạo token.json (lưu lại để chạy lần sau).

Ví dụ .env:

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

Lưu ý quota Drive: Service Account không có quota Drive cá nhân. Repo này chọn Cách A: dùng OAuth người dùng để upload file lên Drive (file thuộc tài khoản của bạn). Vì vậy cần client_secret.json (Desktop app) và token.json sẽ được tạo sau khi cấp quyền lần đầu.

⸻

🧪 Chuẩn bị Google Sheet

Header (hàng 1) phải đúng thứ tự:

id | description | example_asset_url | output_format | model | status | output_url | error

	•	output_format ∈ {PNG, JPG, GIF, MP3}
	•	model ∈ {OpenAI, Claude}
	•	Để status trống cho các dòng cần xử lý.

Có thể dùng Apps Script (trong menu Extensions) để Seed sample data nhanh (kèm menu Automation Test).


⸻

🚀 Chạy chương trình

python runner.py

Khi chạy:
	•	Script đọc các dòng có status trống → tạo output theo output_format.
	•	Upload file lên Google Drive (thư mục GOOGLE_DRIVE_PARENT_FOLDER_ID).
	•	Cập nhật status=done, output_url trên Sheet.
	•	Gửi Slack/Email (nếu không bật SKIP).
	•	Lưu log vào logs.db.


⸻

📊 Báo cáo hằng ngày

Tạo biểu đồ tổng hợp success/fail và gửi báo cáo:

python -c "from runner import daily_report; daily_report()"

	•	Ảnh báo cáo lưu tại reports/summary_*.png và upload lên Drive.

Muốn tự động hoá hằng ngày, thiết lập cron (macOS):

crontab -e
# ví dụ 20:00 mỗi ngày
0 20 * * * cd /path/to/repo && /path/to/repo/.venv/bin/python -c "from runner import daily_report; daily_report()" >> cron.log 2>&1


⸻

💡 DEMO MODE

Nếu hết hạn mức OpenAI (Billing hard limit) hoặc muốn demo nhanh mà không tốn API call:

DEMO_MODE=1

	•	Ảnh sẽ là placeholder có in prompt, MP3 là sample file – workflow vẫn chạy đủ bước.
	•	Khi sẵn sàng chuyển sang chạy thật: DEMO_MODE=0 + điền OPENAI_API_KEY hợp lệ.


⸻

🔔 Thông báo (Email/Slack)
	•	Email (SMTP Gmail): cần bật 2‑Step Verification → App Password → đặt SMTP_APP_PASSWORD.
	•	Slack: tạo Incoming Webhook và điền SLACK_WEBHOOK_URL.

Check nhanh:
	•	Nếu chưa muốn cấu hình: đặt SKIP_EMAIL=1, SKIP_SLACK=1.
	•	Tạo 1 dòng cố ý fail (ví dụ output_format=SVG) để kiểm tra đường đi thông báo thất bại.

⸻

🛠 Troubleshooting

Triệu chứng	Nguyên nhân	Cách khắc phục
Service Accounts do not have storage quota	Upload bằng SA, SA không có quota Drive	Dùng OAuth người dùng (Cách A) hoặc Shared Drive
Billing hard limit has been reached	Hết hạn mức OpenAI	Bật DEMO_MODE=1 hoặc tăng hạn mức/nạp thêm
401 Invalid API key	OPENAI_API_KEY sai/expired	Tạo key mới, đảm bảo không có khoảng trắng
NoValidUrlKeyFound	GOOGLE_SHEET_URL sai	Điền ID thuần hoặc URL chuẩn của Google Sheet
Không gửi email	Thiếu App Password	Bật 2FA + App Password, hoặc SKIP_EMAIL=1
Slack không nhận	Webhook sai/chưa cài app	Tạo lại Incoming Webhook


⸻

🧱 Kiến trúc & Ghi chú kỹ thuật
	•	Sheets (SA): dùng Service Account để đọc/ghi dữ liệu ổn định, không cần người dùng tương tác.
	•	Drive (OAuth user): upload bằng tài khoản của bạn để có quota & sở hữu file.
	•	OpenAI: gpt-image-1 cho ảnh; gpt-4o-mini-tts cho TTS (khi DEMO_MODE=0).
	•	Fallback: khi gặp lỗi billing, hệ thống tự sinh placeholder để pipeline không gãy.
	•	Logging: SQLite logs.db, phục vụ báo cáo hằng ngày và audit.

Sơ đồ tổng quát:

Google Sheets  →  (OpenAI / DEMO)  →  Google Drive (OAuth)  →  Slack/Email
       ↓                             ↑
      SQLite logs  ←  runner.py  ←  daily_report()


⸻

📥 Nộp bài (gợi ý)
	•	Link repo GitHub (repo này).
	•	Video demo (3–5 phút) quay flow end‑to‑end.
	•	Screenshots: Sheet sau khi chạy, Drive có file, báo cáo, thông báo Slack/Email.

⸻

📜 License

MIT.