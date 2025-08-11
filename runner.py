import os, io, time, sqlite3, json, re
from datetime import datetime
from email.mime.text import MIMEText
import smtplib

from dotenv import load_dotenv
import requests
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from slack_sdk.webhook import WebhookClient
from PIL import Image, ImageDraw
import matplotlib.pyplot as plt

# ====== OAuth (Drive - User) ======
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as UserCredentials
from google_auth_oauthlib.flow import InstalledAppFlow

# ================= ENV =================
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SHEET_URL_OR_ID = os.getenv("GOOGLE_SHEET_URL")
PARENT_FOLDER_ID = os.getenv("GOOGLE_DRIVE_PARENT_FOLDER_ID")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
SMTP_USER = os.getenv("SMTP_USER")
SMTP_APP_PASSWORD = os.getenv("SMTP_APP_PASSWORD")

# Flags tiện lợi
DEMO_MODE = os.getenv("DEMO_MODE") == "1"
RETRY_FAILED = os.getenv("RETRY_FAILED") == "1"
SKIP_EMAIL = os.getenv("SKIP_EMAIL") == "1"
SKIP_SLACK = os.getenv("SKIP_SLACK") == "1"

# ================= OPENAI =================
try:
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
except Exception:
    client = None

# ================= GOOGLE (Sheets via Service Account) =================
SCOPES_SA = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.metadata.readonly",
]
if not os.path.exists("credentials.json") or os.path.getsize("credentials.json") == 0:
    raise SystemExit("❌ credentials.json thiếu hoặc rỗng. Tải JSON key của Service Account và đặt tên đúng.")

sa_creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES_SA)
gc = gspread.authorize(sa_creds)

def open_sheet_from_env(gc, url_or_id: str):
    if not url_or_id:
        raise SystemExit("❌ GOOGLE_SHEET_URL trống. Điền link hoặc ID Google Sheets vào .env")
    if re.fullmatch(r"[A-Za-z0-9-_]{20,}", url_or_id.strip()):
        return gc.open_by_key(url_or_id.strip()).sheet1
    if url_or_id.startswith("https://docs.google.com/spreadsheets/d/"):
        return gc.open_by_url(url_or_id.strip()).sheet1
    raise SystemExit("❌ GOOGLE_SHEET_URL không phải link Sheets hoặc ID hợp lệ.")

sheet = open_sheet_from_env(gc, SHEET_URL_OR_ID)

# ================= GOOGLE DRIVE (via User OAuth) =================
USER_DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.file"]

