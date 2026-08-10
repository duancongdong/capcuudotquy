# Danh sách bệnh viện cấp cứu đột quỵ — Việt Nam

Trang tĩnh, mobile-first, hiển thị danh sách bệnh viện/trung tâm sẵn sàng cấp cứu đột quỵ.
Nguồn dữ liệu: Hội Đột Quỵ Việt Nam (VNSA), cập nhật 09/2025.

## Cấu trúc
```
├── index.html          # giao diện, fetch dữ liệu từ data/hospitals.json
├── data/
│   └── hospitals.json  # nguồn dữ liệu duy nhất (170 bản ghi)
└── scripts/
    └── build_data.py   # script transcribe PDF gốc -> hospitals.json (chạy lại khi có PDF mới)
```

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
git add .
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

## Cập nhật dữ liệu định kỳ thủ công (không qua bot)
Nếu cần sửa tay nhanh, mở `data/hospitals.json`, sửa trực tiếp trên GitHub web editor hoặc local, commit — GitHub Pages tự rebuild trong ~1 phút. Khi hệ thống bot (Apps Script) đã hoạt động, các cập nhật định kỳ nên đi qua luồng email + phê duyệt hội đồng để giữ tính minh bạch và đúng quy trình đã thống nhất.
