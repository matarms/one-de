"""
Google One (Gemini) Student Verification Tool
SheerID Student Verification for Google One AI Premium

Enhanced with:
- AUTO POLLING (Waits for SheerID approval/rejection in real-time)
- PROXY IP TRACKING (Shows Current Time & IP at each step)
- FULLY AUTOMATED SUBMISSION (No manual approval required)
- Multi-Style University Templates (Ivy vs State)
"""

import os
import re
import sys
import json
import time
import random
import string
import hashlib
import base64
import webbrowser
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

try:
    import httpx
except ImportError:
    print("❌ Error: httpx required. Install: pip install httpx")
    sys.exit(1)

try:
    from twocaptcha import TwoCaptcha
except ImportError:
    print("❌ Error: 2captcha-python required. Install: pip install 2captcha-python")
    sys.exit(1)

# Import anti-detection module
try:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from anti_detect import (
        get_headers,
        get_fingerprint,
        get_random_user_agent,
        random_delay as anti_delay,
        create_session,
    )
    HAS_ANTI_DETECT = True
    print("[INFO] Anti-detection module loaded")
except ImportError:
    HAS_ANTI_DETECT = False
    print("[WARN] anti_detect.py not found, using basic headers")


# ============ CONFIG ============
PROGRAM_ID = "67c8c14f5f17a83b745e3f82"
SHEERID_API_URL = "https://services.sheerid.com/rest/v2"
MIN_DELAY = 300
MAX_DELAY = 800
OUTPUT_DIR = Path(__file__).parent / "output"

# 2Captcha & HCTI Keys
CAPTCHA_API_KEY = "ecc6bc9b27e7d71e42b583e175b1e865"
HCTI_USER_ID = "01M799KYJQ86GW2CVNZJQPQ3HC"
HCTI_API_KEY = "h1-7gM9UGXeDVmG6JTxOLmuemjg-e3e257fc"

# ==========================================
# CẤU HÌNH PROXY TRUEPROXIES CỦA BẠN
# ==========================================
HARDCODED_PROXY = "http://et034zfrxsey-country-us-lifetime-600-session-usmvqoku:ylWlrAhG6Z9DxHYZWUhV@resi-ipv4-6.gw.tprx.io:8080"
DEFAULT_SITEKEY = "0x4AAAAAACaWNlR_tN9-HfHj"


def get_current_time() -> str:
    return datetime.now().strftime('%H:%M:%S')

def generate_session_id(length: int = 8) -> str:
    """Tạo session ngẫu nhiên mới cho residential proxy"""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

def create_session_proxy(base_proxy: str, new_session: str = None) -> str:
    """Thay thế hoặc thêm session mới vào chuỗi proxy residential"""
    if not new_session:
        new_session = generate_session_id()
    if "-session-" in base_proxy:
        return re.sub(r"-session-[a-zA-Z0-9]+", f"-session-{new_session}", base_proxy)
    if "@" in base_proxy:
        protocol, rest = base_proxy.split("://", 1)
        auth, host = rest.split("@", 1)
        if ":" in auth:
            user, pwd = auth.split(":", 1)
            return f"{protocol}://{user}-session-{new_session}:{pwd}@{host}"
    return base_proxy