def get_user_drive():
    """
    Dùng OAuth người dùng để upload file vào Drive (thuộc tài khoản của bạn, có quota).
    Cần có client_secret.json (Desktop App) cùng thư mục.
    """
    creds = None
    if os.path.exists("token.json"):
        creds = UserCredentials.from_authorized_user_file("token.json", USER_DRIVE_SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists("client_secret.json"):
                raise SystemExit("❌ Thiếu client_secret.json (OAuth Desktop app). Tạo trong Google Cloud → OAuth client ID (Desktop).")
            flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", USER_DRIVE_SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as f:
            f.write(creds.to_json())
    return build("drive", "v3", credentials=creds)

drive = get_user_drive()

# ================= DB =================
os.makedirs("outputs", exist_ok=True)
os.makedirs("reports", exist_ok=True)
conn = sqlite3.connect("logs.db")
c = conn.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS logs(
    ts TEXT, row_id TEXT, description TEXT, example_url TEXT,
    output_format TEXT, model TEXT, output_url TEXT, status TEXT, error TEXT
)
""")
conn.commit()

# ================= Utils =================
def send_slack(text: str):
    try:
        if SKIP_SLACK or not SLACK_WEBHOOK_URL:
            print("[SLACK skipped]", text); return
        WebhookClient(SLACK_WEBHOOK_URL).send(text=text)
    except Exception as e:
        print("[SLACK error]", e)

def send_email(to_email, subject, body):
    try:
        if SKIP_EMAIL or not (SMTP_USER and SMTP_APP_PASSWORD and to_email):
            print("[EMAIL skipped]", subject); return
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = SMTP_USER
        msg["To"] = to_email
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SMTP_USER, SMTP_APP_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        print("[EMAIL error]", e)

def upload_to_drive(local_path, parent_folder_id):
    name = os.path.basename(local_path)
    media = MediaFileUpload(local_path, resumable=True)
    file_metadata = {"name": name, "parents": [parent_folder_id]}
    created = drive.files().create(
        body=file_metadata, media_body=media, fields="id"
    ).execute()
    file_id = created.get("id")
    # Cho phép xem qua link (optional)
    try:
        drive.permissions().create(fileId=file_id, body={"type": "anyone", "role": "reader"}).execute()
    except Exception as e:
        print("[Drive permission warn]", e)
    return f"https://drive.google.com/file/d/{file_id}/view"

def log_row(row_id, description, example, fmt, model, url, status, error=""):
    c.execute("INSERT INTO logs VALUES (?,?,?,?,?,?,?,?,?)",
              (datetime.utcnow().isoformat(), str(row_id), description, example, fmt, model, url, status, error))
    conn.commit()

def optimize_prompt_with_claude(raw_prompt):
    return (raw_prompt +
            "\n\nConstraints: high-quality game-ready asset, consistent style, sharp edges, clean silhouette, "
            "plain background, center composition, lighting consistent, no watermark, 1024x1024.")

# ---- Placeholders for DEMO / billing fallback ----
def placeholder_image_from_prompt(prompt, fmt="PNG", size=(1024, 1024)):
    img = Image.new("RGB", size, (240, 240, 240))
    draw = ImageDraw.Draw(img)
    draw.rectangle([(40, 40), (size[0]-40, size[1]-40)], outline=(120,120,120), width=4)
    header = "DEMO MODE (no OpenAI call)\n"
    text = (prompt or "demo image")[:200]
    draw.text((60, 60), header + text, fill=(50,50,50))
    buf = io.BytesIO()
    img.save(buf, format=fmt.upper())
    return buf.getvalue()

def placeholder_mp3_bytes():
    url = "https://filesamples.com/samples/audio/mp3/sample3.mp3"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.content

# ---- OpenAI helpers with fallback ----
def openai_generate_image(prompt, size="1024x1024"):
    if DEMO_MODE or client is None:
        w, h = map(int, size.split("x"))
        return placeholder_image_from_prompt(prompt, "PNG", (w, h))
    try:
        resp = client.images.generate(model="gpt-image-1", prompt=prompt, size=size)
        image_url = resp.data[0].url
        return requests.get(image_url, timeout=60).content
    except Exception as e:
        msg = str(e).lower()
        if "billing" in msg or "hard limit" in msg or "limit has been reached" in msg:
            w, h = map(int, size.split("x"))
            return placeholder_image_from_prompt(prompt, "PNG", (w, h))
        raise

def openai_tts_to_mp3(text):
    if DEMO_MODE or client is None:
        return placeholder_mp3_bytes()
    try:
        audio = client.audio.speech.with_streaming_response.create(
            model="gpt-4o-mini-tts",
            voice="alloy",
            input=text or "Sample voice for the game asset pipeline.",
            format="mp3",
        )
        buf = io.BytesIO()
        for chunk in audio.iter_bytes():
            buf.write(chunk)
        buf.seek(0)
        return buf.read()
    except Exception as e:
        msg = str(e).lower()
        if "billing" in msg or "hard limit" in msg or "limit has been reached" in msg:
            return placeholder_mp3_bytes()
        raise

def png_to_jpg(png_bytes):
    im = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    out = io.BytesIO()
    im.save(out, format="JPEG", quality=95)
    return out.getvalue()

def png_to_gif(png_bytes):
    im = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    out = io.BytesIO()
    im.save(out, format="GIF")
    return out.getvalue()

# ================= Core =================
def process_row(row_idx, record):
    row_id = record.get("id") or row_idx
    desc = (record.get("description") or "").strip()
    example = (record.get("example_asset_url") or "").strip()
    fmt = (record.get("output_format") or "PNG").strip().upper()
    model = (record.get("model") or "OpenAI").strip()

    prompt = desc
    if example:
        prompt += f"\nReference: {example}"
    if model.lower() == "claude":
        prompt = optimize_prompt_with_claude(prompt)

    try:
        output_local = None
        ts = int(time.time())

        if fmt in ["PNG", "JPG", "GIF"]:
            png_bytes = openai_generate_image(prompt, "1024x1024")
            if fmt == "PNG":
                output_local = f"outputs/{row_id}_{ts}.png"
                with open(output_local, "wb") as f: f.write(png_bytes)
            elif fmt == "JPG":
                jpg_bytes = png_to_jpg(png_bytes)
                output_local = f"outputs/{row_id}_{ts}.jpg"
                with open(output_local, "wb") as f: f.write(jpg_bytes)
            elif fmt == "GIF":
                gif_bytes = png_to_gif(png_bytes)
                output_local = f"outputs/{row_id}_{ts}.gif"
                with open(output_local, "wb") as f: f.write(gif_bytes)

        elif fmt == "MP3":
            audio_bytes = openai_tts_to_mp3(desc or "Sample voice for the game asset pipeline.")
            output_local = f"outputs/{row_id}_{ts}.mp3"
            with open(output_local, "wb") as f: f.write(audio_bytes)
        else:
            raise ValueError(f"Unsupported output_format: {fmt}")

        output_url = upload_to_drive(output_local, PARENT_FOLDER_ID)

        send_slack(f"✅ Row {row_id}: {fmt} created. {output_url}")
        send_email(ADMIN_EMAIL, f"[OK] Asset generated for row {row_id}", output_url)

        log_row(row_id, desc, example, fmt, model, output_url, "success", "")
        sheet.update_cell(row_idx, 6, "done")
        sheet.update_cell(row_idx, 7, output_url)
        sheet.update_cell(row_idx, 8, "")
        return True

    except Exception as e:
        err = str(e)[:500]
        print(f"[ERROR] Row {row_id}: {err}")
        send_slack(f"❌ Row {row_id} failed: {err}")
        try:
            send_email(ADMIN_EMAIL, f"[FAIL] Row {row_id}", err)
        except Exception:
            pass
        log_row(row_id, desc, example, fmt, model, "", "fail", err)
        sheet.update_cell(row_idx, 6, "failed")
        sheet.update_cell(row_idx, 7, "")
        sheet.update_cell(row_idx, 8, err)
        return False

def run_once():
    records = sheet.get_all_records()
    for i, rec in enumerate(records):
        status = (rec.get("status") or "").strip().lower()
        if status == "done":
            continue
        if status == "failed" and not RETRY_FAILED:
            continue
        row_idx = i + 2
        process_row(row_idx, rec)

def daily_report():
    cur = conn.cursor()
    cur.execute("SELECT status, COUNT(*) FROM logs GROUP BY status")
    stats = dict(cur.fetchall())
    ok = stats.get("success", 0); fail = stats.get("fail", 0)

    plt.figure()
    plt.bar(["success", "fail"], [ok, fail])
    plt.title(f"Tasks Summary – success={ok}, fail={fail}")
    report_path = f"reports/summary_{int(time.time())}.png"
    plt.savefig(report_path, dpi=160, bbox_inches="tight")

    report_link = upload_to_drive(report_path, PARENT_FOLDER_ID)
    send_email(ADMIN_EMAIL, "[Daily Report] Automation Summary", f"Success={ok}, Fail={fail}\n{report_link}")
    send_slack(f"📈 Daily report sent. Success={ok}, Fail={fail}\n{report_link}")

# ================= Main =================
if __name__ == "__main__":
    print("== START ==")
    print("SHEET:", SHEET_URL_OR_ID)
    print("DEMO_MODE:", DEMO_MODE, "| RETRY_FAILED:", RETRY_FAILED, "| SKIP_EMAIL:", SKIP_EMAIL, "| SKIP_SLACK:", SKIP_SLACK)

    recs = sheet.get_all_records()
    print("Rows:", len(recs))
    for i, r in enumerate(recs):
        print(f"Row {i+2} -> status={r.get('status')}, fmt={r.get('output_format')}, model={r.get('model')}")

    print("== PROCESS ==")
    run_once()
    print("== DONE ==")
    # daily_report()