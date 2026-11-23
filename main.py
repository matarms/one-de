"""
CLI Entrypoint for Google One (Gemini) Student Verification Tool
Run locally in terminal:
    python main.py
    python main.py "https://services.sheerid.com/verify/..."
    python main.py "URL" --proxy "http://user:pass@host:port"
    python main.py --web  # Start Web Interface
"""

import sys
import argparse
from pathlib import Path

from verifier import (
    GeminiVerifier,
    rotate_residential_proxy,
    check_proxy_ip,
    mask_proxy_url,
    get_current_time,
    stats,
    DEFAULT_SITEKEY
)

def run_cli():
    parser = argparse.ArgumentParser(description="Google One (Gemini) SheerID Student Verification Tool")
    parser.add_argument("url", nargs="?", help="SheerID Verification URL")
    parser.add_argument("--proxy", help="Custom proxy URL (http://user:pass@host:port)")
    parser.add_argument("--school", type=int, help="Target School ID")
    parser.add_argument("--docs-only", action="store_true", help="Only generate documents without submitting")
    parser.add_argument("--web", action="store_true", help="Launch Web Interface")
    parser.add_argument("--port", type=int, default=8080, help="Web server port (default: 8080)")

    args = parser.parse_args()

    if args.web:
        import uvicorn
        print(f"🚀 Starting Web Interface at http://localhost:{args.port}...")
        uvicorn.run("app:app", host="0.0.0.0", port=args.port, reload=False)
        return

    url = args.url
    if not url:
        print("=" * 60)
        print("🤖 GOOGLE ONE (GEMINI) STUDENT VERIFICATION TOOL - CLI")
        print("=" * 60)
        url = input("\n🔗 Nhập link xác minh SheerID: ").strip()

    if not url:
        print("❌ Lỗi: Bạn chưa nhập link xác minh!")
        return

    # Proxy selection
    active_proxy = args.proxy
    if not active_proxy:
        print("\n" + "═" * 58)
        print(" 🔄 [PROXY-CHEAP RESIDENTIAL] CẤP PHÁT IP DÂN CƯ MỸ...")
        print("═" * 58)
        p_url, old_ip, new_ip, sid = rotate_residential_proxy()
        active_proxy = p_url
        if sid:
            masked_sid = str(sid)[:4] + "****"
            print(f"   🔒 Sticky Session ID:         {masked_sid} (Cố định trong 10 phút)")
        print(f"   🔴 [IP Tham chiếu trước đó]: {old_ip}")
        print(f"   🟢 [IP DÂN CƯ MỚI ĐƯỢC CẤP]: {new_ip}")
        print(f"   🌐 Proxy Gateway:             {mask_proxy_url(active_proxy)}")
        print("═" * 58)

    verifier = GeminiVerifier(
        url=url,
        proxy=active_proxy,
        auto_upload=(not args.docs_only),
        target_school_id=args.school
    )

    print("\n🔍 Đang kiểm tra liên kết SheerID...")
    check = verifier.check_link()
    if not check.get("valid"):
        print(f"\n❌ Lỗi liên kết: {check.get('error')}")
        return

    result = verifier.verify()
    print("\n" + "═" * 58)
    status = result.get("status", "unknown")
    if status == "success":
        print(f"\n ✅✅✅ [SUCCESS] - ĐÃ XÁC MINH THÀNH CÔNG! ✅✅✅")
        print(f"   🎓 Sinh viên: {result.get('student')}")
        print(f"   📧 Email EDU: {result.get('email')}")
        print(f"   🏫 Trường:    {result.get('school')}")
        print(f"   📁 Thư mục:   {result.get('outputDir')}")
        print("\n 🎉 Tài khoản Google One AI Premium của bạn đã được kích hoạt!")
    elif status == "pending":
        print(f"\n ⏳ [PENDING] - HỒ SƠ ĐÃ NỘP, ĐANG CHỜ SHEERID XÉT DUYỆT!")
        print(f"   🎓 Sinh viên: {result.get('student')}")
        print(f"   📧 Email EDU: {result.get('email')}")
        print(f"   🏫 Trường:    {result.get('school')}")
        print("\n 📬 Hãy kiểm tra email Google của bạn trong 24-48 giờ tới.")
    elif status == "rejected":
        print(f"\n ❌❌❌ [REJECTED] - SHEERID ĐÃ TỪ CHỐI! ❌❌❌")
        print(f"   Lỗi: {result.get('error')}")
    else:
        print(f"\n ❌ [FAILED] - CÓ LỖI XẢY RA!")
        print(f"   Lỗi: {result.get('error')}")

    print("═" * 58)

if __name__ == "__main__":
    run_cli()