def check_proxy_ip(proxy_url: str, timeout: int = 12) -> str:
    """Kiểm tra IP hiện tại của Proxy qua nhiều endpoint dự phòng"""
    endpoints = [
        "https://api.ipify.org?format=json",
        "https://api64.ipify.org?format=json",
        "https://httpbin.org/ip"
    ]
    for ep in endpoints:
        try:
            resp = httpx.get(ep, proxy=proxy_url, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                if "ip" in data:
                    return data["ip"]
                if "origin" in data:
                    return data["origin"].split(",")[0].strip()
        except Exception:
            continue
    return "Unknown"

def rotate_residential_proxy(base_proxy: str, max_retries: int = 5) -> Tuple[str, str, str]:
    """
    Đổi IP dân cư trước khi chạy:
    1. Kiểm tra và lấy IP hiện tại
    2. Cấp phát session mới và kiểm tra IP mới
    3. Đảm bảo IP mới khác IP cũ
    Trả về: (proxy_mới, ip_cũ, ip_mới)
    """
    old_ip = check_proxy_ip(base_proxy)
    
    for attempt in range(1, max_retries + 1):
        candidate_proxy = create_session_proxy(base_proxy)
        candidate_ip = check_proxy_ip(candidate_proxy)
        
        if candidate_ip != "Unknown" and not candidate_ip.startswith("Error") and candidate_ip != old_ip:
            return candidate_proxy, old_ip, candidate_ip
            
        if candidate_ip != "Unknown" and not candidate_ip.startswith("Error") and attempt == max_retries:
            return candidate_proxy, old_ip, candidate_ip
            
        time.sleep(1)
        
    return base_proxy, old_ip, old_ip


# ============ DATABASE (PHÂN CHIA STYLE RÕ RÀNG) ============
UNIVERSITIES = [
    {
        "id": 3629, "name": "University of Pennsylvania", "domain": "upenn.edu", "weight": 90,
        "style": "Ivy", 
        "primary_color": "#011F5B", "secondary_color": "#990000",
        "address": "3451 Walnut St, Philadelphia, PA 19104", "phone": "(215) 898-5000", "financial_dept": "Student Financial Services",
        "registrar": "Margaret Kip",
        "tuition": 32835, "housing": 6822, "food": 3480, 
        "courses": [("CIS 1100", "Intro to Computer Programming", "MW", "10:15 - 11:30", "Levine Hall 101"), ("MATH 1400", "Calculus I", "TuTh", "09:00 - 10:20", "David Rittenhouse Lab A1"), ("PHYS 0101", "General Physics", "MWF", "11:00 - 12:00", "Dunning Hall"), ("ENGL 1010", "Writing Seminar", "F", "13:00 - 15:00", "Fisher-Bennett 401")]
    },
    {
        "id": 3491, "name": "University of California, Berkeley", "domain": "berkeley.edu", "weight": 97,
        "style": "State",
        "primary_color": "#003262", "secondary_color": "#FDB515",
        "address": "110 Sproul Hall, Berkeley, CA 94720", "phone": "(510) 642-6000", "financial_dept": "Billing and Payment Services",
        "registrar": "Dr. Sarah Jenkins",
        "tuition": 14200, "housing": 10400, "food": 4600, 
        "courses": [("CS 61A", "Structure and Interpretation of Computer Programs", "MWF", "10:00 - 11:00", "Wheeler 150"), ("MATH 1A", "Calculus", "TuTh", "08:00 - 09:30", "Evans 10"), ("ENGLISH R1A", "Reading and Composition", "MWF", "12:00 - 13:00", "Dwinelle 155"), ("ECON 1", "Introduction to Economics", "TuTh", "14:00 - 15:30", "Hearst Mining 290")]
    },
    {
        "id": 1426, "name": "Harvard University", "domain": "harvard.edu", "weight": 92,
        "style": "Ivy",
        "primary_color": "#A51C30", "secondary_color": "#FFFFFF",
        "address": "86 Brattle Street, Cambridge, MA 02138", "phone": "(617) 495-1000", "financial_dept": "Student Financial Services",
        "registrar": "Dr. Robert Vance",
        "tuition": 26000, "housing": 12000, "food": 4000, 
        "courses": [("CS50", "Introduction to Computer Science", "MWF", "10:00 - 11:30", "Sanders Theatre"), ("MATH 21A", "Multivariable Calculus", "TuTh", "09:00 - 10:30", "Science Center 309"), ("EXPOS 20", "Expository Writing", "Tu", "12:00 - 14:00", "Sever Hall 102"), ("ECON 10A", "Principles of Economics", "MW", "11:00 - 12:00", "Memorial Hall 101")]
    },
    {
        "id": 1953, "name": "Massachusetts Institute of Technology", "domain": "mit.edu", "weight": 95,
        "style": "Ivy",
        "primary_color": "#8A8B8C", "secondary_color": "#A31F34",
        "address": "77 Massachusetts Ave, Cambridge, MA 02139", "phone": "(617) 253-1000", "financial_dept": "Student Financial Services",
        "registrar": "Prof. Alan Turing",
        "tuition": 28500, "housing": 11000, "food": 4500, 
        "courses": [("6.100A", "Intro to Programming", "TuTh", "11:00 - 12:30", "Room 32-123"), ("18.01", "Single Variable Calculus", "MWF", "09:00 - 10:00", "Room 10-250"), ("8.01", "Physics I", "TuTh", "14:00 - 15:30", "Room 26-100"), ("21W.730", "Writing and Rhetoric", "W", "15:00 - 17:00", "Room 14E-304")]
    },
    {
        "id": 3521, "name": "University of Florida", "domain": "ufl.edu", "weight": 90,
        "style": "State",
        "primary_color": "#0021A5", "secondary_color": "#FA4616",
        "address": "Gainesville, FL 32611", "phone": "(352) 392-3261", "financial_dept": "University Bursar",
        "registrar": "Prof. Linda Brown",
        "tuition": 6500, "housing": 6000, "food": 3000, 
        "courses": [("COP 3502", "Programming Fundamentals", "MW", "10:40 - 11:30", "CSE Building E121"), ("MAC 2311", "Analytic Geometry and Calculus 1", "TuTh", "08:30 - 09:45", "Little Hall 109"), ("PHY 2048", "Physics with Calculus 1", "MWF", "12:50 - 13:40", "NPB 1001"), ("ENC 1101", "Expository and Argumentative Writing", "F", "14:00 - 15:50", "Turlington Hall 2312")]
    },
    {
        "id": 3535, "name": "University of Illinois at Urbana-Champaign", "domain": "illinois.edu", "weight": 91,
        "style": "State",
        "primary_color": "#E84A27", "secondary_color": "#13294B",
        "address": "601 E John St, Champaign, IL 61820", "phone": "(217) 333-1000", "financial_dept": "Student Accounts",
        "registrar": "Dr. James Wilson",
        "tuition": 15500, "housing": 7500, "food": 4000, 
        "courses": [("CS 125", "Intro to Computer Science", "MWF", "11:00 - 11:50", "Foellinger Auditorium"), ("MATH 221", "Calculus I", "TuTh", "09:30 - 10:50", "Altgeld Hall 314"), ("PHYS 211", "University Physics: Mechanics", "MWF", "13:00 - 13:50", "Loomis Lab 141"), ("RHET 105", "Writing and Research", "Tu", "14:00 - 15:50", "English Building 160")]
    }
]


# ============ STATS TRACKING ============
class Stats:
    def __init__(self):
        self.file = Path(__file__).parent / "stats.json"
        self.data = self._load()

    def _load(self) -> Dict:
        if self.file.exists():
            try:
                return json.loads(self.file.read_text())
            except Exception:
                pass
        return {"total": 0, "success": 0, "failed": 0, "orgs": {}}

    def _save(self):
        self.file.write_text(json.dumps(self.data, indent=2))

    def record(self, org: str, success: bool):
        self.data["total"] += 1
        self.data["success" if success else "failed"] += 1
        if org not in self.data["orgs"]:
            self.data["orgs"][org] = {"success": 0, "failed": 0}
        self.data["orgs"][org]["success" if success else "failed"] += 1
        self._save()

    def get_rate(self, org: str = None) -> float:
        if org:
            o = self.data["orgs"].get(org, {})
            total = o.get("success", 0) + o.get("failed", 0)
            return o.get("success", 0) / total * 100 if total else 50
        return self.data["success"] / self.data["total"] * 100 if self.data["total"] else 0

    def print_stats(self):
        print(f"\n📊 Statistics:")
        print(f"   Total: {self.data['total']} | ✅ {self.data['success']} | ❌ {self.data['failed']}")
        if self.data["total"]:
            print(f"   Success Rate: {self.get_rate():.1f}%")

stats = Stats()


def select_university() -> Dict:
    weights = [u["weight"] for u in UNIVERSITIES]
    total = sum(weights)
    r = random.uniform(0, total)
    cumulative = 0
    for uni, weight in zip(UNIVERSITIES, weights):
        cumulative += weight
        if r <= cumulative:
            return {**uni, "idExtended": str(uni["id"])}
    return {**UNIVERSITIES[0], "idExtended": str(UNIVERSITIES[0]["id"])}


# ============ UTILITIES ============
FIRST_NAMES_MALE = ["James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph", "Thomas", "Christopher", "Charles", "Daniel", "Matthew", "Anthony", "Mark", "Donald", "Steven", "Andrew", "Paul", "Joshua"]
FIRST_NAMES_FEMALE = ["Mary", "Patricia", "Jennifer", "Linda", "Barbara", "Elizabeth", "Susan", "Jessica", "Sarah", "Karen", "Lisa", "Nancy", "Betty", "Margaret", "Sandra", "Ashley", "Kimberly", "Emily", "Donna", "Michelle"]
LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker", "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores", "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell", "Carter", "Roberts", "Turner", "Phillips", "Evans", "Parker", "Edwards"]

def random_delay():
    time.sleep(random.randint(MIN_DELAY, MAX_DELAY) / 1000)

def generate_fingerprint() -> str:
    resolutions = ["1920x1080", "1366x768", "1536x864", "1440x900", "1280x720", "2560x1440"]
    timezones = [-8, -7, -6, -5, -4, 0, 1, 2, 3, 5.5, 8, 9, 10]
    languages = ["en-US", "en-GB", "en-CA", "en-AU", "es-ES", "fr-FR", "de-DE", "pt-BR"]
    platforms = ["Win32", "MacIntel", "Linux x86_64"]
    vendors = ["Google Inc.", "Apple Computer, Inc.", ""]
    components = [str(int(time.time() * 1000)), str(random.random()), random.choice(resolutions), str(random.choice(timezones)), random.choice(languages), random.choice(platforms), random.choice(vendors), str(random.randint(1, 16)), str(random.randint(2, 32)), str(random.randint(0, 1))]
    return hashlib.md5("|".join(components).encode()).hexdigest()

def generate_name_and_photo() -> Tuple[str, str, str, str]:
    is_male = random.choice([True, False])
    first = random.choice(FIRST_NAMES_MALE) if is_male else random.choice(FIRST_NAMES_FEMALE)
    last = random.choice(LAST_NAMES)
    
    gender_path = "men" if is_male else "women"
    photo_id = random.randint(1, 99)
    photo_url = f"https://randomuser.me/api/portraits/{gender_path}/{photo_id}.jpg"
        
    netid = f"{first[0].lower()}{last[0].lower()}{random.randint(100, 999)}"
    return first, last, photo_url, netid

def generate_email(first: str, last: str, domain: str, netid: str) -> str:
    return f"{netid}@{domain}"

def generate_birth_date() -> str:
    return f"{random.randint(2006, 2007)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"

def create_output_dir(email: str) -> Path:
    safe_email = re.sub(r"[^a-zA-Z0-9@._-]", "_", email)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder = OUTPUT_DIR / f"{safe_email}_{timestamp}"
    folder.mkdir(parents=True, exist_ok=True)
    return folder

def get_base64_image(url: str) -> str:
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        resp = httpx.get(url, headers=headers, follow_redirects=True, timeout=10)
        if resp.status_code == 200:
            return f"data:image/jpeg;base64,{base64.b64encode(resp.content).decode('utf-8')}"
    except Exception:
        pass
    return ""


# ============ HTML TO IMAGE ENGINE (CHROME / EDGE & HCTI FALLBACK) ============

def find_headless_browser() -> Optional[str]:
    """Tìm đường dẫn trình duyệt Chrome hoặc Edge để render HTML sang ảnh cục bộ"""
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    import shutil
    for prog in ["chrome", "msedge", "google-chrome", "chromium"]:
        p = shutil.which(prog)
        if p:
            return p
    return None

def render_html_to_image(html_content: str, save_path: Path, width: int = 950, height: int = 1250, google_fonts: str = None) -> Optional[bytes]:
    """
    Render HTML sang ảnh PNG chất lượng cao:
    1. Ưu tiên: Dùng Chrome / Edge headless trực tiếp trên máy (siêu nét, nhanh, không giới hạn, không tốn credit API).
    2. Fallback: HCTI API nếu không có trình duyệt.
    """
    browser = find_headless_browser()
    if browser:
        tmp_html = None
        tmp_png = None
        try:
            fonts_link = ""
            if google_fonts:
                font_families = [f"family={f.strip().replace(' ', '+')}" for f in google_fonts.split(",") if f.strip()]
                fonts_link = f"<link href='https://fonts.googleapis.com/css2?{'&'.join(font_families)}&display=swap' rel='stylesheet'>"
            
            full_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    {fonts_link}
    <style>
        * {{ box-sizing: border-box; }}
        html, body {{ margin: 0; padding: 0; background: #111; width: 100%; height: 100%; overflow: hidden; }}
    </style>
</head>
<body>
    {html_content}
</body>
</html>"""

            with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8") as f:
                f.write(full_html)
                tmp_html = f.name
                
            tmp_png = Path(tempfile.gettempdir()) / f"doc_{random.randint(100000, 999999)}.png"
            
            cmd = [
                browser,
                "--headless=new",
                "--disable-gpu",
                "--hide-scrollbars",
                f"--window-size={width},{height}",
                f"--screenshot={tmp_png}",
                tmp_html
            ]
            
            subprocess.run(cmd, capture_output=True, timeout=25)
            
            if tmp_png.exists() and tmp_png.stat().st_size > 0:
                data = tmp_png.read_bytes()
                save_path.write_bytes(data)
                print(f"     [{get_current_time()}] 💾 Đã lưu: {save_path.name}")
                return data
        except Exception as e:
            print(f"     ⚠️ Local render lỗi: {e}, thử HCTI API...")
        finally:
            if tmp_html and os.path.exists(tmp_html):
                try: os.remove(tmp_html)
                except Exception: pass
            if tmp_png and tmp_png.exists():
                try: os.remove(tmp_png)
                except Exception: pass

    # Fallback: HCTI API
    try:
        data_payload = {"html": html_content, "css": "body { margin: 0; }"}
        if google_fonts:
            data_payload["google_fonts"] = google_fonts
            
        response = httpx.post("https://hcti.io/v1/image", auth=(HCTI_USER_ID, HCTI_API_KEY), data=data_payload, timeout=30)
        if response.status_code == 200:
            img_url = response.json().get("url")
            img_resp = httpx.get(img_url, timeout=30)
            if img_resp.status_code == 200:
                save_path.write_bytes(img_resp.content)
                print(f"     [{get_current_time()}] 💾 Đã lưu (HCTI): {save_path.name}")
                return img_resp.content
        else:
            print(f"     ❌ Lỗi HCTI API: HTTP {response.status_code} ({response.text[:80]})")
    except Exception as e:
        print(f"     ❌ Lỗi HCTI: {e}")
        
    return None


# ============ API DOCUMENT GENERATORS ============

def generate_scanned_id_card(first, last, school_data, dob, save_path, photo_b64, logo_b64, finance_data, netid) -> Optional[bytes]:
    print(f"     [{get_current_time()}] ⏳ Đang tạo Thẻ sinh viên...")
    school = school_data["name"]
    address = school_data["address"]
    phone = school_data["phone"]
    primary = school_data["primary_color"]
    secondary = school_data["secondary_color"]
    student_id = finance_data["student_id"]
    
    issue_date = "08/15/2026"
    valid_thru = "06/2030"
    barcode_url = f"https://barcode.tec-it.com/barcode.ashx?data={student_id}&code=Code128&dpi=96&hideh=1&bcolor=%23FFFFFF&textcolor=%23000000"
    
    global_noise = """
        <div style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; opacity: 0.25; pointer-events: none; background-image: url('https://www.transparenttextures.com/patterns/stardust.png'); mix-blend-mode: overlay; z-index: 999;"></div>
    """

    html_content = f"""
    <div style="width: 900px; height: 1100px; background-color: #3e2723; background-image: url('https://www.transparenttextures.com/patterns/wood-pattern.png'); padding: 50px; box-sizing: border-box; position: relative; font-family: Arial, sans-serif; display: flex; flex-direction: column; align-items: center; justify-content: center; overflow: hidden;">
        {global_noise}
        <div style="width: 700px; height: 440px; background: #ffffff; border-radius: 12px; margin-bottom: 50px; position: relative; box-shadow: 15px 25px 35px rgba(0,0,0,0.6); transform: perspective(1000px) rotateX(15deg) rotateY(-10deg) rotateZ(2deg);">
            <div style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: linear-gradient(135deg, rgba(255,255,255,0.6) 0%, rgba(255,255,255,0) 40%); border-radius: 12px; pointer-events: none; z-index: 10;"></div>
            <div style="background: {primary}; height: 90px; display: flex; align-items: center; justify-content: space-between; padding: 0 30px; border-top-left-radius: 12px; border-top-right-radius: 12px;">
                <div style="display: flex; align-items: center; gap: 15px;">
                    <div style="width: 60px; height: 60px; background: white; border-radius: 50%; padding: 4px; display: flex; justify-content: center; align-items: center;">
                        <img src="{logo_b64}" style="max-width: 100%; max-height: 100%; object-fit: contain;">
                    </div>
                    <div>
                        <h1 style="margin: 0; font-size: 22px; color: white; text-transform: uppercase;">{school}</h1>
                        <p style="margin: 3px 0 0 0; font-size: 12px; color: {secondary};">STUDENT IDENTIFICATION CARD</p>
                    </div>
                </div>
                <div style="color: white; text-align: right;">
                    <div style="font-size: 16px; font-weight: bold;">{netid}</div>
                </div>
            </div>
            <div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); opacity: 0.08; z-index: 0; mix-blend-mode: multiply;">
                <img src="{logo_b64}" style="width: 350px;">
            </div>
            <div style="padding: 25px 30px; display: flex; gap: 30px; position: relative; z-index: 1;">
                <div style="text-align: center;">
                    <img src="{photo_b64}" style="width: 150px; height: 190px; object-fit: cover; border-radius: 6px; border: 2px solid {primary};">
                    <div style="width: 45px; height: 35px; background: linear-gradient(135deg, #d4af37, #f3e5ab); border-radius: 4px; border: 1px solid #999; margin: 15px auto 0 auto; position: relative;">
                        <div style="position: absolute; top: 10px; left: 5px; right: 5px; height: 1px; background: #999;"></div>
                        <div style="position: absolute; top: 20px; left: 5px; right: 5px; height: 1px; background: #999;"></div>
                        <div style="position: absolute; top: 5px; bottom: 5px; left: 15px; width: 1px; background: #999;"></div>
                        <div style="position: absolute; top: 5px; bottom: 5px; right: 15px; width: 1px; background: #999;"></div>
                    </div>
                </div>
                <div style="flex-grow: 1;">
                    <div style="margin-bottom: 15px;">
                        <div style="font-size: 10px; color: #666; font-weight: bold;">NAME</div>
                        <div style="font-size: 24px; font-weight: bold; color: #000; text-transform: uppercase;">{first} {last}</div>
                    </div>
                    <div style="display: flex; gap: 40px; margin-bottom: 15px;">
                        <div>
                            <div style="font-size: 10px; color: #666; font-weight: bold;">DATE OF BIRTH</div>
                            <div style="font-size: 16px; font-weight: bold;">{dob}</div>
                        </div>
                        <div>
                            <div style="font-size: 10px; color: #666; font-weight: bold;">STUDENT ID</div>
                            <div style="font-size: 16px; font-weight: bold; color: #d32f2f;">{student_id}</div>
                        </div>
                    </div>
                    <div style="display: flex; gap: 40px;">
                        <div>
                            <div style="font-size: 10px; color: #666; font-weight: bold;">ISSUE DATE</div>
                            <div style="font-size: 16px; font-weight: bold;">{issue_date}</div>
                        </div>
                        <div>
                            <div style="font-size: 10px; color: #666; font-weight: bold;">VALID THRU</div>
                            <div style="font-size: 16px; font-weight: bold;">{valid_thru}</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <div style="width: 700px; height: 440px; background: #ffffff; border-radius: 12px; position: relative; box-shadow: 15px 25px 35px rgba(0,0,0,0.6); transform: perspective(1000px) rotateX(15deg) rotateY(-10deg) rotateZ(2deg);">
            <div style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: linear-gradient(135deg, rgba(255,255,255,0.6) 0%, rgba(255,255,255,0) 40%); border-radius: 12px; pointer-events: none; z-index: 10;"></div>
            <div style="background: #222; height: 50px; width: 100%; position: absolute; top: 40px;"></div>
            <div style="background: #f0f0f0; height: 60px; display: flex; align-items: center; justify-content: center; border-bottom: 2px solid {primary}; border-top-left-radius: 12px; border-top-right-radius: 12px;">
                <h2 style="margin: 0; font-size: 18px; color: {primary}; letter-spacing: 1px;">TERMS AND CONDITIONS</h2>
            </div>
            <div style="padding: 40px; color: #444; font-size: 13px; line-height: 1.6; margin-top: 50px;">
                <p><strong>1. Property of the University:</strong> This card is the property of {school} and is non-transferable. It must be presented upon request to any University official.</p>
                <p><strong>2. Loss or Theft:</strong> If found, please drop in any U.S. mailbox or return to the address below. A replacement fee will be charged for lost cards.</p>
                <p><strong>3. Misuse:</strong> Altering or misusing this card is a violation of University policy and may result in disciplinary action.</p>
            </div>
            <div style="position: absolute; bottom: 30px; left: 40px; right: 40px; display: flex; justify-content: space-between; align-items: flex-end;">
                <div><img src="{barcode_url}" style="height: 50px; opacity: 0.8;"></div>
                <div style="text-align: right; font-size: 11px; color: #666;">
                    <p style="margin: 0; font-weight: bold;">{school} - Office of the Registrar</p>
                    <p style="margin: 0;">{address}</p>
                    <p style="margin: 0;">{phone}</p>
                </div>
            </div>
        </div>
    </div>
    """

    return render_html_to_image(html_content, save_path, width=950, height=1150, google_fonts="Arial")


def generate_hcti_doc(first, last, school_data, dob, save_path, doc_type, photo_b64, logo_b64, finance_data) -> Optional[bytes]:
    print(f"     [{get_current_time()}] ⏳ Đang tạo {doc_type}...")
    school = school_data["name"]
    address = school_data["address"]
    phone = school_data["phone"]
    financial_dept = school_data["financial_dept"]
    courses = school_data["courses"]
    primary = school_data["primary_color"]
    style = school_data["style"]
    registrar_name = school_data["registrar"]
    
    tuition = school_data["tuition"] + random.uniform(100.50, 999.50)
    housing = school_data["housing"] + random.uniform(50.25, 499.75)
    food = school_data["food"] + random.uniform(10.10, 199.90)
    health_fee = random.uniform(150.00, 350.00)
    tech_fee = random.uniform(100.00, 250.00)
    library_fee = random.uniform(80.00, 180.00)
    rec_fee = random.uniform(50.00, 120.00)
    total = tuition + housing + food + health_fee + tech_fee + library_fee + rec_fee
    
    student_id = finance_data["student_id"]
    
    issue_date = (datetime.now() - timedelta(days=random.randint(5, 25))).strftime('%B %d, %Y')
    receipt_date = (datetime.now() - timedelta(days=random.randint(2, 4))).strftime('%B %d, %Y')
    
    rotation = random.randint(-18, -8)
    opacity = round(random.uniform(0.6, 0.85), 2)
    stamp_color = random.choice(["#b71c1c", "#d32f2f", "#c62828"])
    
    def generate_grunge_stamp(text_top, text_bottom):
        return f"""
        <div style="position: absolute; bottom: 80px; right: 80px; width: 160px; height: 160px; transform: rotate({rotation}deg); opacity: {opacity}; mix-blend-mode: multiply; z-index: 10;">
            <div style="position: absolute; inset: 0; border: 4px solid {stamp_color}; border-radius: 50%; filter: blur(0.5px) contrast(1.5); mask-image: url('https://www.transparenttextures.com/patterns/dust.png'); mask-size: cover;"></div>
            <div style="position: absolute; inset: 15px; border: 2px solid {stamp_color}; border-radius: 50%; filter: blur(0.3px); mask-image: url('https://www.transparenttextures.com/patterns/dust.png'); mask-size: cover;"></div>
            <div style="position: absolute; top: 20px; width: 100%; text-align: center; font-family: 'Arial Black', sans-serif; font-size: 11px; color: {stamp_color}; transform: scaleY(1.2); filter: blur(0.4px);">{text_top}</div>
            <div style="position: absolute; bottom: 20px; width: 100%; text-align: center; font-family: 'Arial Black', sans-serif; font-size: 13px; color: {stamp_color}; transform: scaleY(1.2); filter: blur(0.4px);">{text_bottom}</div>
            <div style="position: absolute; inset: 0; display: flex; justify-content: center; align-items: center; font-size: 28px; color: {stamp_color}; filter: blur(0.3px);">★</div>
        </div>
        """

    watermark = f"""
        <div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); opacity: 0.05; z-index: 0; pointer-events: none; mix-blend-mode: multiply;">
            <img src="{logo_b64}" style="width: 500px;">
        </div>
    """
    
    scan_noise = """
        <div style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; opacity: 0.15; pointer-events: none; background-image: url('https://www.transparenttextures.com/patterns/stardust.png'); mix-blend-mode: overlay; z-index: 999;"></div>
        <div style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: radial-gradient(circle at 30% 30%, rgba(255,255,255,0.3) 0%, rgba(0,0,0,0.1) 100%); pointer-events: none; z-index: 998;"></div>
    """
    
    html_content = ""
    
    if style == "Ivy":
        font_family = "'Times New Roman', serif"
        
        if doc_type == "class_schedule":
            rows = ""
            for code, title, days, time_str, room in courses:
                rows += f"<tr><td style='padding: 12px; border-bottom: 1px solid #ccc;'>{code}</td><td style='padding: 12px; border-bottom: 1px solid #ccc;'>{title}</td><td style='padding: 12px; border-bottom: 1px solid #ccc;'>{days}</td><td style='padding: 12px; border-bottom: 1px solid #ccc;'>{time_str}</td><td style='padding: 12px; border-bottom: 1px solid #ccc;'>{room}</td></tr>"
            
            html_content = f"""
            <div style="width: 900px; height: 1200px; background: #2d2d2d; padding: 50px; box-sizing: border-box; display: flex; justify-content: center; align-items: center;">
                <div style="width: 850px; padding: 60px; background: #fcfcfc; font-family: {font_family}; color: #000; min-height: 1100px; position: relative; box-sizing: border-box; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.7); transform: perspective(1200px) rotateX(5deg) rotateY(-5deg);">
                    {watermark}{scan_noise}
                    <div style="text-align: center; border-bottom: 2px solid {primary}; padding-bottom: 20px; margin-bottom: 40px; position: relative; z-index: 1;">
                        <img src="{logo_b64}" style="height: 90px; margin-bottom: 15px;">
                        <h1 style="margin: 0; font-size: 32px; color: {primary}; font-weight: normal; letter-spacing: 2px;">{school}</h1>
                        <p style="margin: 10px 0 0 0; font-size: 18px; font-style: italic;">Office of the Registrar</p>
                    </div>
                    <div style="display: flex; justify-content: space-between; margin-bottom: 40px; font-size: 18px; position: relative; z-index: 1;">
                        <div><strong>Student:</strong> {first} {last}<br><strong>DOB:</strong> {dob}</div>
                        <div style="text-align: right;"><strong>ID:</strong> {student_id}<br><strong>Term:</strong> Fall 2026</div>
                    </div>
                    <h2 style="text-align: center; font-size: 22px; text-transform: uppercase; letter-spacing: 3px; text-decoration: underline; margin-bottom: 30px;">Official Class Schedule</h2>
                    <table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 16px; position: relative; z-index: 1;">
                        <thead>
                            <tr style="border-bottom: 2px solid #000;">
                                <th style="padding: 12px;">Course</th><th style="padding: 12px;">Title</th><th style="padding: 12px;">Days</th><th style="padding: 12px;">Time</th><th style="padding: 12px;">Room</th>
                            </tr>
                        </thead>
                        <tbody>{rows}</tbody>
                    </table>
                    <div style="margin-top: 80px; display: flex; justify-content: space-between; align-items: flex-end; position: relative; z-index: 1;">
                        <div style="text-align: center;">
                            <p style="font-family: 'Brush Script MT', cursive; font-size: 36px; margin: 0;">{registrar_name}</p>
                            <p style="border-top: 1px solid #000; padding-top: 5px; width: 250px; margin-top: 5px; font-size: 16px;">University Registrar</p>
                        </div>
                        <p style="position: absolute; bottom: 0; right: 0; font-size: 14px;">Issued: {issue_date}</p>
                    </div>
                    {generate_grunge_stamp(school.upper(), "REGISTRAR")}
                </div>
            </div>
            """
        elif doc_type == "tuition_receipt":
            html_content = f"""
            <div style="width: 900px; height: 1200px; background: #2d2d2d; padding: 50px; box-sizing: border-box; display: flex; justify-content: center; align-items: center;">
                <div style="width: 850px; padding: 60px; background: #fcfcfc; font-family: {font_family}; color: #000; min-height: 1100px; position: relative; box-sizing: border-box; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.7); transform: perspective(1200px) rotateX(5deg) rotateY(5deg);">
                    {watermark}{scan_noise}
                    <div style="text-align: center; border-bottom: 2px solid {stamp_color}; padding-bottom: 20px; margin-bottom: 40px; position: relative; z-index: 1;">
                        <img src="{logo_b64}" style="height: 90px; margin-bottom: 15px;">
                        <h1 style="margin: 0; font-size: 32px; color: {primary}; font-weight: normal; letter-spacing: 2px;">{school}</h1>
                        <p style="margin: 10px 0 0 0; font-size: 18px; font-style: italic;">{financial_dept}</p>
                    </div>
                    <div style="display: flex; justify-content: space-between; margin-bottom: 40px; font-size: 18px; position: relative; z-index: 1;">
                        <div><strong>Student:</strong> {first} {last}<br><strong>ID:</strong> {student_id}</div>
                        <div style="text-align: right;"><strong>Date:</strong> {receipt_date}<br><strong>Status:</strong> <span style="color: green; font-weight: bold;">PAID</span></div>
                    </div>
                    <h2 style="text-align: center; font-size: 22px; text-transform: uppercase; letter-spacing: 3px; margin-bottom: 30px;">Statement of Account</h2>
                    <table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 16px; position: relative; z-index: 1;">
                        <thead>
                            <tr style="border-bottom: 2px solid #000;"><th style="padding: 15px;">Item</th><th style="padding: 15px; text-align: right;">Amount</th></tr>
                        </thead>
                        <tbody>
                            <tr><td style="padding: 15px; border-bottom: 1px dotted #999;">Tuition and Fees (Fall 2026)</td><td style="padding: 15px; text-align: right; border-bottom: 1px dotted #999;">${tuition:,.2f}</td></tr>
                            <tr><td style="padding: 15px; border-bottom: 1px dotted #999;">Health Insurance</td><td style="padding: 15px; text-align: right; border-bottom: 1px dotted #999;">${health_fee:,.2f}</td></tr>
                            <tr><td style="padding: 15px; border-bottom: 1px dotted #999;">Technology Fee</td><td style="padding: 15px; text-align: right; border-bottom: 1px dotted #999;">${tech_fee:,.2f}</td></tr>
                            <tr><td style="padding: 15px; border-bottom: 1px dotted #999;">Library Fee</td><td style="padding: 15px; text-align: right; border-bottom: 1px dotted #999;">${library_fee:,.2f}</td></tr>
                            <tr><td style="padding: 15px; border-bottom: 1px dotted #999;">Recreation Center</td><td style="padding: 15px; text-align: right; border-bottom: 1px dotted #999;">${rec_fee:,.2f}</td></tr>
                            <tr><td style="padding: 15px; border-bottom: 1px dotted #999;">Room and Board</td><td style="padding: 15px; text-align: right; border-bottom: 1px dotted #999;">${housing+food:,.2f}</td></tr>
                            <tr style="font-weight: bold; border-top: 2px solid #000;"><td style="padding: 15px; text-align: right; font-size: 18px;">Total:</td><td style="padding: 15px; text-align: right; font-size: 18px;">${total:,.2f}</td></tr>
                        </tbody>
                    </table>
                    {generate_grunge_stamp(school.upper(), "BURSAR")}
                    <div style="position: absolute; bottom: 30px; width: 100%; text-align: center; font-size: 14px; color: #555;">
                        {address} | {phone}
                    </div>
                </div>
            </div>
            """
            
    elif style == "State":
        font_family = "Arial, sans-serif"
        
        if doc_type == "class_schedule":
            rows = ""
            for code, title, days, time_str, room in courses:
                rows += f"<tr><td style='padding: 15px; border-bottom: 1px solid #eee; font-weight: bold;'>{code}</td><td style='padding: 15px; border-bottom: 1px solid #eee;'>{title}</td><td style='padding: 15px; border-bottom: 1px solid #eee;'>{days}</td><td style='padding: 15px; border-bottom: 1px solid #eee;'>{time_str}</td><td style='padding: 15px; border-bottom: 1px solid #eee;'>{room}</td></tr>"
            
            html_content = f"""
            <div style="width: 900px; height: 1200px; background: #2d2d2d; padding: 50px; box-sizing: border-box; display: flex; justify-content: center; align-items: center;">
                <div style="width: 850px; padding: 50px; background: #ffffff; font-family: {font_family}; color: #333; min-height: 1100px; position: relative; box-sizing: border-box; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.7); transform: perspective(1200px) rotateX(5deg) rotateY(-5deg);">
                    {watermark}{scan_noise}
                    <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 4px solid {primary}; padding-bottom: 20px; margin-bottom: 40px; position: relative; z-index: 1;">
                        <div style="display: flex; align-items: center; gap: 20px;">
                            <img src="{logo_b64}" style="height: 70px;">
                            <div>
                                <h1 style="margin: 0; font-size: 26px; color: {primary}; font-weight: 800; text-transform: uppercase;">{school}</h1>
                                <p style="margin: 5px 0 0 0; font-size: 16px; font-weight: bold; color: #666;">OFFICE OF THE REGISTRAR</p>
                            </div>
                        </div>
                        <div style="text-align: right;">
                            <h2 style="margin: 0; font-size: 22px; color: {primary};">CLASS SCHEDULE</h2>
                            <p style="margin: 5px 0 0 0; font-size: 14px;">Date Issued: {issue_date}</p>
                        </div>
                    </div>
                    <div style="display: flex; justify-content: space-between; margin-bottom: 30px; font-size: 16px; position: relative; z-index: 1; background: #f8f9fa; padding: 15px; border-left: 5px solid {primary};">
                        <div><strong>Student Name:</strong> {first} {last}<br><strong>DOB:</strong> {dob}</div>
                        <div style="text-align: right;"><strong>Student ID:</strong> <span style="color: #d32f2f; font-weight: bold;">{student_id}</span><br><strong>Academic Term:</strong> Fall 2026</div>
                    </div>
                    <table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 15px; position: relative; z-index: 1;">
                        <thead>
                            <tr style="background: {primary}; color: white;">
                                <th style="padding: 15px;">Course Code</th><th style="padding: 15px;">Course Title</th><th style="padding: 15px;">Days</th><th style="padding: 15px;">Time</th><th style="padding: 15px;">Room</th>
                            </tr>
                        </thead>
                        <tbody>{rows}</tbody>
                    </table>
                    <div style="margin-top: 80px; display: flex; justify-content: space-between; align-items: flex-end; position: relative; z-index: 1;">
                        <div style="text-align: center;">
                            <p style="font-family: 'Great Vibes', cursive; font-size: 38px; margin: 0; color: #000;">{registrar_name}</p>
                            <p style="border-top: 2px solid #000; padding-top: 5px; width: 250px; margin-top: 5px; font-size: 16px; font-weight: bold;">University Registrar</p>
                        </div>
                    </div>
                    {generate_grunge_stamp(school.upper(), "REGISTRAR")}
                </div>
            </div>
            """
        elif doc_type == "tuition_receipt":
            html_content = f"""
            <div style="width: 900px; height: 1200px; background: #2d2d2d; padding: 50px; box-sizing: border-box; display: flex; justify-content: center; align-items: center;">
                <div style="width: 850px; padding: 50px; background: #ffffff; font-family: {font_family}; color: #333; min-height: 1100px; position: relative; box-sizing: border-box; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.7); transform: perspective(1200px) rotateX(5deg) rotateY(5deg);">
                    {watermark}{scan_noise}
                    <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 4px solid {stamp_color}; padding-bottom: 20px; margin-bottom: 40px; position: relative; z-index: 1;">
                        <div style="display: flex; align-items: center; gap: 20px;">
                            <img src="{logo_b64}" style="height: 70px;">
                            <div>
                                <h1 style="margin: 0; font-size: 26px; color: {primary}; font-weight: 800; text-transform: uppercase;">{school}</h1>
                                <p style="margin: 5px 0 0 0; font-size: 16px; font-weight: bold; color: #666;">{financial_dept.upper()}</p>
                            </div>
                        </div>
                        <div style="text-align: right;">
                            <h2 style="margin: 0; font-size: 22px; color: {stamp_color};">TUITION RECEIPT</h2>
                            <p style="margin: 5px 0 0 0; font-size: 14px;">Date Issued: {receipt_date}</p>
                        </div>
                    </div>
                    <div style="display: flex; justify-content: space-between; margin-bottom: 40px; font-size: 16px; position: relative; z-index: 1; background: #f8f9fa; padding: 15px; border-left: 5px solid {stamp_color};">
                        <div><strong>Student Name:</strong> {first} {last}<br><strong>Student ID:</strong> {student_id}</div>
                        <div style="text-align: right;"><strong>Transaction ID:</strong> TXN-{random.randint(100000000, 999999999)}<br><strong>Status:</strong> <span style="color: green; font-weight: bold;">PAID IN FULL</span></div>
                    </div>
                    <table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 15px; position: relative; z-index: 1;">
                        <thead>
                            <tr style="background: {stamp_color}; color: white;"><th style="padding: 15px;">Description</th><th style="padding: 15px; text-align: right;">Amount</th></tr>
                        </thead>
                        <tbody>
                            <tr><td style="padding: 15px; border-bottom: 1px solid #eee;">Tuition - Full-Time Undergraduate</td><td style="padding: 15px; text-align: right; border-bottom: 1px solid #eee;">${tuition:,.2f}</td></tr>
                            <tr><td style="padding: 15px; border-bottom: 1px solid #eee;">Student Health Insurance</td><td style="padding: 15px; text-align: right; border-bottom: 1px solid #eee;">${health_fee:,.2f}</td></tr>
                            <tr><td style="padding: 15px; border-bottom: 1px solid #eee;">Technology & Lab Fee</td><td style="padding: 15px; text-align: right; border-bottom: 1px solid #eee;">${tech_fee:,.2f}</td></tr>
                            <tr><td style="padding: 15px; border-bottom: 1px solid #eee;">Library & Resource Fee</td><td style="padding: 15px; text-align: right; border-bottom: 1px solid #eee;">${library_fee:,.2f}</td></tr>
                            <tr><td style="padding: 15px; border-bottom: 1px solid #eee;">Recreation Center Fee</td><td style="padding: 15px; text-align: right; border-bottom: 1px solid #eee;">${rec_fee:,.2f}</td></tr>
                            <tr><td style="padding: 15px; border-bottom: 1px solid #eee;">Housing & Meal Plan</td><td style="padding: 15px; text-align: right; border-bottom: 1px solid #eee;">${housing+food:,.2f}</td></tr>
                            <tr style="font-weight: bold; background: #f8f9fa; border-top: 3px solid #333;"><td style="padding: 15px; text-align: right; font-size: 18px;">Total Amount Paid:</td><td style="padding: 15px; text-align: right; font-size: 18px;">${total:,.2f}</td></tr>
                        </tbody>
                    </table>
                    {generate_grunge_stamp(school.upper(), "BURSAR")}
                    <div style="position: absolute; bottom: 30px; width: 100%; text-align: center; font-size: 14px; color: #777;">
                        {address} | {phone}
                    </div>
                </div>
            </div>
            """

    return render_html_to_image(html_content, save_path, width=950, height=1250, google_fonts="Times New Roman, Arial, Great Vibes")


# ============ VERIFIER ============
class GeminiVerifier:
    def __init__(self, url: str, sitekey: str, proxy: str = None):
        self.url = url
        self.sitekey = sitekey
        self.vid = self._parse_id(url)
        self.fingerprint = generate_fingerprint()

        if HAS_ANTI_DETECT:
            self.client, self.lib_name = create_session(proxy)
            print(f"[INFO] Using {self.lib_name} for HTTP requests")
        else:
            proxy_url = None
            if proxy:
                if not proxy.startswith("http"):
                    proxy = f"http://{proxy}"
                proxy_url = proxy
            self.client = httpx.Client(timeout=30, proxy=proxy_url)
            self.lib_name = "httpx"
        self.org = None

    def __del__(self):
        if hasattr(self, "client"):
            try: self.client.close()
            except: pass

    @staticmethod
    def _parse_id(url: str) -> Optional[str]:
        match = re.search(r"verificationId=([a-f0-9]+)", url, re.IGNORECASE)
        return match.group(1) if match else None

    def _request(self, method: str, endpoint: str, body: Dict = None) -> Tuple[Dict, int]:
        random_delay()
        try:
            headers = get_headers(for_sheerid=True) if HAS_ANTI_DETECT else {"Content-Type": "application/json"}
            resp = self.client.request(method, f"{SHEERID_API_URL}{endpoint}", json=body, headers=headers)
            try: parsed = resp.json() if resp.text else {}
            except: parsed = {"_text": resp.text}
            return parsed, resp.status_code
        except Exception as e:
            raise Exception(f"Request failed: {e}")

    def _upload_s3(self, url: str, data: bytes) -> bool:
        attempts = [
            lambda: self.client.put(url, content=data, headers={"Content-Type": "image/png"}, timeout=60),
            lambda: self.client.put(url, data=data, headers={"Content-Type": "image/png"}, timeout=60),
            lambda: self.client.request("PUT", url, data=data, headers={"Content-Type": "image/png"}, timeout=60)
        ]
        last_exc = None
        for fn in attempts:
            try:
                resp = fn()
                if hasattr(resp, "status_code"):
                    if 200 <= resp.status_code < 300: return True
                    print(f"     ❗ S3 upload failed: HTTP {resp.status_code}")
                    return False
                else: return bool(resp)
            except Exception as e:
                last_exc = e
                continue
        print(f"     ❗ S3 upload failed. Last error: {last_exc}")
        return False

    @staticmethod
    def _save_log(out_dir: Path, log: list):
        if out_dir and log:
            try: (out_dir / "request_log.json").write_text(json.dumps(log, indent=2, ensure_ascii=False, default=str))
            except: pass

    @staticmethod
    def _write_info(out_dir: Path, info: Dict):
        if out_dir:
            try: (out_dir / "info.json").write_text(json.dumps(info, indent=2, ensure_ascii=False))
            except: pass

    def check_link(self) -> Dict:
        if not self.vid: return {"valid": False, "error": "Invalid URL"}
        data, status = self._request("GET", f"/verification/{self.vid}")
        if status != 200: return {"valid": False, "error": f"HTTP {status}"}
        step = data.get("currentStep", "")
        valid_steps = ["collectStudentPersonalInfo", "docUpload", "sso"]
        if step in valid_steps: return {"valid": True, "step": step}
        elif step == "success": return {"valid": False, "error": "Already verified"}
        elif step == "pending": return {"valid": False, "error": "Already pending review"}
        return {"valid": False, "error": f"Invalid step: {step}"}

    def solve_captcha(self) -> str:
        print(f"   [{get_current_time()}] 🔄 Đang giải CAPTCHA (Turnstile) qua 2Captcha...")
        try:
            solver = TwoCaptcha(CAPTCHA_API_KEY)
            result = solver.turnstile(sitekey=self.sitekey, url=self.url)
            print(f"   [{get_current_time()}] ✅ Đã giải xong CAPTCHA!")
            return result['code']
        except Exception as e:
            print(f"   ❌ Lỗi giải CAPTCHA: {e}")
            raise Exception(f"Captcha solving failed: {e}")

    def verify(self) -> Dict:
        if not self.vid: return {"success": False, "error": "Invalid verification URL"}

        out_dir: Optional[Path] = None
        request_log: list = []
        info: Dict = {}

        try:
            check_data, check_status = self._request("GET", f"/verification/{self.vid}")
            current_step = check_data.get("currentStep", "") if check_status == 200 else ""
            request_log.append({"step": "check", "status": check_status, "currentStep": current_step})

            first, last, photo_url, netid = generate_name_and_photo()
            self.org = select_university()
            email = generate_email(first, last, self.org["domain"], netid)
            dob = generate_birth_date()
            logo_url = f"https://logo.pubrio.com/{self.org['domain']}"
            
            finance_data = {"student_id": random.randint(10000000, 99999999)}

            out_dir = create_output_dir(email)
            print(f"\n   [{get_current_time()}] 📁 Output: {out_dir}")
            print(f"   🎓 Student: {first} {last} ({netid})")
            print(f"   📧 Email: {email}")
            print(f"   🏫 School: {self.org['name']} (Style: {self.org['style']})")
            print(f"   🎂 DOB: {dob}")
            
            print(f"   [{get_current_time()}] ▶ Đang tải ảnh (Logo & Photo) để nhúng Base64...")
            logo_b64 = get_base64_image(logo_url)
            photo_b64 = get_base64_image(photo_url)
            
            if not logo_b64 or not photo_b64:
                print("   ❌ Lỗi: Không thể tải ảnh từ mạng. Vui lòng kiểm tra kết nối!")
                stats.record(self.org["name"], False)
                return {"success": False, "error": "Image download failed", "outputDir": str(out_dir)}

            print(f"   [{get_current_time()}] ▶ Đang tạo 3 loại giấy tờ (Phân chia Style)...")
            docs_data = {}
            
            path_id = out_dir / "scanned_id_card.png"
            data_id = generate_scanned_id_card(first, last, self.org, dob, path_id, photo_b64, logo_b64, finance_data, netid)
            if data_id: docs_data["scanned_id_card.png"] = data_id
            
            path_sch = out_dir / "class_schedule.png"
            data_sch = generate_hcti_doc(first, last, self.org, dob, path_sch, "class_schedule", photo_b64, logo_b64, finance_data)
            if data_sch: docs_data["class_schedule.png"] = data_sch

            path_rcp = out_dir / "tuition_receipt.png"
            data_rcp = generate_hcti_doc(first, last, self.org, dob, path_rcp, "tuition_receipt", photo_b64, logo_b64, finance_data)
            if data_rcp: docs_data["tuition_receipt.png"] = data_rcp

            if not docs_data:
                stats.record(self.org["name"], False)
                return {"success": False, "error": "Không thể tạo được tài liệu nào", "outputDir": str(out_dir)}

            info = {
                "email": email, "firstName": first, "lastName": last, "birthDate": dob,
                "school": self.org["name"], "schoolId": self.org["id"], "schoolDomain": self.org["domain"],
                "photoUrl": photo_url, "netid": netid, "financeData": finance_data,
                "docFiles": list(docs_data.keys()), "verificationId": self.vid,
                "fingerprint": self.fingerprint, "createdAt": datetime.now().isoformat(), "status": "in_progress",
            }
            self._write_info(out_dir, info)
            self._save_log(out_dir, request_log)

            # ==========================================
            # CHỌN CHẾ ĐỘ NỘP TÀI LIỆU (TỰ ĐỘNG HAY THỦ CÔNG)
            # ==========================================
            print("\n" + "═"*58)
            print(f" 📄 [{get_current_time()}] ĐÃ CHUẨN BỊ XONG 3 LOẠI TÀI LIỆU!")
            print(f" 📁 Thư mục lưu ảnh: {out_dir}")
            print(f" 🎓 Sinh viên: {first} {last} | Ngày sinh: {dob}")
            print(f" 🏫 Trường: {self.org['name']} | Email: {email}")
            print("═"*58)

            # Tự động mở thư mục ảnh cho người dùng tiện xem
            try:
                if sys.platform == 'win32':
                    os.startfile(out_dir)
                elif sys.platform == 'darwin':
                    os.system(f'open "{out_dir}"')
                else:
                    os.system(f'xdg-open "{out_dir}"')
            except Exception:
                pass

            print("\n 👉 CHỌN PHƯƠNG THỨC UPLOAD:")
            print("    [1] Up tự động     - Tool tự nộp thông tin & tự upload ảnh lên SheerID (Mặc định)")
            print("    [2] Tự up thủ công - Bạn tự upload tài liệu trên trình duyệt web")
            
            upload_mode = input("\n   > Nhập lựa chọn (1 hoặc 2, nhấn Enter để chọn 1 - Tự động): ").strip()

            if upload_mode == "2":
                print("\n" + "─"*58)
                print(" 👤 CHẾ ĐỘ: TỰ UPLOAD THỦ CÔNG")
                print("─"*58)
                print(" 👉 Bạn muốn:")
                print("    [a] Tool tự điền thông tin & giải Captcha, bạn chỉ cần kéo thả up ảnh trên web (Khuyên dùng)")
                print("    [b] Bạn tự điền toàn bộ từ thông tin sinh viên đến up ảnh trên web")
                sub_choice = input("   > Chọn (a hoặc b, nhấn Enter để chọn a): ").strip().lower()
                if sub_choice != "b":
                    sub_choice = "a"

                if sub_choice == "a":
                    if current_step == "collectStudentPersonalInfo":
                        print(f"\n   [{get_current_time()}] ⏳ Tool đang gửi trước thông tin sinh viên & giải Captcha...")
                        body = {
                            "firstName": first, "lastName": last, "birthDate": dob, "email": email, "phoneNumber": "",
                            "organization": {"id": self.org["id"], "idExtended": self.org["idExtended"], "name": self.org["name"]},
                            "deviceFingerprintHash": self.fingerprint, "locale": "en-US",
                            "metadata": {
                                "marketConsentValue": False, "verificationId": self.vid,
                                "refererUrl": f"https://services.sheerid.com/verify/{PROGRAM_ID}/?verificationId={self.vid}",
                                "flags": '{"collect-info-step-email-first":"default","doc-upload-considerations":"default","doc-upload-may24":"default","doc-upload-redesign-use-legacy-message-keys":false,"docUpload-assertion-checklist":"default","font-size":"default","include-cvec-field-france-student":"not-labeled-optional"}',
                                "submissionOptIn": "By submitting the personal information above, I acknowledge that my personal information is being collected under the privacy policy of the business from which I am seeking a discount",
                            },
                        }

                        captcha_token = self.solve_captcha()
                        body["captchaToken"] = captcha_token

                        data, status = self._request("POST", f"/verification/{self.vid}/step/collectStudentPersonalInfo", body)
                        request_log.append({"step": "collectStudentPersonalInfo", "status": status, "response": data})

                        if status != 200:
                            stats.record(self.org["name"], False)
                            info["status"] = "failed"; info["error"] = f"Submit failed: HTTP {status} - {data}"
                            self._write_info(out_dir, info); self._save_log(out_dir, request_log)
                            print(f"     [{get_current_time()}] ❗ Submit failed: HTTP {status}")
                            return {"success": False, "error": info["error"], "outputDir": str(out_dir)}

                        if data.get("currentStep") == "error":
                            stats.record(self.org["name"], False)
                            info["status"] = "failed"; info["error"] = f"Error: {data.get('errorIds', [])}"
                            self._write_info(out_dir, info); self._save_log(out_dir, request_log)
                            return {"success": False, "error": info["error"], "outputDir": str(out_dir)}

                        current_step = data.get("currentStep", "")

                    if current_step in ["sso", "collectStudentPersonalInfo"]:
                        print(f"   [{get_current_time()}] ⏳ Skipping SSO...")
                        _, status = self._request("DELETE", f"/verification/{self.vid}/step/sso")
                        request_log.append({"step": "skip_sso", "status": status})

                    print(f"   [{get_current_time()}] ✅ Đã nộp thông tin! Trang web SheerID hiện đã ở bước upload tài liệu.")

                print("\n" + "═"*58)
                print(" 📋 THÔNG TIN SINH VIÊN (DÙNG ĐỂ ĐIỀN TRÊN WEB NẾU CẦN):")
                print("─"*58)
                print(f"   🏫 Trường đại học: {self.org['name']}")
                print(f"   👤 Họ (First Name): {first}")
                print(f"   👤 Tên (Last Name): {last}")
                print(f"   🎂 Ngày sinh:       {dob}")
                print(f"   📧 Email:           {email}")
                print(f"   🔗 Link xác minh:   {self.url}")
                print(f"   📁 Thư mục tài liệu:{out_dir}")
                print("─"*58)

                # Mở link SheerID trên trình duyệt
                open_web = input("   🌐 Mở link xác minh SheerID trên trình duyệt ngay? (Y/n): ").strip().lower()
                if open_web != 'n':
                    try:
                        webbrowser.open(self.url)
                    except Exception as e:
                        print(f"   ⚠️ Không thể mở trình duyệt: {e}")

                print("\n   👉 Bạn hãy tải 1 trong các ảnh trong thư mục lên trang web SheerID:")
                print("      - scanned_id_card.png (Thẻ sinh viên)")
                print("      - class_schedule.png  (Thời khóa biểu)")
                print("      - tuition_receipt.png (Biên lai học phí)")
                print("\n   👉 Sau khi bạn đã nhấn Gửi / Nộp tài liệu trên trình duyệt xong:")
                print("      - Nhấn [Enter] để Tool tự động theo dõi kết quả xét duyệt (Polling)")
                print("      - Hoặc gõ 'q' để kết thúc ngay.")
                user_done = input("   > ").strip().lower()

                if user_done == 'q':
                    info["status"] = "pending"
                    info["manual"] = True
                    self._write_info(out_dir, info)
                    self._save_log(out_dir, request_log)
                    return {
                        "status": "pending",
                        "student": f"{first} {last}",
                        "email": email,
                        "school": self.org["name"],
                        "outputDir": str(out_dir),
                        "manual": True
                    }

                print(f"\n   [{get_current_time()}] ⏳ Bắt đầu theo dõi kết quả xét duyệt từ SheerID...")

            else:
                # ==========================================
                # CHẾ ĐỘ 1: TỰ ĐỘNG NỘP LÊN SHEERID
                # ==========================================
                print(f"\n   [{get_current_time()}] 🤖 CHẾ ĐỘ: TỰ ĐỘNG NỘP LÊN SHEERID...")
                time.sleep(2)
                print(f"   [{get_current_time()}] ⏳ Bắt đầu gửi dữ liệu lên SheerID...")

                if current_step == "collectStudentPersonalInfo":
                    print(f"   [{get_current_time()}] ▶ Step 2/3: Submitting student info...")
                    body = {
                        "firstName": first, "lastName": last, "birthDate": dob, "email": email, "phoneNumber": "",
                        "organization": {"id": self.org["id"], "idExtended": self.org["idExtended"], "name": self.org["name"]},
                        "deviceFingerprintHash": self.fingerprint, "locale": "en-US",
                        "metadata": {
                            "marketConsentValue": False, "verificationId": self.vid,
                            "refererUrl": f"https://services.sheerid.com/verify/{PROGRAM_ID}/?verificationId={self.vid}",
                            "flags": '{"collect-info-step-email-first":"default","doc-upload-considerations":"default","doc-upload-may24":"default","doc-upload-redesign-use-legacy-message-keys":false,"docUpload-assertion-checklist":"default","font-size":"default","include-cvec-field-france-student":"not-labeled-optional"}',
                            "submissionOptIn": "By submitting the personal information above, I acknowledge that my personal information is being collected under the privacy policy of the business from which I am seeking a discount",
                        },
                    }

                    captcha_token = self.solve_captcha()
                    body["captchaToken"] = captcha_token

                    data, status = self._request("POST", f"/verification/{self.vid}/step/collectStudentPersonalInfo", body)
                    request_log.append({"step": "collectStudentPersonalInfo", "status": status, "response": data})

                    if status != 200:
                        stats.record(self.org["name"], False)
                        info["status"] = "failed"; info["error"] = f"Submit failed: HTTP {status} - {data}"
                        self._write_info(out_dir, info); self._save_log(out_dir, request_log)
                        print(f"     [{get_current_time()}] ❗ Submit failed: HTTP {status}")
                        return {"success": False, "error": info["error"], "outputDir": str(out_dir)}

                    if data.get("currentStep") == "error":
                        stats.record(self.org["name"], False)
                        info["status"] = "failed"; info["error"] = f"Error: {data.get('errorIds', [])}"
                        self._write_info(out_dir, info); self._save_log(out_dir, request_log)
                        return {"success": False, "error": info["error"], "outputDir": str(out_dir)}

                    print(f"     [{get_current_time()}] 📍 Current step: {data.get('currentStep')}")
                    current_step = data.get("currentStep", "")
                elif current_step in ["docUpload", "sso"]:
                    print(f"   [{get_current_time()}] ▶ Step 2/3: Skipping (already past info submission)...")

                if current_step in ["sso", "collectStudentPersonalInfo"]:
                    print(f"   [{get_current_time()}] ▶ Step 3/4: Skipping SSO...")
                    _, status = self._request("DELETE", f"/verification/{self.vid}/step/sso")
                    request_log.append({"step": "skip_sso", "status": status})

                print(f"   [{get_current_time()}] ▶ Step 4/5: Uploading {len(docs_data)} documents...")
                
                files_payload = [{"fileName": name, "mimeType": "image/png", "fileSize": len(data)} for name, data in docs_data.items()]
                upload_body = {"files": files_payload}
                
                data, status = self._request("POST", f"/verification/{self.vid}/step/docUpload", upload_body)
                request_log.append({"step": "docUpload", "status": status, "response": data})

                if not data.get("documents"):
                    stats.record(self.org["name"], False)
                    info["status"] = "failed"; info["error"] = "No upload URLs returned"
                    self._write_info(out_dir, info); self._save_log(out_dir, request_log)
                    return {"success": False, "error": "No upload URL", "outputDir": str(out_dir)}

                uploaded_count = 0
                for i, doc_info in enumerate(data["documents"]):
                    file_name = files_payload[i]["fileName"]
                    upload_url = doc_info.get("uploadUrl")
                    file_content = docs_data[file_name]
                    
                    print(f"     [{get_current_time()}] ⏳ Đang tải lên: {file_name}...")
                    if self._upload_s3(upload_url, file_content):
                        uploaded_count += 1
                        print(f"     [{get_current_time()}] ✅ Đã tải lên: {file_name}")
                    else:
                        print(f"     [{get_current_time()}] ❌ Tải lên thất bại: {file_name}")

                if uploaded_count == 0:
                    stats.record(self.org["name"], False)
                    info["status"] = "failed"; info["error"] = "S3 upload failed for all files"
                    self._write_info(out_dir, info); self._save_log(out_dir, request_log)
                    return {"success": False, "error": "Upload failed", "outputDir": str(out_dir)}

                print(f"   [{get_current_time()}] ▶ Step 5/5: Completing upload...")
                data, status = self._request("POST", f"/verification/{self.vid}/step/completeDocUpload")
                request_log.append({"step": "completeDocUpload", "status": status, "response": data})
                print(f"     [{get_current_time()}] ✅ Upload completed: {data.get('currentStep', 'pending')}")

            # ==========================================
            # POLLING (CHỜ KẾT QUẢ TỪ SHEERID)
            # ==========================================
            print("\n" + "═"*58)
            print(f" ⏳ [{get_current_time()}] ĐANG CHỜ SHEERID XÉT DUYỆT (TỐI ĐA 5 PHÚT)...")
            print(" (Hệ thống sẽ tự động kiểm tra lại mỗi 15 giây)")
            print("═"*58)
            
            final_status = "pending"
            final_data = {}
            
            for attempt in range(20): # 20 * 15s = 300s (5 phút)
                time.sleep(15)
                check_data, _ = self._request("GET", f"/verification/{self.vid}")
                step = check_data.get("currentStep", "")
                
                if step == "success":
                    final_status = "success"
                    final_data = check_data
                    break
                elif step in ["error", "rejected", "failure"]:
                    final_status = "failed"
                    final_data = check_data
                    break
                else:
                    print(f"   [{get_current_time()}] ⏳ Lần {attempt+1}/20: Trạng thái hiện tại là '{step}'. Tiếp tục chờ...")

            if final_status == "success":
                stats.record(self.org["name"], True)
                info["status"] = "success"; info["completedAt"] = datetime.now().isoformat()
                self._write_info(out_dir, info); self._save_log(out_dir, request_log)
                return {
                    "success": True, "status": "success",
                    "message": "VERIFICATION SUCCESSFUL!",
                    "student": f"{first} {last}", "email": email, "school": self.org["name"],
                    "outputDir": str(out_dir),
                }
            elif final_status == "failed":
                stats.record(self.org["name"], False)
                info["status"] = "failed"; info["error"] = f"Rejected: {final_data.get('errorIds', [])}"
                self._write_info(out_dir, info); self._save_log(out_dir, request_log)
                return {
                    "success": False, "status": "rejected",
                    "error": f"SheerID Rejected: {final_data.get('errorIds', [])}",
                    "student": f"{first} {last}", "email": email, "school": self.org["name"],
                    "outputDir": str(out_dir),
                }
            else:
                stats.record(self.org["name"], True)
                info["status"] = "submitted"; info["completedAt"] = datetime.now().isoformat()
                self._write_info(out_dir, info); self._save_log(out_dir, request_log)
                return {
                    "success": True, "status": "pending",
                    "message": "Submitted successfully. Pending manual review (24-48h).",
                    "student": f"{first} {last}", "email": email, "school": self.org["name"],
                    "outputDir": str(out_dir),
                }

        except KeyboardInterrupt:
            print("\n\n   🛑 Đã hủy bởi người dùng. Link SheerID này chưa bị gửi đi.")
            return {"success": False, "error": "Cancelled by user", "outputDir": str(out_dir) if out_dir else None}
        except Exception as e:
            if self.org: stats.record(self.org["name"], False)
            if out_dir:
                try:
                    info["status"] = "exception"; info["error"] = str(e)
                    self._write_info(out_dir, info); self._save_log(out_dir, request_log)
                except: pass
            return {"success": False, "error": str(e), "outputDir": str(out_dir) if out_dir else None}


# ============ MAIN (INTERACTIVE) ============
def main():
    print()
    print("╔" + "═" * 58 + "╗")
    print("║" + " 🤖 Google One (Gemini) Verification Tool".center(58) + "║")
    print("║" + " SheerID Student Discount (Auto-Polling & IP Rotate)".center(58) + "║")
    print("╚" + "═" * 58 + "╝")
    print()

    # Hỗ trợ nhận link từ tham số dòng lệnh hoặc nhập tương tác
    if len(sys.argv) > 1 and "sheerid.com" in sys.argv[1]:
        url = sys.argv[1].strip()
        print(f"   🔗 Link SheerID (từ tham số): {url}")
    else:
        url = input("   🔗 Nhập link SheerID (https://services.sheerid.com/verify/...):\n   > ").strip()
        
    if not url or "sheerid.com" not in url:
        print("\n   ❌ Link không hợp lệ. Phải chứa 'sheerid.com'")
        return

    print("\n   🔑 Nhập Sitekey (Nhấn Enter để dùng mặc định: 0x4AAAAAACaWNlR_tN9-HfHj):")
    sitekey = input("   > ").strip()
    if not sitekey:
        sitekey = DEFAULT_SITEKEY
        print(f"      -> Đã chọn Sitekey mặc định: {sitekey}")
    elif not sitekey.startswith("0x"):
        print("\n   ❌ Sitekey không hợp lệ.")
        return

    # ========================================================
    # ĐỔI IP DÂN CƯ TRƯỚC KHI CHẠY VÀ THÔNG BÁO IP
    # ========================================================
    print("\n" + "═" * 58)
    print(" 🔄 [RESIDENTIAL PROXY] ĐỔI IP DÂN CƯ TRƯỚC KHI CHẠY")
    print("═" * 58)
    print(f"   ⏱️  Thời gian bắt đầu: {get_current_time()}")
    print("   ⏳ 1. Đang kiểm tra IP dân cư hiện tại...")
    
    current_ip = check_proxy_ip(HARDCODED_PROXY)
    print(f"   🔴 [IP HIỆN TẠI (Trước khi đổi)]: {current_ip}")
    
    print("   ⏳ 2. Đang tạo session mới và đổi IP dân cư...")
    active_proxy, old_ip, new_ip = rotate_residential_proxy(HARDCODED_PROXY)
    
    print(f"   🟢 [IP MỚI (Sau khi đổi)]:       {new_ip}")
    if current_ip != new_ip and new_ip != "Unknown" and not str(new_ip).startswith("Error"):
        print(f"   ✅ ĐÃ ĐỔI IP DÂN CƯ THÀNH CÔNG! ({current_ip} ➜ {new_ip})")
    else:
        print(f"   ℹ️  IP proxy hoạt động: {new_ip}")
        
    session_tag = re.search(r"session-([a-zA-Z0-9]+)", active_proxy)
    if session_tag:
        print(f"   🔒 Sticky Session ID: {session_tag.group(1)} (Cố định trong 10 phút)")
        
    print("═" * 58)
    print("   🚀 ĐÃ ĐỔI IP THÀNH CÔNG -> TIẾN HÀNH CHẠY XÁC MINH VỚI IP MỚI...")
    print("   ⏳ Processing...\n")

    verifier = GeminiVerifier(url, sitekey, proxy=active_proxy)

    check = verifier.check_link()
    if not check.get("valid"):
        print(f"\n   ❌ Link Error: {check.get('error')}")
        return

    result = verifier.verify()

    # Kiểm tra IP sau khi chạy xong
    end_ip = check_proxy_ip(active_proxy)

    print()
    print("═" * 58)
    
    status = result.get("status", "unknown")
    
    if status == "success":
        print(f"\n ✅✅✅ [SUCCESS] - ĐÃ XÁC MINH THÀNH CÔNG! ✅✅✅")
        print(f"   Thời gian: {get_current_time()}")
        print(f"   👤 Sinh viên: {result.get('student')}")
        print(f"   📧 Email: {result.get('email')}")
        print(f"   🏫 Trường: {result.get('school')}")
        print(f"   📁 Ảnh lưu tại: {result.get('outputDir')}")
        print("\n   🎉 Tài khoản Google One AI Premium của bạn đã được kích hoạt!")
        
    elif status == "rejected":
        print(f"\n ❌❌❌ [REJECTED] - SHEERID ĐÃ TỪ CHỐI! ❌❌❌")
        print(f"   Thời gian: {get_current_time()}")
        print(f"   Lỗi: {result.get('error')}")
        print(f"   📁 Ảnh lưu tại: {result.get('outputDir')}")
        print("\n   💡 Khuyên dùng: Thử tạo link mới, đổi trường, hoặc dùng proxy khác.")
        
    elif status == "pending":
        print(f"\n ⏳ [PENDING] - ĐÃ GỬI, ĐANG CHỜ DUYỆT!")
        print(f"   Thời gian: {get_current_time()}")
        print(f"   👤 Sinh viên: {result.get('student')}")
        print(f"   📧 Email: {result.get('email')}")
        print(f"   🏫 Trường: {result.get('school')}")
        print(f"   📁 Ảnh lưu tại: {result.get('outputDir')}")
        print("\n   ⏳ Hồ sơ đã được gửi thành công.")
        print("   Bạn hãy kiểm tra email Google (hoặc hộp thư rác) trong 24-48 giờ tới.")
        
    else:
        print(f"\n ❌ [FAILED] - CÓ LỖI XẢY RA!")
        print(f"   Lỗi: {result.get('error')}")
        if result.get("outputDir"):
            print(f"   📁 Debug files: {result.get('outputDir')}")
            
    print("\n" + "═" * 58)
    print(f" 🟢 IP Proxy ban đầu (Lúc chạy):      {new_ip}")
    print(f" 🟢 IP Proxy kết thúc (Sau khi chạy): {end_ip}")
    if new_ip != end_ip:
         print(" ⚠️ CẢNH BÁO: IP ĐÃ BỊ XOAY TRONG QUÁ TRÌNH CHẠY! (Đây có thể là lý do gây lỗi)")
    else:
         print(" ✅ IP giữ cố định (Sticky) hoàn hảo trong suốt quá trình chạy!")
    print("═" * 58)

    stats.print_stats()
    print("\n   Nhấn Enter để thoát...")
    input()

if __name__ == "__main__":
    main()