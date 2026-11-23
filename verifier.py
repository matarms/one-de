"""
Core Verifier Module for Google One (Gemini) Student Verification Tool
SheerID Student Verification for Google One AI Premium

Enhanced with:
- Non-blocking callback logging for Web UI & CLI
- Local Headless Chromium & HCTI API fallback
- Multi-Style University Templates (Ivy vs State)
- Sticky Residential Proxy Rotation & IP Tracking
- Robust Error Handling & Step Recovery
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
import subprocess
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, Callable, List

# Load environment variables if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    import httpx
except ImportError:
    print("❌ Error: httpx required. Install: pip install httpx")
    sys.exit(1)

try:
    from twocaptcha import TwoCaptcha
    HAS_2CAPTCHA = True
except ImportError:
    HAS_2CAPTCHA = False

# Import anti-detection module
try:
    # Try local first
    from anti_detect import (
        get_headers,
        get_fingerprint,
        get_random_user_agent,
        random_delay as anti_delay,
        create_session,
    )
    HAS_ANTI_DETECT = True
except ImportError:
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
    except ImportError:
        HAS_ANTI_DETECT = False


# ============ DEFAULT CONFIG ============
PROGRAM_ID = "67c8c14f5f17a83b745e3f82"
SHEERID_API_URL = "https://services.sheerid.com/rest/v2"
MIN_DELAY = 300
MAX_DELAY = 800
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_SITEKEY = "0x4AAAAAACaWNlR_tN9-HfHj"
DEFAULT_CAPTCHA_API_KEY = os.environ.get("CAPTCHA_API_KEY", "ecc6bc9b27e7d71e42b583e175b1e865")
DEFAULT_HCTI_USER_ID = os.environ.get("HCTI_USER_ID", "01M799KYJQ86GW2CVNZJQPQ3HC")
DEFAULT_HCTI_API_KEY = os.environ.get("HCTI_API_KEY", "h1-7gM9UGXeDVmG6JTxOLmuemjg-e3e257fc")


def get_current_time() -> str:
    return datetime.now().strftime('%H:%M:%S')


def get_env_var(name: str) -> Optional[str]:
    """Read env var from process environment or Windows Registry fallback"""
    val = os.environ.get(name)
    if val:
        return val
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment")
        val, _ = winreg.QueryValueEx(key, name)
        winreg.CloseKey(key)
        return val
    except Exception:
        return None


_CACHED_PROXY_CHEAP: Optional[Tuple[str, str, str, str, str, str]] = None


def fetch_proxy_cheap_credentials() -> Optional[Tuple[str, str, str, str, str, str]]:
    """Tự động đồng bộ credentials từ Proxy-Cheap REST API (https://api.proxy-cheap.com/proxies)"""
    global _CACHED_PROXY_CHEAP
    if _CACHED_PROXY_CHEAP:
        return _CACHED_PROXY_CHEAP

    api_key = get_env_var("PROXY_CHEAP_API_KEY") or "01a1f415-dece-75b3-bd25-39d6d8119cb3"
    api_secret = get_env_var("PROXY_CHEAP_API_SECRET") or "01a1f415-dece-7627-bd25-39d6d88b27c4"

    if api_key and api_secret:
        try:
            headers = {
                "X-Api-Key": api_key.strip(),
                "X-Api-Secret": api_secret.strip(),
                "Accept": "application/json"
            }
            proxy_id = get_env_var("PROXY_CHEAP_ID") or "2653591"
            resp = httpx.get(f"https://api.proxy-cheap.com/proxies/{proxy_id}", headers=headers, timeout=8)
            if resp.status_code == 200:
                p = resp.json()
                auth = p.get("authentication", {})
                u = auth.get("username")
                pw = auth.get("password")
                if u and pw:
                    _CACHED_PROXY_CHEAP = (u, pw, "thehub.proxy-cheap.com", "8080", "US", "10")
                    return _CACHED_PROXY_CHEAP
        except Exception:
            pass

    # Dự phòng thông tin đã xác thực trực tiếp
    _CACHED_PROXY_CHEAP = ("e7kbQPHHUQO0vy3", "v25auuqAWEH6xHi", "thehub.proxy-cheap.com", "8080", "US", "10")
    return _CACHED_PROXY_CHEAP


def get_proxy_config() -> Optional[Tuple[str, str, str, str, str, str]]:
    """Read proxy credentials from env vars, Proxy-Cheap API, or cached config"""
    user = get_env_var("PROXY_USER")
    pass_base = get_env_var("PROXY_PASS_BASE")
    host = get_env_var("PROXY_HOST") or "thehub.proxy-cheap.com"
    port = get_env_var("PROXY_PORT") or "8080"
    country = get_env_var("PROXY_COUNTRY") or "US"
    ttl = get_env_var("PROXY_TTL") or "10"
    
    if user and pass_base:
        return user, pass_base, host, str(port), country, str(ttl)
        
    return fetch_proxy_cheap_credentials()


def auto_rotate_session(proxy_url: Optional[str], session_id: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
    """
    Tự động xoay session ID cho proxy residential để lấy IP mới:
    Hỗ trợ TrueProxies, Proxy-Cheap, Smartproxy, v.v.
    """
    if not proxy_url:
        return None, None
        
    sid = session_id or ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    
    if "-session-" in proxy_url:
        rotated = re.sub(r"-session-[a-zA-Z0-9]+", f"-session-{sid}", proxy_url)
        return rotated, sid
        
    if "_session-" in proxy_url:
        rotated = re.sub(r"_session-[a-zA-Z0-9]+", f"_session-{sid}", proxy_url)
        return rotated, sid
        
    if "session-" in proxy_url:
        rotated = re.sub(r"session-[a-zA-Z0-9]+", f"session-{sid}", proxy_url)
        return rotated, sid

    return proxy_url, None


def generate_proxy_url(session_id: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
    """Tạo URL proxy Proxy-Cheap với session ID ngẫu nhiên mới"""
    sid = session_id or str(random.randint(10_000_000, 99_999_999))
    
    cfg = get_proxy_config()
    if cfg:
        user, pass_base, host, port, country, ttl = cfg
        pw = f"{pass_base}_country-{country}_session-{sid}_ttl-{ttl}"
        proxy_url = f"http://{user}:{pw}@{host}:{port}"
        return proxy_url, sid

    default_p = get_env_var("DEFAULT_PROXY") or get_env_var("HTTP_PROXY") or get_env_var("HTTPS_PROXY")
    if default_p:
        rotated, rotated_sid = auto_rotate_session(default_p, sid)
        return rotated, (rotated_sid or "default")

    return None, None


def mask_proxy_url(proxy_url: Optional[str]) -> str:
    if not proxy_url:
        return "None (Direct Connection)"
    return re.sub(r":([^@:]+)@", ":***@", proxy_url)


def check_proxy_ip(proxy_url: Optional[str], timeout: int = 4, max_retries: int = 1) -> str:
    """Check current public IP via proxy with fast failure on auth errors"""
    if not proxy_url:
        try:
            resp = httpx.get("https://api.ipify.org?format=json", timeout=timeout)
            if resp.status_code == 200:
                return resp.json().get("ip", "Direct IP")
        except Exception:
            return "Direct Connection"
        return "Direct IP"

    endpoints = [
        "https://api.ipify.org?format=json",
        "https://checkip.amazonaws.com"
    ]
    
    for attempt in range(max_retries):
        for ep in endpoints:
            try:
                resp = httpx.get(ep, proxy=proxy_url, timeout=timeout)
                if resp.status_code == 200:
                    if "json" in ep:
                        return resp.json().get("ip", "Unknown")
                    return resp.text.strip()
                elif resp.status_code == 407:
                    return "Error: 407 Proxy Auth Required (Hết hạn hoặc sai user/pass)"
            except httpx.ProxyError as pe:
                if "407" in str(pe):
                    return "Error: 407 Proxy Auth Required (Hết hạn hoặc sai user/pass)"
                return f"Error: Proxy Connection Error ({pe})"
            except Exception:
                continue
    return "Unknown"


def rotate_residential_proxy(max_retries: int = 2) -> Tuple[Optional[str], str, str, Optional[str]]:
    """Cấp phát session ID mới và kiểm tra IP dân cư Mỹ từ Proxy-Cheap"""
    candidate_proxy, sid = generate_proxy_url()
    if not candidate_proxy:
        return None, "Direct", "Direct", None

    candidate_ip = "Unknown"
    for attempt in range(1, max_retries + 1):
        candidate_proxy, sid = generate_proxy_url()
        candidate_ip = check_proxy_ip(candidate_proxy, timeout=4)
        
        if candidate_ip != "Unknown" and not str(candidate_ip).startswith("Error"):
            return candidate_proxy, candidate_ip, candidate_ip, sid
            
        time.sleep(0.3)
        
    err_label = candidate_ip if str(candidate_ip).startswith("Error") else "Error: Proxy không phản hồi (Bị chặn bởi IP Whitelist)"
    return None, err_label, err_label, sid


# ============ UNIVERSITIES DATABASE ============
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
    def __init__(self, stats_path: Optional[Path] = None):
        self.file = stats_path or (BASE_DIR / "stats.json")
        self.data = self._load()

    def _load(self) -> Dict:
        if self.file.exists():
            try:
                return json.loads(self.file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"total": 0, "success": 0, "failed": 0, "orgs": {}}

    def _save(self):
        try:
            self.file.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

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

    def get_summary(self) -> Dict:
        return {
            "total": self.data.get("total", 0),
            "success": self.data.get("success", 0),
            "failed": self.data.get("failed", 0),
            "successRate": round(self.get_rate(), 1),
            "orgs": self.data.get("orgs", {})
        }


stats = Stats()


def select_university(target_id: Optional[int] = None) -> Dict:
    """Select university by ID, or choose weighted random"""
    if target_id is not None:
        for u in UNIVERSITIES:
            if u["id"] == target_id:
                return {**u, "idExtended": str(u["id"])}
    weights = [u["weight"] for u in UNIVERSITIES]
    total = sum(weights)
    r = random.uniform(0, total)
    cumulative = 0
    for uni, weight in zip(UNIVERSITIES, weights):
        cumulative += weight
        if r <= cumulative:
            return {**uni, "idExtended": str(uni["id"])}
    return {**UNIVERSITIES[0], "idExtended": str(UNIVERSITIES[0]["id"])}


# ============ STUDENT GENERATORS ============
FIRST_NAMES_MALE = ["James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph", "Thomas", "Christopher", "Charles", "Daniel", "Matthew", "Anthony", "Mark", "Donald", "Steven", "Andrew", "Paul", "Joshua"]
FIRST_NAMES_FEMALE = ["Mary", "Patricia", "Jennifer", "Linda", "Barbara", "Elizabeth", "Susan", "Jessica", "Sarah", "Karen", "Lisa", "Nancy", "Betty", "Margaret", "Sandra", "Ashley", "Kimberly", "Emily", "Donna", "Michelle"]
LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker", "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores", "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell", "Carter", "Roberts", "Turner", "Phillips", "Evans", "Parker", "Edwards"]


def random_delay():
    time.sleep(random.uniform(MIN_DELAY, MAX_DELAY) / 1000)


def generate_fingerprint() -> str:
    raw = f"{random.random()}-{time.time()}-{random.randint(1000, 9999)}"
    return hashlib.md5(raw.encode()).hexdigest()


def generate_name_and_photo() -> Tuple[str, str, str, str]:
    is_male = random.choice([True, False])
    first = random.choice(FIRST_NAMES_MALE if is_male else FIRST_NAMES_FEMALE)
    last = random.choice(LAST_NAMES)
    photo_id = random.randint(1, 35) if is_male else random.randint(36, 70)
    photo_url = f"https://i.pravatar.cc/300?img={photo_id}"
    netid = f"{first[0].lower()}{last.lower()}{random.randint(100, 999)}"
    return first, last, photo_url, netid


def generate_email(first: str, last: str, domain: str, netid: str) -> str:
    patterns = [
        f"{first.lower()}.{last.lower()}{random.randint(10, 99)}@{domain}",
        f"{netid}@{domain}",
        f"{first[0].lower()}{last.lower()}{random.randint(100, 999)}@{domain}"
    ]
    return random.choice(patterns)


def generate_birth_date() -> str:
    start = datetime(2002, 1, 1)
    end = datetime(2005, 12, 31)
    delta = end - start
    random_days = random.randint(0, delta.days)
    return (start + timedelta(days=random_days)).strftime("%Y-%m-%d")


def create_output_dir(email: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dir_name = f"{email}_{timestamp}"
    path = OUTPUT_DIR / dir_name
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_base64_image(url: str) -> str:
    """Fetch image and encode as base64 data URI"""
    try:
        resp = httpx.get(url, follow_redirects=True, timeout=12)
        if resp.status_code == 200:
            b64 = base64.b64encode(resp.content).decode('utf-8')
            mime = "image/jpeg" if url.lower().endswith(('.jpg', '.jpeg')) else "image/png"
            return f"data:{mime};base64,{b64}"
    except Exception:
        pass
    return ""


# ============ HEADLESS BROWSER & RENDERING ENGINE ============

def find_headless_browser() -> Optional[str]:
    """Find Chrome/Chromium/Edge path for headless rendering"""
    # 1. Environment variable override
    env_bin = os.environ.get("CHROME_BIN") or os.environ.get("CHROMIUM_PATH")
    if env_bin and os.path.exists(env_bin):
        return env_bin

    # 2. Linux standard paths (Railway / Docker)
    linux_paths = [
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/snap/bin/chromium"
    ]
    for p in linux_paths:
        if os.path.exists(p):
            return p

    # 3. Windows standard paths
    win_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
    ]
    for p in win_paths:
        if os.path.exists(p):
            return p

    # 4. PATH lookup
    for prog in ["chromium", "chromium-browser", "google-chrome", "chrome", "msedge"]:
        p = shutil.which(prog)
        if p:
            return p
    return None


def render_html_to_image(
    html_content: str,
    save_path: Path,
    width: int = 950,
    height: int = 1250,
    google_fonts: str = None,
    hcti_user: Optional[str] = None,
    hcti_key: Optional[str] = None
) -> Optional[bytes]:
    """
    Render HTML to high quality PNG:
    1. Local headless Chromium/Chrome with --no-sandbox (Railway/Linux & Windows ready).
    2. Fallback to HCTI API if browser is not available.
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
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--hide-scrollbars",
                f"--window-size={width},{height}",
                f"--screenshot={tmp_png}",
                tmp_html
            ]
            
            subprocess.run(cmd, capture_output=True, timeout=30)
            
            if tmp_png.exists() and tmp_png.stat().st_size > 0:
                data = tmp_png.read_bytes()
                save_path.write_bytes(data)
                return data
        except Exception:
            pass
        finally:
            if tmp_html and os.path.exists(tmp_html):
                try: os.remove(tmp_html)
                except Exception: pass
            if tmp_png and tmp_png.exists():
                try: os.remove(tmp_png)
                except Exception: pass

    # Fallback: HCTI API
    hcti_u = hcti_user or DEFAULT_HCTI_USER_ID
    hcti_k = hcti_key or DEFAULT_HCTI_API_KEY
    if hcti_u and hcti_k:
        try:
            data_payload = {"html": html_content, "css": "body { margin: 0; }"}
            if google_fonts:
                data_payload["google_fonts"] = google_fonts
                
            response = httpx.post("https://hcti.io/v1/image", auth=(hcti_u, hcti_k), data=data_payload, timeout=30)
            if response.status_code == 200:
                img_url = response.json().get("url")
                img_resp = httpx.get(img_url, timeout=30)
                if img_resp.status_code == 200:
                    save_path.write_bytes(img_resp.content)
                    return img_resp.content
        except Exception:
            pass
        
    return None


# ============ DOCUMENT TEMPLATES ============

def generate_scanned_id_card(
    first: str, last: str, school_data: Dict, dob: str, save_path: Path,
    photo_b64: str, logo_b64: str, finance_data: Dict, netid: str,
    hcti_user: str = None, hcti_key: str = None
) -> Optional[bytes]:
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
                        <h2 style="color: white; margin: 0; font-size: 20px; font-weight: bold; letter-spacing: 0.5px;">{school}</h2>
                        <span style="color: rgba(255,255,255,0.8); font-size: 13px; font-weight: 500;">STUDENT IDENTIFICATION</span>
                    </div>
                </div>
            </div>
            <div style="padding: 25px 30px; display: flex; gap: 30px; position: relative;">
                <div style="position: absolute; right: 20px; top: 20px; width: 180px; height: 180px; opacity: 0.04; pointer-events: none;">
                    <img src="{logo_b64}" style="width: 100%; height: 100%; object-fit: contain;">
                </div>
                <div style="width: 160px; height: 210px; border: 3px solid #e0e0e0; border-radius: 8px; overflow: hidden; background: #eee; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                    <img src="{photo_b64}" style="width: 100%; height: 100%; object-fit: cover;">
                </div>
                <div style="flex: 1; display: flex; flex-direction: column; justify-content: space-between; z-index: 2;">
                    <div>
                        <div style="font-size: 12px; color: #777; font-weight: bold; text-transform: uppercase;">Name</div>
                        <div style="font-size: 24px; font-weight: bold; color: #111; margin-bottom: 12px;">{first} {last}</div>
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                            <div>
                                <div style="font-size: 11px; color: #777; font-weight: bold;">STUDENT ID</div>
                                <div style="font-size: 15px; font-weight: 600; color: #333;">{student_id}</div>
                            </div>
                            <div>
                                <div style="font-size: 11px; color: #777; font-weight: bold;">NETID</div>
                                <div style="font-size: 15px; font-weight: 600; color: #333;">{netid}</div>
                            </div>
                            <div>
                                <div style="font-size: 11px; color: #777; font-weight: bold;">DATE OF BIRTH</div>
                                <div style="font-size: 15px; font-weight: 600; color: #333;">{dob}</div>
                            </div>
                            <div>
                                <div style="font-size: 11px; color: #777; font-weight: bold;">STATUS</div>
                                <div style="font-size: 15px; font-weight: 600; color: #2e7d32;">UNDERGRADUATE</div>
                            </div>
                        </div>
                    </div>
                    <div style="display: flex; justify-content: space-between; align-items: flex-end; border-top: 1px solid #eee; padding-top: 10px;">
                        <div>
                            <span style="font-size: 10px; color: #888;">ISSUED: {issue_date}</span><br>
                            <span style="font-size: 10px; color: #d32f2f; font-weight: bold;">EXPIRES: {valid_thru}</span>
                        </div>
                        <div style="width: 50px; height: 50px; background: linear-gradient(135deg, #e0e0e0, #f5f5f5, #e0e0e0); border-radius: 50%; display: flex; align-items: center; justify-content: center; border: 1px solid #ccc; box-shadow: inset 0 0 5px rgba(0,0,0,0.2);">
                            <span style="font-size: 8px; font-weight: bold; color: #888; text-align: center;">OFFICIAL<br>SEAL</span>
                        </div>
                    </div>
                </div>
            </div>
            <div style="position: absolute; bottom: 0; left: 0; width: 100%; height: 6px; background: {secondary}; border-bottom-left-radius: 12px; border-bottom-right-radius: 12px;"></div>
        </div>
        <div style="width: 700px; height: 440px; background: #fdfdfd; border-radius: 12px; position: relative; box-shadow: 15px 25px 35px rgba(0,0,0,0.6); transform: perspective(1000px) rotateX(15deg) rotateY(-10deg) rotateZ(-3deg); display: flex; flex-direction: column; justify-content: space-between; box-sizing: border-box; overflow: hidden;">
            <div style="height: 60px; background: #1a1a1a; margin-top: 30px; width: 100%;"></div>
            <div style="padding: 20px 40px; font-size: 11px; color: #555; line-height: 1.5;">
                <p style="margin: 0 0 10px 0;">This card is the property of <strong>{school}</strong> and is non-transferable. If found, please return to: {address}.</p>
                <p style="margin: 0;">For emergency assistance call {phone}.</p>
            </div>
            <div style="padding: 0 40px 30px 40px; display: flex; justify-content: space-between; align-items: center;">
                <div style="text-align: center;">
                    <img src="{barcode_url}" style="height: 45px; display: block; margin: 0 auto 5px auto;">
                    <span style="font-family: monospace; font-size: 12px; letter-spacing: 2px;">{student_id}</span>
                </div>
                <div style="font-size: 12px; font-weight: bold; color: #333; border: 1px dashed #999; padding: 10px 15px; border-radius: 4px;">
                    FALL 2026 VALIDATED
                </div>
            </div>
        </div>
    </div>
    """
    return render_html_to_image(html_content, save_path, width=950, height=1150, google_fonts="Arial", hcti_user=hcti_user, hcti_key=hcti_key)


def generate_hcti_doc(
    first: str, last: str, school_data: Dict, dob: str, save_path: Path, doc_type: str,
    photo_b64: str, logo_b64: str, finance_data: Dict,
    hcti_user: str = None, hcti_key: str = None
) -> Optional[bytes]:
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

    return render_html_to_image(html_content, save_path, width=950, height=1250, google_fonts="Times New Roman, Arial, Great Vibes", hcti_user=hcti_user, hcti_key=hcti_key)


# ============ VERIFIER CLASS ============
class GeminiVerifier:
    def __init__(
        self,
        url: str,
        sitekey: str = DEFAULT_SITEKEY,
        proxy: Optional[str] = None,
        log_callback: Optional[Callable[[Dict], None]] = None,
        auto_upload: bool = True,
        target_school_id: Optional[int] = None,
        captcha_api_key: Optional[str] = None,
        hcti_user_id: Optional[str] = None,
        hcti_api_key: Optional[str] = None,
        output_dir: Optional[Path] = None
    ):
        self.url = url.strip()
        self.sitekey = sitekey
        self.proxy = proxy
        self.callback = log_callback
        self.auto_upload = auto_upload
        self.target_school_id = target_school_id
        self.captcha_key = captcha_api_key or DEFAULT_CAPTCHA_API_KEY
        self.hcti_user = hcti_user_id or DEFAULT_HCTI_USER_ID
        self.hcti_key = hcti_api_key or DEFAULT_HCTI_API_KEY
        self.custom_output_dir = output_dir

        self.vid = self._parse_id(self.url)
        self.fingerprint = generate_fingerprint()

        # Session setup
        if HAS_ANTI_DETECT:
            try:
                self.client, self.lib_name = create_session(proxy)
            except Exception:
                self._setup_httpx_session(proxy)
        else:
            self._setup_httpx_session(proxy)

        self.org = None
        self.is_cancelled = False

    def _setup_httpx_session(self, proxy: Optional[str]):
        proxy_url = None
        if proxy:
            if not proxy.startswith("http"):
                proxy = f"http://{proxy}"
            proxy_url = proxy
        timeout = httpx.Timeout(timeout=30.0, connect=20.0, read=30.0, write=20.0, pool=15.0)
        self.client = httpx.Client(timeout=timeout, proxy=proxy_url)
        self.lib_name = "httpx"

    def cancel(self):
        self.is_cancelled = True

    def log(self, message: str, level: str = "info", progress: Optional[int] = None, data: Optional[Dict] = None):
        t = get_current_time()
        print(f"[{t}] {message}")
        if self.callback:
            try:
                payload = {
                    "timestamp": t,
                    "message": message,
                    "level": level,
                    "progress": progress,
                    "data": data or {}
                }
                self.callback(payload)
            except Exception:
                pass

    def __del__(self):
        if hasattr(self, "client"):
            try: self.client.close()
            except Exception: pass

    @staticmethod
    def _parse_id(url: str) -> Optional[str]:
        match = re.search(r"verificationId=([a-f0-9]+)", url, re.IGNORECASE)
        return match.group(1) if match else None

    def _request(self, method: str, endpoint: str, body: Dict = None, max_retries: int = 3) -> Tuple[Dict, int]:
        last_exc = None
        for attempt in range(1, max_retries + 2):
            if attempt > 1:
                time.sleep(1.5)
            else:
                random_delay()
            try:
                headers = get_headers(for_sheerid=True) if HAS_ANTI_DETECT else {"Content-Type": "application/json"}
                resp = self.client.request(method, f"{SHEERID_API_URL}{endpoint}", json=body, headers=headers)
                try: parsed = resp.json() if resp.text else {}
                except Exception: parsed = {"_text": resp.text}
                return parsed, resp.status_code
            except Exception as e:
                last_exc = e
                if attempt <= max_retries:
                    err_name = type(e).__name__
                    err_str = f" [{err_name}]" if not str(e) else f" [{err_name}: {str(e)[:60]}]"
                    self.log(f"⚠️ Yêu cầu tới SheerID bị chậm/timeout (Lần {attempt}/{max_retries}){err_str}, đang tự động thử lại...", level="warning")
                    
                    if self.proxy:
                        # Thử đổi session ID residential proxy sang node khác
                        rotated_proxy, new_sid = auto_rotate_session(self.proxy)
                        if not new_sid or rotated_proxy == self.proxy:
                            rotated_proxy, new_sid = generate_proxy_url()
                        
                        if rotated_proxy and rotated_proxy != self.proxy:
                            self.log(f"🔄 Proxy node phản hồi chậm, tự động xoay sang Session IP dân cư mới ({new_sid})...", level="info")
                            try: self.client.close()
                            except Exception: pass
                            self.proxy = rotated_proxy
                            timeout = httpx.Timeout(timeout=30.0, connect=20.0, read=30.0, write=20.0, pool=15.0)
                            self.client = httpx.Client(timeout=timeout, proxy=rotated_proxy)
                            continue
                        elif attempt >= max_retries:
                            # Lần thử cuối cùng: thử chuyển sang kết nối trực tiếp của server
                            self.log("⚡ Thử đổi sang kết nối dự phòng trực tiếp của server...", level="warning")
                            try: self.client.close()
                            except Exception: pass
                            timeout = httpx.Timeout(timeout=25.0, connect=15.0)
                            self.client = httpx.Client(timeout=timeout)
                            self.proxy = None
                            continue
                    continue
        raise Exception(f"Request failed: {last_exc}")

    def _upload_s3(self, url: str, data: bytes) -> bool:
        attempts = [
            lambda: self.client.put(url, content=data, headers={"Content-Type": "image/png"}, timeout=60),
            lambda: self.client.put(url, data=data, headers={"Content-Type": "image/png"}, timeout=60),
            lambda: self.client.request("PUT", url, data=data, headers={"Content-Type": "image/png"}, timeout=60),
            # Direct upload fallback (S3 presigned URLs accept direct connections reliably)
            lambda: httpx.put(url, content=data, headers={"Content-Type": "image/png"}, timeout=60)
        ]
        last_exc = None
        for fn in attempts:
            try:
                resp = fn()
                if hasattr(resp, "status_code"):
                    if 200 <= resp.status_code < 300: return True
                    return False
                else: return bool(resp)
            except Exception as e:
                last_exc = e
                continue
        return False

    @staticmethod
    def _save_log(out_dir: Path, log: list):
        if out_dir and log:
            try: (out_dir / "request_log.json").write_text(json.dumps(log, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
            except Exception: pass

    @staticmethod
    def _write_info(out_dir: Path, info: Dict):
        if out_dir:
            try: (out_dir / "info.json").write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")
            except Exception: pass

    def check_link(self) -> Dict:
        if not self.vid:
            return {"valid": False, "error": "URL không chứa verificationId hợp lệ"}
        data, status = self._request("GET", f"/verification/{self.vid}")
        if status != 200:
            return {"valid": False, "error": f"HTTP {status} - Link không tồn tại hoặc đã hết hạn"}
        step = data.get("currentStep", "")
        valid_steps = ["collectStudentPersonalInfo", "docUpload", "sso"]
        if step in valid_steps:
            return {"valid": True, "step": step}
        elif step == "success":
            return {"valid": False, "error": "Link này đã được xác minh thành công trước đó"}
        elif step == "pending":
            return {"valid": False, "error": "Hồ sơ của link này đang chờ xét duyệt"}
        return {"valid": False, "error": f"Trạng thái hiện tại không hợp lệ: {step}"}

    def solve_captcha(self) -> str:
        self.log("🔄 Đang giải CAPTCHA Cloudflare Turnstile qua 2Captcha...", level="info", progress=55)
        if not HAS_2CAPTCHA or not self.captcha_key:
            raise Exception("Thiếu thư viện 2captcha-python hoặc chưa cấu hình CAPTCHA_API_KEY")
        try:
            solver = TwoCaptcha(self.captcha_key)
            result = solver.turnstile(sitekey=self.sitekey, url=self.url)
            self.log("✅ Đã giải xong Turnstile CAPTCHA thành công!", level="success", progress=65)
            return result['code']
        except Exception as e:
            self.log(f"❌ Lỗi giải CAPTCHA: {e}", level="error")
            raise Exception(f"Lỗi giải Captcha: {e}")

    def verify(self) -> Dict:
        if not self.vid:
            return {"success": False, "status": "failed", "error": "Invalid verification URL"}

        out_dir: Optional[Path] = self.custom_output_dir
        request_log: list = []
        info: Dict = {}

        try:
            self.log("🔍 Đang kiểm tra trạng thái liên kết SheerID...", level="info", progress=5)
            check_data, check_status = self._request("GET", f"/verification/{self.vid}")
            if check_status != 200:
                return {"success": False, "status": "failed", "error": f"Link không hợp lệ: HTTP {check_status}"}

            current_step = check_data.get("currentStep", "")
            request_log.append({"step": "check", "status": check_status, "currentStep": current_step})
            self.log(f"📍 Bước hiện tại của SheerID: {current_step}", level="info", progress=15)

            # Generate student identity
            self.log("👤 Đang tạo hồ sơ sinh viên ngẫu nhiên...", level="info", progress=20)
            first, last, photo_url, netid = generate_name_and_photo()
            self.org = select_university(self.target_school_id)
            email = generate_email(first, last, self.org["domain"], netid)
            dob = generate_birth_date()
            logo_url = f"https://logo.pubrio.com/{self.org['domain']}"
            finance_data = {"student_id": random.randint(10000000, 99999999)}

            if not out_dir:
                out_dir = create_output_dir(email)

            self.log(f"🎓 Sinh viên: {first} {last} (NetID: {netid})", level="info")
            self.log(f"🏫 Trường: {self.org['name']} (Phong cách: {self.org['style']})", level="info")
            self.log(f"📧 Email: {email} | 🎂 Ngày sinh: {dob}", level="info", progress=25)

            # Download assets
            self.log("🖼️ Đang tải logo trường & ảnh sinh viên...", level="info", progress=30)
            logo_b64 = get_base64_image(logo_url)
            photo_b64 = get_base64_image(photo_url)
            
            if not logo_b64 or not photo_b64:
                stats.record(self.org["name"], False)
                return {"success": False, "status": "failed", "error": "Không thể tải logo hoặc ảnh thẻ", "outputDir": str(out_dir)}

            # Generate 3 documents
            self.log("📄 Đang tạo 3 loại giấy tờ (Thẻ SV, Thời khóa biểu, Biên lai)...", level="info", progress=35)
            docs_data = {}
            
            # 1. Scanned ID Card
            path_id = out_dir / "scanned_id_card.png"
            data_id = generate_scanned_id_card(
                first, last, self.org, dob, path_id, photo_b64, logo_b64, finance_data, netid,
                hcti_user=self.hcti_user, hcti_key=self.hcti_key
            )
            if data_id:
                docs_data["scanned_id_card.png"] = data_id
                self.log("✅ Đã tạo Thẻ sinh viên scan (scanned_id_card.png)", level="success", progress=40)

            # 2. Class Schedule
            path_sch = out_dir / "class_schedule.png"
            data_sch = generate_hcti_doc(
                first, last, self.org, dob, path_sch, "class_schedule", photo_b64, logo_b64, finance_data,
                hcti_user=self.hcti_user, hcti_key=self.hcti_key
            )
            if data_sch:
                docs_data["class_schedule.png"] = data_sch
                self.log("✅ Đã tạo Thời khóa biểu chính thức (class_schedule.png)", level="success", progress=45)

            # 3. Tuition Receipt
            path_rcp = out_dir / "tuition_receipt.png"
            data_rcp = generate_hcti_doc(
                first, last, self.org, dob, path_rcp, "tuition_receipt", photo_b64, logo_b64, finance_data,
                hcti_user=self.hcti_user, hcti_key=self.hcti_key
            )
            if data_rcp:
                docs_data["tuition_receipt.png"] = data_rcp
                self.log("✅ Đã tạo Biên lai đóng học phí (tuition_receipt.png)", level="success", progress=50)

            if not docs_data:
                stats.record(self.org["name"], False)
                return {"success": False, "status": "failed", "error": "Không thể tạo tài liệu", "outputDir": str(out_dir)}

            info = {
                "email": email, "firstName": first, "lastName": last, "birthDate": dob,
                "school": self.org["name"], "schoolId": self.org["id"], "schoolDomain": self.org["domain"],
                "photoUrl": photo_url, "netid": netid, "financeData": finance_data,
                "docFiles": list(docs_data.keys()), "verificationId": self.vid,
                "fingerprint": self.fingerprint, "createdAt": datetime.now().isoformat(), "status": "in_progress",
            }
            self._write_info(out_dir, info)
            self._save_log(out_dir, request_log)

            doc_file_list = list(docs_data.keys())
            self.log(f"📁 Đã tạo xong {len(doc_file_list)} tài liệu minh chứng!", level="success", progress=52, data={"docFiles": doc_file_list, "dirName": out_dir.name})

            # Check if user only requested docs generation (Preview/Manual mode)
            if not self.auto_upload:
                self.log("👤 Chế độ: Chỉ tạo giấy tờ (Bạn có thể tải ảnh về để tự upload)", level="info", progress=100)
                info["status"] = "docs_generated"
                self._write_info(out_dir, info)
                return {
                    "success": True,
                    "status": "docs_generated",
                    "message": "Đã tạo xong 3 loại tài liệu",
                    "student": f"{first} {last}",
                    "email": email,
                    "school": self.org["name"],
                    "dob": dob,
                    "docFiles": doc_file_list,
                    "outputDir": str(out_dir),
                    "dirName": out_dir.name
                }

            # ==========================================
            # AUTO SUBMIT PERSONAL INFO & CAPTCHA
            # ==========================================
            if current_step == "collectStudentPersonalInfo":
                self.log("📝 Bước 1/3: Nộp thông tin cá nhân sinh viên...", level="info", progress=54)
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
                    err_msg = f"Submit failed: HTTP {status} - {data}"
                    info["status"] = "failed"; info["error"] = err_msg
                    self._write_info(out_dir, info); self._save_log(out_dir, request_log)
                    self.log(f"❌ Nộp thông tin thất bại: {err_msg}", level="error")
                    return {"success": False, "status": "failed", "error": err_msg, "outputDir": str(out_dir)}

                if data.get("currentStep") == "error":
                    stats.record(self.org["name"], False)
                    err_msg = f"Lỗi từ SheerID: {data.get('errorIds', [])}"
                    info["status"] = "failed"; info["error"] = err_msg
                    self._write_info(out_dir, info); self._save_log(out_dir, request_log)
                    self.log(f"❌ SheerID báo lỗi: {err_msg}", level="error")
                    return {"success": False, "status": "failed", "error": err_msg, "outputDir": str(out_dir)}

                current_step = data.get("currentStep", "")
                self.log(f"✅ Đã nộp thông tin cá nhân thành công! Bước tiếp theo: {current_step}", level="success", progress=70)

            # Skip SSO if present
            if current_step in ["sso", "collectStudentPersonalInfo"]:
                self.log("⚡ Bước 2/3: Bỏ qua cổng SSO trường đại học...", level="info", progress=72)
                _, status = self._request("DELETE", f"/verification/{self.vid}/step/sso")
                request_log.append({"step": "skip_sso", "status": status})

            # ==========================================
            # UPLOAD DOCUMENTS TO S3
            # ==========================================
            self.log(f"📤 Bước 3/3: Đang yêu cầu cấp URL tải lên cho {len(docs_data)} tài liệu...", level="info", progress=75)
            files_payload = [{"fileName": name, "mimeType": "image/png", "fileSize": len(data)} for name, data in docs_data.items()]
            upload_body = {"files": files_payload}
            
            data, status = self._request("POST", f"/verification/{self.vid}/step/docUpload", upload_body)
            request_log.append({"step": "docUpload", "status": status, "response": data})

            if not data.get("documents"):
                stats.record(self.org["name"], False)
                err_msg = "SheerID không cấp URL tải lên tài liệu"
                info["status"] = "failed"; info["error"] = err_msg
                self._write_info(out_dir, info); self._save_log(out_dir, request_log)
                self.log(f"❌ {err_msg}", level="error")
                return {"success": False, "status": "failed", "error": err_msg, "outputDir": str(out_dir)}

            uploaded_count = 0
            for i, doc_info in enumerate(data["documents"]):
                file_name = files_payload[i]["fileName"]
                upload_url = doc_info.get("uploadUrl")
                file_content = docs_data[file_name]
                
                self.log(f"⏳ Đang tải lên S3: {file_name}...", level="info", progress=76 + i * 4)
                if self._upload_s3(upload_url, file_content):
                    uploaded_count += 1
                    self.log(f"✅ Tải lên S3 thành công: {file_name}", level="success")
                else:
                    self.log(f"⚠️ Tải lên S3 thất bại: {file_name}", level="warning")

            if uploaded_count == 0:
                stats.record(self.org["name"], False)
                err_msg = "Không tải được tài liệu nào lên S3"
                info["status"] = "failed"; info["error"] = err_msg
                self._write_info(out_dir, info); self._save_log(out_dir, request_log)
                self.log(f"❌ {err_msg}", level="error")
                return {"success": False, "status": "failed", "error": err_msg, "outputDir": str(out_dir)}

            self.log("🏁 Đang hoàn tất phiên nộp hồ sơ...", level="info", progress=88)
            data, status = self._request("POST", f"/verification/{self.vid}/step/completeDocUpload")
            request_log.append({"step": "completeDocUpload", "status": status, "response": data})
            self.log("✅ Đã hoàn tất việc nộp tài liệu lên SheerID!", level="success", progress=90)

            # ==========================================
            # POLLING FOR APPROVAL
            # ==========================================
            max_polls = 60  # 60 * 10s = 600s (10 phút)
            poll_interval = 10
            self.log(f"⏳ Bắt đầu theo dõi kết quả xét duyệt từ SheerID (Tối đa {max_polls * poll_interval // 60} phút)...", level="info", progress=92)
            final_status = "pending"
            final_data = {}
            
            for attempt in range(max_polls):
                if self.is_cancelled:
                    self.log("🛑 Đã dừng theo dõi theo yêu cầu", level="warning")
                    break
                time.sleep(poll_interval)
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
                    self.log(f"⏳ Lần {attempt+1}/{max_polls}: Trạng thái hiện tại: '{step}'. Vui lòng chờ...", level="info", progress=min(92 + int(attempt * 7 / max_polls), 99))

            # Handle result
            if final_status == "success":
                stats.record(self.org["name"], True)
                info["status"] = "success"; info["completedAt"] = datetime.now().isoformat()
                self._write_info(out_dir, info); self._save_log(out_dir, request_log)
                self.log("🎉 XÁC MINH THÀNH CÔNG! Gói Google One AI Premium đã được kích hoạt!", level="success", progress=100)
                return {
                    "success": True,
                    "status": "success",
                    "message": "Xác minh thành công! Gói Google One AI Premium đã được kích hoạt.",
                    "student": f"{first} {last}",
                    "email": email,
                    "school": self.org["name"],
                    "dob": dob,
                    "docFiles": doc_file_list,
                    "outputDir": str(out_dir),
                    "dirName": out_dir.name
                }
            elif final_status == "failed":
                stats.record(self.org["name"], False)
                err_msg = f"SheerID đã từ chối: {final_data.get('errorIds', [])}"
                info["status"] = "failed"; info["error"] = err_msg
                self._write_info(out_dir, info); self._save_log(out_dir, request_log)
                self.log(f"❌ {err_msg}", level="error", progress=100)
                return {
                    "success": False,
                    "status": "rejected",
                    "error": err_msg,
                    "student": f"{first} {last}",
                    "email": email,
                    "school": self.org["name"],
                    "dob": dob,
                    "docFiles": doc_file_list,
                    "outputDir": str(out_dir),
                    "dirName": out_dir.name
                }
            else:
                stats.record(self.org["name"], True)
                info["status"] = "submitted"; info["completedAt"] = datetime.now().isoformat()
                self._write_info(out_dir, info); self._save_log(out_dir, request_log)
                self.log("📫 Hồ sơ đã nộp thành công! Đang chờ duyệt qua email (24-48h).", level="info", progress=100)
                return {
                    "success": True,
                    "status": "pending",
                    "message": "Hồ sơ đã gửi thành công, đang chờ hệ thống SheerID duyệt.",
                    "student": f"{first} {last}",
                    "email": email,
                    "school": self.org["name"],
                    "dob": dob,
                    "docFiles": doc_file_list,
                    "outputDir": str(out_dir),
                    "dirName": out_dir.name
                }

        except Exception as e:
            if self.org:
                stats.record(self.org["name"], False)
            err_msg = str(e)
            if out_dir:
                try:
                    info["status"] = "exception"; info["error"] = err_msg
                    self._write_info(out_dir, info); self._save_log(out_dir, request_log)
                except Exception:
                    pass
            self.log(f"❌ Lỗi ngoại lệ: {err_msg}", level="error")
            return {"success": False, "status": "failed", "error": err_msg, "outputDir": str(out_dir) if out_dir else None}
