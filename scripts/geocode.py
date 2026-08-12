# -*- coding: utf-8 -*-
"""
Chạy trên máy bạn (không chạy được trong sandbox này vì domain bị chặn):
    pip install requests
    python3 geocode.py

Việc này CHỈ CẦN CHẠY 1 LẦN (hoặc mỗi khi có địa chỉ mới) — kết quả lưu thẳng
vào data/hospitals.json, trang web sẽ đọc lat/lng có sẵn, không geocode lúc runtime.

Tuân thủ chính sách sử dụng của Nominatim (OpenStreetMap):
- Tối đa 1 request/giây
- Bắt buộc có User-Agent riêng, không dùng chung IP để spam
- https://operations.osmfoundation.org/policies/nominatim/
"""
import json, time, requests

INPUT_FILE = "data/hospitals.json"
OUTPUT_FILE = "data/hospitals.json"  # ghi đè sau khi thêm lat/lng
USER_AGENT = "capcuudotquy-vn/1.0 (lien-he: your-email@example.com)"  # SỬA email liên hệ thật

def geocode(address):
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": address, "format": "json", "limit": 1, "countrycodes": "vn"}
    headers = {"User-Agent": USER_AGENT}
    r = requests.get(url, params=params, headers=headers, timeout=10)
    r.raise_for_status()
    results = r.json()
    if not results:
        return None, None
    return float(results[0]["lat"]), float(results[0]["lon"])

def main():
    with open(INPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)

    for i, h in enumerate(data):
        if h.get("lat") and h.get("lng"):
            continue  # đã có toạ độ, bỏ qua để tiết kiệm request

        full_address = f"{h['address']}, Việt Nam"
        try:
            lat, lng = geocode(full_address)
        except Exception as e:
            print(f"[{i+1}/{len(data)}] LỖI: {h['name']} — {e}")
            lat, lng = None, None

        h["lat"] = lat
        h["lng"] = lng

        status = "OK" if lat else "KHÔNG TÌM THẤY — cần sửa địa chỉ hoặc nhập tay"
        print(f"[{i+1}/{len(data)}] {h['name']}: {status}")

        time.sleep(1.1)  # bắt buộc theo chính sách Nominatim

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    missing = [h["name"] for h in data if not h.get("lat")]
    print(f"\nHoàn tất. {len(data) - len(missing)}/{len(data)} địa chỉ geocode thành công.")
    if missing:
        print("Cần kiểm tra/nhập tay toạ độ cho:")
        for name in missing:
            print(f"  - {name}")

if __name__ == "__main__":
    main()
