# Danh sách bệnh viện cấp cứu đột quỵ — Việt Nam

Trang tĩnh, mobile-first, hiển thị danh sách bệnh viện/trung tâm sẵn sàng cấp cứu đột quỵ.
Nguồn dữ liệu: Hội Đột Quỵ Việt Nam (VNSA), cập nhật 09/2025.

## Cấu trúc
```
├── index.html          # khung giao diện (HTML thuần, không chứa JS/CSS inline)
├── style.css            # toàn bộ giao diện
├── app.js                # toàn bộ logic: fetch dữ liệu, tìm kiếm, lọc, bản đồ, định vị
├── data/
│   └── hospitals.json  # nguồn dữ liệu duy nhất (170 bản ghi)
└── scripts/
    ├── build_data.py   # script transcribe PDF gốc -> hospitals.json (chạy lại khi có PDF mới)
    └── geocode.py       # script tra toạ độ (lat/lng) cho từng địa chỉ, chạy 1 lần
```
**Vì sao tách JS/CSS ra file riêng:** trang dùng Content-Security-Policy (CSP) nghiêm ngặt —
`script-src 'self'` không có `'unsafe-inline'`. Nếu để JS/CSS nằm inline trong HTML, trình duyệt
sẽ CHẶN toàn bộ, trang sẽ trống trơn. Khi sửa code, luôn sửa trong `app.js`/`style.css`,
không thêm `<script>`/`<style>` hay `style="..."` inline trực tiếp vào `index.html`.

## Schema `hospitals.json`
```json
{
  "id": "benh-vien-bach-mai-ha-noi",
  "name": "Bệnh viện Bạch Mai",
  "type": "Trung Tâm Đột Quỵ",
  "province": "Hà Nội",
  "address": "78 Giải Phóng, Phường Kim Liên, Thành phố Hà Nội",
  "hotline": "086 9587687",
  "thrombolysis": "Có",
  "intervention": "Có",
  "status": "active",
  "updatedAt": "2025-09",
  "source": "Hội Đột Quỵ Việt Nam (VNSA)"
}
```
Đây chính là schema mà bot Apps Script (đã triển khai ở bước trước) sẽ đọc/ghi khi xử lý đề xuất cập nhật qua email.

## Triển khai lên GitHub — các bước thực hiện

### 1. Tạo repo mới trên GitHub
- Vào github.com → New repository → đặt tên, ví dụ `danh-sach-cap-cuu-dot-quy`
- Không tick "Initialize with README" (vì mình đã có sẵn)

### 2. Push code lên (chạy trên máy bạn, trong thư mục chứa các file này)
```bash
git init
git add index.html style.css app.js data/ scripts/ README.md
git commit -m "Khởi tạo: danh sách 170 bệnh viện cấp cứu đột quỵ (nguồn VNSA, 09/2025)"
git branch -M main
git remote add origin https://github.com/<ten-org-hoac-user>/<ten-repo>.git
git push -u origin main
```

### 3. Bật GitHub Pages
- Vào repo trên GitHub → **Settings → Pages**
- Source: **Deploy from a branch**
- Branch: `main` / `/ (root)`
- Lưu, đợi 1-2 phút → trang sẽ có tại `https://<ten-org>.github.io/<ten-repo>/`

### 4. Bật branch protection (khớp với kiến trúc bot đã thiết kế)
- Settings → Branches → Add rule cho `main`
- Bật **Require a pull request before merging**
- Điều này bắt buộc bot Apps Script (khi merge đề xuất đã đạt 80%) phải đi qua Pull Request, giữ lịch sử minh bạch, thay vì commit thẳng.

### 5. Tạo Fine-grained PAT cho bot (nếu chưa làm ở bước trước)
- Settings cá nhân → Developer settings → Fine-grained tokens
- Chỉ cấp quyền cho đúng repo này: `Contents: Read and write`, `Pull requests: Read and write`
- Dùng token này điền vào Script Property `GITHUB_TOKEN` trong Apps Script

### 6. Cập nhật QR code
- Sau khi có URL GitHub Pages thật, generate lại QR **tĩnh** trỏ thẳng vào URL đó (dùng script `qrcode` đã làm ở bước trước, không dùng dịch vụ rút gọn trung gian).

## Bản đồ (chế độ Bản đồ trên trang chủ)
Trang có nút chuyển "Danh sách / Bản đồ" ở đầu (dùng Leaflet.js + OpenStreetMap, miễn phí vĩnh viễn, không cần API key).

**Trước khi bản đồ hiển thị đủ 170 điểm, cần chạy geocode 1 lần:**
```bash
pip install requests
python3 scripts/geocode.py
```
Script này đọc từng địa chỉ trong `data/hospitals.json`, tra toạ độ qua Nominatim (OpenStreetMap, free), rồi ghi thẳng `lat`/`lng` vào file — chỉ cần chạy 1 lần (hoặc khi có địa chỉ mới), không geocode lúc runtime.

⚠️ Trước khi chạy, sửa `USER_AGENT` trong `scripts/geocode.py` thành email liên hệ thật của bạn (Nominatim yêu cầu để tránh bị chặn IP).

Hiện tại `data/hospitals.json` đã có sẵn toạ độ demo cho ~15 bệnh viện lớn để bạn xem trước giao diện — chạy `geocode.py` để điền đủ 170.

Nếu cần sửa tay nhanh, mở `data/hospitals.json`, sửa trực tiếp trên GitHub web editor hoặc local, commit — GitHub Pages tự rebuild trong ~1 phút. Khi hệ thống bot (Apps Script) đã hoạt động, các cập nhật định kỳ nên đi qua luồng email + phê duyệt hội đồng để giữ tính minh bạch và đúng quy trình đã thống nhất.

## Bảo mật — các quy tắc bắt buộc giữ khi sửa code sau này

1. **Không thêm `<script>` hay `<style>` hoặc `style="..."` inline vào `index.html`.**
   CSP (`Content-Security-Policy`) khai báo trong `<head>` chặn toàn bộ inline script/style
   không có `'unsafe-inline'`. Mọi logic JS luôn viết trong `app.js`, mọi CSS luôn viết trong
   `style.css`. Nếu cần thêm thư viện ngoài (CDN), phải thêm domain đó vào CSP
   (`script-src`/`style-src`) VÀ đính kèm SRI hash (`integrity="sha384-..."`) — có thể lấy
   hash chính thức tại trang cdnjs.cloudflare.com của thư viện đó.

2. **Luôn escape dữ liệu trước khi chèn vào HTML** — dùng hàm `escapeHtml()` có sẵn trong
   `app.js` cho bất kỳ trường nào lấy từ `hospitals.json` (tên, địa chỉ, loại hình...).

3. **Test lại CSP sau mỗi lần sửa lớn**: mở DevTools → tab Console, tải lại trang, thao tác
   qua hết các tính năng (tìm kiếm, lọc, Tìm gần tôi, chuyển Bản đồ). Nếu thấy dòng đỏ
   "Refused to..." hoặc "Content Security Policy" → có chỗ vi phạm CSP cần sửa ngay, vì
   nghĩa là tính năng đó đang bị trình duyệt âm thầm chặn.

4. **Không hardcode API key/token nào trong các file này** — trang không cần và không nên
   dùng Google Maps API hay bất kỳ dịch vụ trả phí nào; giữ nguyên kiến trúc free-vĩnh-viễn
   (OpenStreetMap, Leaflet, geolocation trình duyệt).

