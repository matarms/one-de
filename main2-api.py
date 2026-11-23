import httpx
import time
import sys
from pathlib import Path
from io import BytesIO
from PIL import Image

# Đảm bảo thư mục output tồn tại
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

def generate_document_via_api(doc_type="transcript"):
    print("⏳ Đang kết nối tới API tạo giấy tờ...")
    
    # Dữ liệu mẫu
    first_name = "Rebecca"
    last_name = "Thompson"
    school = "University of Pennsylvania"
    
    # API URL (Sử dụng API mã nguồn mở)
    # Lưu ý: API này có thể thay đổi hoặc die bất cứ lúc nào
    api_url = "https://sicg.vercel.app/gen"
    
    params = {
        "name": f"{first_name} {last_name}",
        "college": school,
        "id": "94697925",
        "dob": "2004-02-27",
        "issue_date": time.strftime("%d %b %Y"), # Ngày cấp hôm nay
        "type": doc_type # "transcript" hoặc "id_card"
    }

    try:
        print(f"🔄 Đang yêu cầu API tạo: {doc_type}...")
        response = httpx.get(api_url, params=params, timeout=30)
        
        if response.status_code == 200:
            print("✅ Tải thành công từ API!")
            
            # Lưu file ảnh
            filename = f"api_{doc_type}.png"
            filepath = OUTPUT_DIR / filename
            filepath.write_bytes(response.content)
            
            print(f"💾 Đã lưu ảnh tại: {filepath}")
            
            # Hiển thị ảnh ra màn hình (nếu có thư viện Pillow)
            try:
                img = Image.open(BytesIO(response.content))
                img.show()
            except Exception as e:
                print(f"⚠️ Không thể mở ảnh tự động: {e}")
                
        else:
            print(f"❌ Lỗi từ API: HTTP {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"❌ Lỗi kết nối mạng: {e}")
        print("Vui lòng kiểm tra lại kết nối Internet hoặc API đã bị đóng.")

if __name__ == "__main__":
    print("========================================")
    print("🤖 TOOL TẠO GIẤY TỜ SINH VIÊN QUA API")
    print("========================================")
    
    # Tạo cả 2 loại giấy tờ
    generate_document_via_api(doc_type="transcript")
    generate_document_via_api(doc_type="id_card")
    
    print("\n🎉 Hoàn tất! Nhấn Enter để thoát...")
    input()