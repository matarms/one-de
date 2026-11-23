import base64

def get_base64_image(url: str) -> str:
    """Tải ảnh từ URL và chuyển thành Base64 để nhúng trực tiếp vào HTML (tránh lỗi vỡ ảnh)"""
    try:
        resp = httpx.get(url, follow_redirects=True, timeout=10)
        if resp.status_code == 200:
            b64 = base64.b64encode(resp.content).decode('utf-8')
            # Đoán định dạng file (thường là jpg hoặc png)
            mime = "image/jpeg" if url.lower().endswith(('.jpg', '.jpeg')) else "image/png"
            return f"data:{mime};base64,{b64}"
    except Exception:
        pass
    return "" # Trả về rỗng nếu lỗi

# ============ API DOCUMENT GENERATOR ============
def download_document_from_api(first, last, school, dob, doc_type, save_path, domain) -> Optional[bytes]:
    print(f"     ⏳ Đang chuẩn bị ảnh cho {school}...")
    
    # 1. Tải ảnh và chuyển sang Base64 để đảm bảo không bị vỡ
    print("     ⏳ Đang tải Logo, Ảnh thẻ, QR Code...")
    logo_b64 = get_base64_image(f"https://logo.pubrio.com/{domain}")
    # Dùng i.pravatar.cc thay cho thispersondoesnotexist vì nó ổn định hơn, không bị chặn
    photo_b64 = get_base64_image("https://i.pravatar.cc/300?img=11") 
    qr_b64 = get_base64_image(f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=https://{domain}/verify")
    
    current_date = time.strftime('%B %d, %Y')
    random_id = random.randint(10000000, 99999999)

    # 2. Tạo HTML với bàn gỗ thật và vỏ nhựa (Bọc trong f-string cẩn thận)
    # CHÚ Ý: Dùng dấu ngoặc nhọn kép {{ }} cho các đoạn CSS để Python không hiểu nhầm là biến
    html_content = f"""
    <div style="width: 850px; height: 650px; background-image: url('https://images.unsplash.com/photo-1551269901-5c5e14c25df7?q=80&w=1000&auto=format&fit=crop'); background-size: cover; background-position: center; position: relative; display: flex; justify-content: center; align-items: center; box-sizing: border-box;">

        <!-- Lớp tối 4 góc (Vignette) tạo cảm giác ánh sáng phòng -->
        <div style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; box-shadow: inset 0 0 150px rgba(0,0,0,0.7); pointer-events: none;"></div>

        <!-- VỎ NHỰA (Plastic Sleeve) -->
        <div style="width: 540px; height: 360px; background: rgba(255, 255, 255, 0.15); border: 2px solid rgba(255,255,255,0.4); border-radius: 15px; position: relative; z-index: 5; box-shadow: 0 20px 40px rgba(0,0,0,0.5), inset 0 0 30px rgba(255,255,255,0.3); display: flex; justify-content: center; align-items: center; padding-top: 10px; transform: rotate(-2deg); backdrop-filter: blur(2px);">

            <!-- Lỗ đục trên vỏ nhựa -->
            <div style="position: absolute; top: 15px; width: 100%; display: flex; justify-content: center; gap: 40px;">
                <div style="width: 18px; height: 18px; background: #333; border-radius: 50%; box-shadow: inset 0 4px 8px rgba(0,0,0,0.8), 0 1px 1px rgba(255,255,255,0.5);"></div>
                <div style="width: 18px; height: 18px; background: #333; border-radius: 50%; box-shadow: inset 0 4px 8px rgba(0,0,0,0.8), 0 1px 1px rgba(255,255,255,0.5);"></div>
            </div>

            <!-- TẤM THẺ SINH VIÊN (Bên trong vỏ nhựa) -->
            <div style="width: 500px; height: 310px; background: #ffffff; position: relative; border-radius: 8px; overflow: hidden; box-shadow: 0 5px 15px rgba(0,0,0,0.2); border: 1px solid #ccc; font-family: Arial, sans-serif;">
                
                <!-- Header -->
                <div style="background: #002855; color: white; padding: 12px 20px; display: flex; align-items: center; justify-content: space-between;">
                    <div style="display: flex; align-items: center; gap: 15px;">
                        <img src="{logo_b64}" style="height: 45px; background: white; padding: 2px; border-radius: 50%;">
                        <div>
                            <h2 style="margin: 0; font-size: 16px; text-transform: uppercase; letter-spacing: 0.5px;">{school}</h2>
                            <p style="margin: 2px 0 0 0; font-size: 10px; color: #ccc;">STUDENT IDENTITY CARD</p>
                        </div>
                    </div>
                    <div style="font-size: 14px; font-weight: bold;">FALL 2026</div>
                </div>

                <!-- Body -->
                <div style="padding: 20px; display: flex; gap: 20px;">
                    <img src="{photo_b64}" style="width: 110px; height: 140px; object-fit: cover; border: 2px solid #002855; border-radius: 4px;">
                    
                    <div style="flex-grow: 1;">
                        <div style="font-size: 10px; color: #666; font-weight: bold; margin-top: 5px;">SURNAME</div>
                        <div style="font-size: 22px; font-weight: 900; color: #000; text-transform: uppercase;">{last}</div>
                        
                        <div style="font-size: 10px; color: #666; font-weight: bold; margin-top: 10px;">OTHER NAMES</div>
                        <div style="font-size: 18px; font-weight: bold; color: #333; text-transform: uppercase;">{first}</div>
                        
                        <div style="display: flex; justify-content: space-between; margin-top: 15px;">
                            <div>
                                <div style="font-size: 10px; color: #666; font-weight: bold;">DATE OF BIRTH</div>
                                <div style="font-size: 14px; font-weight: bold;">{dob}</div>
                            </div>
                            <div>
                                <div style="font-size: 10px; color: #666; font-weight: bold;">STUDENT ID</div>
                                <div style="font-size: 14px; font-weight: bold; color: #d32f2f;">{random_id}</div>
                            </div>
                        </div>
                    </div>
                    
                    <div style="display: flex; flex-direction: column; justify-content: flex-end; align-items: center;">
                        <img src="{qr_b64}" style="width: 70px; height: 70px;">
                    </div>
                </div>

                <!-- Footer -->
                <div style="position: absolute; bottom: 0; width: 100%; background: #e0e0e0; padding: 10px 20px; display: flex; justify-content: space-between; box-sizing: border-box;">
                    <div style="font-size: 11px; font-weight: bold; color: #333;">ISSUED: {current_date}</div>
                    <div style="font-size: 11px; font-weight: bold; color: #333;">VALID THRU: 08/2028</div>
                </div>
            </div>

            <!-- Lớp phản chiếu ánh sáng của vỏ nhựa (Glare) đè lên thẻ -->
            <div style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: linear-gradient(135deg, rgba(255,255,255,0.4) 0%, rgba(255,255,255,0) 40%); z-index: 10; pointer-events: none; border-radius: 15px;"></div>
        </div>
    </div>
    """

    try:
        response = httpx.post(
            "https://hcti.io/v1/image",
            auth=(HCTI_USER_ID, HCTI_API_KEY),
            data={
                "html": html_content,
                "css": "body { margin: 0; }",
                "google_fonts": "Arial"
            },
            timeout=30
        )
        
        if response.status_code == 200:
            image_url = response.json().get("url")
            img_response = httpx.get(image_url)
            if img_response.status_code == 200:
                data = img_response.content
                save_path.write_bytes(data)
                print(f"     💾 Đã lưu ảnh: {save_path.name}")
                return data
            else:
                print(f"     ❌ Không thể tải ảnh từ URL (HTTP {img_response.status_code})")
                return None
        else:
            print(f"     ❌ Lỗi API HTML/CSS to Image (HTTP {response.status_code})")
            print(f"     Chi tiết: {response.text}")
            return None
    except Exception as e:
        print(f"     ❌ Lỗi kết nối API: {e}")
        return None