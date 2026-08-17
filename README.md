# Tra cứu cơ sở điều trị đột quỵ — Việt Nam

Website tĩnh mobile-first giúp người dân nhanh chóng:

- Tìm cơ sở y tế có khả năng điều trị đột quỵ theo tên, tỉnh/thành và vị trí hiện tại.
- Gọi hotline của cơ sở hoặc gọi cấp cứu `115`.
- Mở chỉ đường bằng Google Maps.
- Xem bản đồ các cơ sở đã có tọa độ.
- Nhận biết dấu hiệu đột quỵ theo quy tắc `K-H-Ẩ-N`.

Nguồn dữ liệu quản trị là [Google Sheet danh sách bệnh viện](https://docs.google.com/spreadsheets/d/1gkHumsymX037G_PjioUIoAIpnUnOvTqoI4TgSHd7H6c/edit?usp=sharing). Dữ liệu phát hành cho website nằm tại [data/hospitals.json](data/hospitals.json).

> Nội dung trên website chỉ có tính chất tham khảo. Khi nghi ngờ đột quỵ, gọi `115` và đưa người bệnh đến cơ sở y tế càng sớm càng tốt. Cần gọi trước cho bệnh viện để xác nhận khả năng tiếp nhận.

## 1. Kiến trúc hệ thống

```text
Admin sửa Google Sheet
        │
        │ E2: Updating → Released
        ▼
Google Apps Script installable on-edit trigger
        │ workflow_dispatch + sheet_id + sheet_gid
        ▼
GitHub Actions: tải CSV → kiểm tra → sinh hospitals.json
        │
        │ commit/push data/hospitals.json lên main
        ▼
GitHub Pages tự triển khai website tĩnh
```

Website không có backend, database hoặc API server riêng. Trình duyệt tải HTML/CSS/JS và `data/hospitals.json` từ GitHub Pages.

### Thành phần chính

| Thành phần | Vai trò |
|---|---|
| `index.html` | HTML giao diện, metadata SEO, nội dung khẩn cấp và JSON-LD nền |
| `style.css` | Giao diện responsive, accessibility và trạng thái tải |
| `app.js` | Tải dữ liệu, tìm kiếm/lọc, định vị, bản đồ, JSON-LD động |
| `data/hospitals.json` | Dữ liệu phát hành duy nhất mà website sử dụng |
| `scripts/sync_sheet.py` | Parse và kiểm tra CSV từ Google Sheet rồi sinh JSON |
| `.github/workflows/sync-hospitals.yml` | GitHub Actions đồng bộ dữ liệu và commit JSON |
| `automation/google-apps-script/Code.gs` | Phát hiện E2 chuyển sang `Released` và gọi workflow |

Các file `data/hospitals_ggs.json`, `data/hospitals_ggs_v2.json` và file backup là các bản đối chiếu/kiểm tra, không phải nguồn dữ liệu website khi chạy production.

## 2. Chức năng website

### Tab Danh sách

- Hiển thị các bản ghi có `status: "active"`.
- Số đơn vị, số tỉnh/thành và tháng dữ liệu được tính động từ `hospitals.json`.
- Tab `Dấu hiệu` hiển thị thời điểm phiên bản website được phát hành dạng `hh:mm:ss dd/mm/yyyy` từ trường `publishedAt`.
- Tìm kiếm không dấu; hỗ trợ một số từ viết tắt như `BV`, `TPHCM`, `HN`, `stroke`.
- Lọc theo `province`.
- Gọi từng số hotline bằng liên kết `tel:`.
- Mở chỉ đường bằng Google Maps.
- Nút “Tìm bệnh viện gần tôi nhất” dùng Geolocation API của trình duyệt và sắp xếp theo khoảng cách đường thẳng. Thẻ có ghi rõ loại khoảng cách; nút “Chỉ đường” mở Google Maps đến đúng tọa độ `lat,lng` của cơ sở để xem quãng đường di chuyển thực tế.

### Tab Bản đồ

- Leaflet và marker cluster chỉ được tải khi người dùng mở tab Bản đồ lần đầu.
- Marker được cache, không dựng lại toàn bộ khi bộ lọc không thay đổi.
- Popup chỉ được tạo khi marker được click.
- Trạng thái chờ CDN và lỗi tải bản đồ được hiển thị rõ.
- Số cơ sở có tọa độ và tổng số cơ sở trong mô tả bản đồ lấy động từ dữ liệu.

Lớp nền hiện dùng tile OpenStreetMap. Đây là dịch vụ bên ngoài, cần giữ attribution và tuân thủ [Tile Usage Policy](https://operations.osmfoundation.org/policies/tiles/). Không dùng bản đồ để tải trước/bulk download tile.

### Tab Dấu hiệu

Nội dung sử dụng quy tắc `K-H-Ẩ-N`:

- `K`: Khóe miệng méo.
- `H`: Hụt sức tay.
- `Ẩ`: Âm giọng ngọng.
- `N`: Nhanh gọi `115`.

## 3. Cấu trúc dữ liệu `hospitals.json`

Mỗi phần tử là một cơ sở y tế:

```json
{
  "id": "benh-vien-bach-mai-ha-noi",
  "name": "Bệnh Viện Bạch Mai",
  "type": "Trung Tâm Đột Quỵ",
  "province": "Hà Nội",
  "address": "78 Giải Phóng, Phường Kim Liên, Thành phố Hà Nội",
  "hotline": "086 9587687",
  "thrombolysis": "Có",
  "intervention": "Có",
  "status": "active",
  "updatedAt": "2026-06",
  "publishedAt": "2026-08-17T08:05:05Z",
  "source": "Hội Đột Quỵ Việt Nam (VNSA)",
  "lat": 21.003117,
  "lng": 105.834165
}
```

`lat` và `lng` là số, không phải chuỗi:

- Phía trước dấu phẩy trong Google Sheet là `lat`.
- Phía sau dấu phẩy là `lng`.
- Định dạng bắt buộc: `lat,lng`, dùng dấu chấm cho phần thập phân, ví dụ `10.3872588,105.440206`.
- `lat` phải nằm trong `-90..90`; `lng` trong `-180..180`.
- Không dùng trường `geocode`.

> Khi nhập tọa độ, không đảo thứ tự thành `lng,lat`. Parser sẽ từ chối định dạng thừa, mơ hồ hoặc ngoài phạm vi.

Các trường bắt buộc khi đồng bộ là `name`, `type`, `address`, `province`. `thrombolysis` và `intervention` được chuẩn hóa thành `Có` hoặc `Không`.

## 4. Quy trình Admin cập nhật dữ liệu

### Quy ước Google Sheet

Sheet hiện dùng:

- `C2`: tháng cập nhật, dạng `MM/YYYY`, ví dụ `06/2026`.
- `E2`: trạng thái phát hành, chỉ dùng `Updating` hoặc `Released`.
- Hàng `3`: tiêu đề cột.
- Hàng `4` trở đi: dữ liệu bệnh viện.
- Cột `B`: `name`.
- Cột `C`: `type`.
- Cột `D`: `address`.
- Cột `E`: `hotline`.
- Cột `F`: `thrombolysis` — dropdown `Có/Không`.
- Cột `G`: `intervention` — dropdown `Có/Không`.
- Cột `H`: `province`.
- Cột `I`: tọa độ `lat,lng`.

Quy tắc cột `hotline`:

Chỉ sử dụng hai format sau:

**Format 1 — nhiều số điện thoại độc lập**

Các số được ngăn cách bằng dấu `/`. Mỗi số là một lựa chọn gọi riêng.

```text
02838412692 / 115
```

**Format 2 — số điện thoại có nhánh phụ**

Ghi nhánh trong ngoặc ngay sau số chính, dùng từ `nhấn` hoặc `ext` và số nhánh.

```text
02838412692 (nhấn 211) / 115
02839248158 (ext 440)
```

Khi người dùng bấm gọi, website chỉ gọi số chính (`02838412692` hoặc `02839248158`).
Phần `(nhấn 211)` hoặc `(ext 440)` chỉ là hướng dẫn để người dùng nhấn tiếp trên điện thoại.

### Các lỗi hotline thường gặp

- Dùng chữ `hoặc` thay cho `/`: `02838412692 hoặc 115` — phải sửa thành `02838412692 / 115`.
- Gộp số nhánh vào số điện thoại: `02838412692211` — phải ghi `02838412692 (nhấn 211)`.
- Ghi số nhánh trong ngoặc nhưng thiếu từ chỉ dẫn: `02838412692 (211)` — phải ghi `(nhấn 211)` hoặc `(ext 211)`.
- Ghi chú chữ không phải nhánh trong hotline: `02623841649 (Khoa cấp cứu)` — không thuộc format cho phép; đưa thông tin này vào trường phù hợp hoặc chỉ giữ số điện thoại.
- Dữ liệu bị lỗi ký tự hoặc lẫn chữ: `ầ1n1 5T hhoặc 02933115` — xóa và nhập lại bằng số điện thoại chính xác.
- Dùng dấu phẩy, dấu chấm phẩy hoặc xuống dòng để tách nhiều số — thay bằng dấu `/`.

Script đồng bộ sẽ kiểm tra các lỗi trên. Nếu hotline không hợp lệ, dữ liệu sẽ không được phát hành lên website; Admin cần sửa lỗi rồi chuyển `E2` sang `Released` lại.

### Cập nhật và phát hành

1. Đổi `E2` từ `Released` sang `Updating`.
2. Thêm hoặc sửa dữ liệu các bệnh viện.
3. Kiểm tra tên, địa chỉ, tỉnh/thành, hotline, hai cột Có/Không và tọa độ.
4. Đổi `E2` sang `Released`.
5. Apps Script gọi GitHub Actions bằng `workflow_dispatch`.
6. GitHub Actions tải đúng tab Sheet, kiểm tra và sinh lại `data/hospitals.json`.
7. Nếu JSON thay đổi, workflow ghi `publishedAt` theo thời điểm phát hành, commit/push lên `main`; GitHub Pages triển khai phiên bản mới.

Khi `Released` chuyển về `Updating`, không có workflow nào được gọi. Trigger chỉ thực hiện dispatch khi giá trị cuối của `E2` là `Released`.

`updatedAt` là tháng dữ liệu do Admin nhập tại ô `C2` theo danh sách cập nhật của Hội Đột Quỵ Việt Nam, ví dụ `06/2026`; trường này không phải ngày triển khai website. `publishedAt` là thời điểm phiên bản JSON được workflow phát hành và dùng cho ghi chú ở tab `Dấu hiệu`.

Nếu địa chỉ thay đổi nhưng cột I để trống, parser không giữ tọa độ cũ. Tọa độ cũ chỉ được giữ khi `name`, `province` và `address` không đổi; quy tắc này tránh hiển thị sai vị trí trên bản đồ.

## 5. Cài đặt tự động hóa một lần

### 5.1. GitHub Actions

Workflow nằm ở [.github/workflows/sync-hospitals.yml](.github/workflows/sync-hospitals.yml). Workflow nhận hai input:

- `sheet_id`: ID Google Sheet.
- `sheet_gid`: ID của tab đang đồng bộ.

Workflow đã khai báo:

```yaml
permissions:
  contents: write
```

Quyền này cho phép `GITHUB_TOKEN` commit `data/hospitals.json`. Nó không tự động vượt qua branch protection của `main`.

### 5.2. GitHub token cho Apps Script

Apps Script cần token để gọi API `workflow_dispatch`; token này không được đặt trong source code.

1. Tạo fine-grained PAT giới hạn vào repository `duancongdong/capcuudotquy`.
2. Cấp quyền repository `Actions: Read and write` và quyền metadata đọc nếu GitHub yêu cầu.
3. Không commit token vào Git.
4. Lưu token trong Apps Script bằng **Project Settings → Script properties**:

```text
Key:   GITHUB_ACTIONS_TOKEN
Value: <GitHub token>
```

Nếu token bị lộ, phải revoke ngay và tạo token mới.

### 5.3. Apps Script và installable trigger

1. Mở Google Sheet → **Extensions → Apps Script**.
2. Dán nội dung [automation/google-apps-script/Code.gs](automation/google-apps-script/Code.gs).
3. Lưu project.
4. Chọn hàm `setupReleaseTrigger` trên thanh công cụ và bấm **Run** đúng một lần.
5. Cấp quyền Google cho Apps Script bằng tài khoản owner hoặc tài khoản tạo trigger.
6. Mở **Triggers** (biểu tượng đồng hồ) để xác nhận chỉ còn đúng một trigger:

   - Function: `onEditReleasedStatus`
   - Event source: `From spreadsheet`
   - Event type: `On edit`

`setupReleaseTrigger` tự xóa các trigger trùng của chính project rồi tạo lại một trigger duy nhất. Nếu trước đây nhiều tài khoản khác nhau từng tạo trigger, mỗi tài khoản cần tự xóa trigger do mình tạo; Google chỉ cho phép một người xóa trigger của chính họ.

Trigger chỉ dispatch khi Admin sửa trực tiếp đúng một ô `E2` từ `Updating` sang `Released`. Dán/cập nhật cả Sheet, sửa các cột dữ liệu, định dạng ô, hoặc đổi `E2` từ trạng thái khác sẽ không chạy đồng bộ. Một khoảng chặn 60 giây cũng ngăn các trigger trùng dispatch lặp.

Installable trigger chạy với quyền của tài khoản tạo trigger. Vì vậy nên tạo trigger bằng tài khoản owner có quyền chỉnh sửa Sheet và quyền cần thiết trên GitHub. Trigger không chạy do thay đổi từ API/script; Admin cần sửa trực tiếp ô `E2` trên Sheet.

### 5.4. Quyền đọc Google Sheet

GitHub Actions tải CSV bằng URL export công khai. Sheet phải cho phép:

```text
Anyone with the link → Viewer
```

Quyền chỉnh sửa Sheet chỉ cấp cho Admin. Không đặt dữ liệu nhạy cảm vào Sheet vì bản export dùng cho website là dữ liệu công khai.

## 6. Branch protection và tự động push `main`

Workflow hiện tại commit trực tiếp lên `main`. Vì vậy nếu `main` bật `Require a pull request before merging`, push tự động có thể bị từ chối.

### Mục tiêu khuyến nghị

- Người dùng/developer: bắt buộc tạo Pull Request.
- Automation đồng bộ dữ liệu: được phép push trực tiếp nhưng chỉ với identity riêng.
- Không cấp bypass rộng cho mọi Admin hoặc dùng token cá nhân của owner trong workflow.

### Cách triển khai an toàn

Tạo một GitHub App riêng, ví dụ `Hospital Data Sync Bot`, chỉ cài trên repository này, cấp `Contents: Read and write`. Sau đó:

1. Thêm App vào bypass list của branch protection/ruleset cho `main`.
2. Lưu App ID và private key trong GitHub Actions Secrets.
3. Cập nhật workflow để tạo App installation token và dùng token đó cho `actions/checkout`/`git push`.
4. Giữ `Require a pull request before merging` cho tất cả actor còn lại.

Nếu repository là tài khoản cá nhân, bypass list của branch protection cổ điển có thể không cho thêm actor. Khi đó dùng **Settings → Rules → Rulesets**, tạo branch ruleset cho `main`, giữ yêu cầu PR và thêm GitHub App vào **Bypass list**. Không xóa protection cũ cho đến khi ruleset mới đã hoạt động và kiểm thử thành công.

> Xóa toàn bộ branch protection sẽ cho phép mọi người có quyền ghi push trực tiếp vào `main`; việc này không phù hợp nếu vẫn muốn bắt buộc review qua Pull Request.

## 7. Triển khai GitHub Pages

Trong repository:

1. Vào **Settings → Pages**.
2. Chọn **Deploy from a branch**.
3. Chọn branch `main` và thư mục `/ (root)`.
4. Lưu và chờ GitHub Pages cấp URL.

Mỗi commit mới lên `main` sẽ kích hoạt triển khai Pages. Workflow đồng bộ dữ liệu không phải workflow deploy Pages; nó chỉ cập nhật JSON để Pages phục vụ phiên bản mới.

## 8. Chạy và kiểm tra local

Không cần cài npm dependency. Dùng một static server để `fetch('./data/hospitals.json')` hoạt động:

```powershell
python -m http.server 8000
```

Mở `http://localhost:8000`.

Kiểm tra JSON bằng Python:

```powershell
python -c "import json; json.load(open('data/hospitals.json', encoding='utf-8')); print('JSON OK')"
```

Chạy parser với một CSV đã tải về:

```powershell
python scripts/sync_sheet.py --csv .\hospitals.csv --output .\data\hospitals.json
```

Kiểm tra thủ công:

- Danh sách hiển thị đúng tổng số bản ghi.
- Số tỉnh/thành và tháng cập nhật thay đổi theo JSON.
- Tìm kiếm có dấu/không dấu và lọc tỉnh hoạt động.
- Gọi hotline, gọi `115`, mở chỉ đường.
- Chuyển sang Bản đồ: CDN tải thành công, marker có đúng `lat/lng`.
- Chuyển sang Dấu hiệu: nội dung hiển thị đúng `K-H-Ẩ-N`.
- Console không có lỗi CSP, lỗi JSON hoặc lỗi JavaScript.

## 9. Bảo mật và nguyên tắc sửa code

1. Không thêm `<script>`, `<style>` hoặc `style="..."` inline vào `index.html`. CSP hiện tại không cho phép inline script/style.
2. Dữ liệu lấy từ JSON phải đi qua `escapeHtml()` trước khi chèn vào HTML.
3. Không đưa PAT, GitHub App private key, webhook secret hoặc API key vào repository.
4. Khi thêm thư viện CDN, phải cập nhật CSP và dùng SRI `integrity`/`crossorigin`.
5. Không dùng Google Maps API key nếu không cần thiết.
6. Không đưa `geocode` hoặc dữ liệu vị trí dư thừa vào JSON; chỉ giữ `lat` và `lng` đã kiểm tra.
7. Không dùng `innerHTML` với dữ liệu chưa escape.
8. Sau mỗi thay đổi lớn, kiểm tra cả CSP, tìm kiếm, định vị, bản đồ và trạng thái lỗi mạng.
9. Không coi `lat/lng` là thông tin đã xác nhận y tế; Admin phải kiểm tra lại tọa độ khi đổi địa chỉ.

## 10. Xử lý sự cố

### E2 đã là `Released` nhưng không có workflow

- Kiểm tra Apps Script → **Triggers** có đúng `onEditReleasedStatus` và event `On edit`.
- Kiểm tra Apps Script → **Executions** để xem lỗi.
- Kiểm tra Script property có đúng tên `GITHUB_ACTIONS_TOKEN`.
- Kiểm tra token còn hạn và có quyền gọi Actions workflow.
- Đảm bảo thay đổi `E2` được thực hiện trực tiếp trên Sheet.

### Workflow báo Sheet chưa Released

Kiểm tra đúng tab, đúng ô `E2` và giá trị chính xác là `Released`. Parser không cho phép workflow phát hành khi trạng thái là `Updating`.

### Workflow không tải được CSV

Kiểm tra Sheet đang được chia sẻ `Anyone with the link → Viewer`, `sheet_gid` trỏ đúng tab và URL export còn truy cập được.

### Workflow không push được `main`

- Kiểm tra `permissions: contents: write` trong workflow.
- Kiểm tra branch protection/ruleset có chặn direct push không.
- Nếu yêu cầu PR vẫn bật, cấu hình bypass có giới hạn cho GitHub App automation hoặc chuyển workflow sang mô hình tạo Pull Request.
- Lỗi PAT thiếu `workflow` khi push file trong `.github/workflows/` là lỗi quyền của token dùng để push code, không phải lỗi parser dữ liệu.

### Bản đồ không hiển thị

- Người dùng phải mở tab Bản đồ để CDN Leaflet được tải.
- Kiểm tra kết nối tới `cdnjs.cloudflare.com` và tile server.
- Kiểm tra `lat`/`lng` có đúng thứ tự và nằm trong phạm vi hợp lệ.
- Nếu CDN bản đồ lỗi, dùng tab Danh sách và gọi hotline/chỉ đường.

### Địa chỉ đổi nhưng marker biến mất

Đây là hành vi có chủ đích. Khi địa chỉ đổi mà Sheet không có tọa độ mới, parser xóa tọa độ cũ để không dẫn người dùng đến vị trí sai. Hãy cập nhật lại cột I theo dạng `lat,lng`.

## 11. Nguyên tắc phát hành dữ liệu

Trước khi chuyển `E2` sang `Released`, Admin nên kiểm tra:

- Tên bệnh viện, loại hình, địa chỉ và tỉnh/thành.
- Hotline còn hoạt động.
- F/G chỉ chứa `Có` hoặc `Không`.
- Cột I đúng thứ tự `lat,lng`.
- Địa chỉ mới đã có tọa độ mới.
- Không có dữ liệu cá nhân hoặc thông tin không nên công khai.

Sau khi phát hành, kiểm tra GitHub Actions, commit JSON và website Pages. Khi có sai sót, chuyển `E2` về `Updating`, sửa dữ liệu, kiểm tra lại và chuyển về `Released` để phát hành phiên bản mới.
