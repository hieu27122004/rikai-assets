# WORKFLOW — Luồng hoạt động Rikai Assets

---

## 1. Tổng quan hệ thống

```
┌──────────────────────────────────────────────────────────────────┐
│                        RIKAI ASSETS                              │
│                                                                  │
│   Admin (group_rikai_asset_admin)   User (group_rikai_asset_user)│
│   ──────────────────────        ──────────────────────       │
│   ✔ Tạo / Sửa / Xóa tài sản        ✔ Xem tài sản               │
│   ✔ Tạo & điều hành kiểm kê        ✔ Single Check (quét QR)    │
│   ✔ Xem Inventory Assets            ✘ Không tạo/sửa được          │
│   ✔ Quét Inventory Scan             ┘                              │
│   ✔ Xem báo cáo tài sản thiếu                                    │
└──────────────────────────────────────────────────────────────────┘
```

Hệ thống gồm **2 luồng chính**:
1. **Single Check** — Quét QR để tra cứu thông tin tài sản (không ghi DB)
2. **Inventory Session** — Phiên kiểm kê chính thức (ghi nhận đầy đủ)

---

## 2. Vòng đời Tài sản

Mỗi tài sản có 2 trạng thái độc lập:

### `state` — Trạng thái hoạt động (tồn tại mãi)
```
                     ┌─────────────┐
            tạo mới  │  available  │  ← Chưa cấp cho ai
                ───▶ │ (Sẵn sàng)  │
                     └──────┬──────┘
                            │ cấp phát cho nhân viên
                            ▼
                     ┌─────────────┐
                     │   in_use    │  ← Nhân viên đang cầm
                     │ (Đang dùng) │
                     └──────┬──────┘
                            │ quản lý yêu cầu trả lại
                            ▼
                     ┌──────────────────┐
                     │ return_requested │  ← Chờ nhân viên trả
                     └──────┬───────────┘
                            │
              ┌─────────────┴──────────────┐
              │ trả thành công             │ cần sửa chữa
              ▼                            ▼
       ┌─────────────┐             ┌─────────────┐
       │  available  │             │ maintenance │  ← Gửi bảo trì
       └─────────────┘             └──────┬──────┘
                                          │ thanh lý
                                          ▼
                                   ┌─────────────┐
                                   │   retired   │  ← Không dùng nữa
                                   │(Đã thanh lý)│    Bị loại khỏi
                                   └─────────────┘    kiểm kê
```

### `inventory_status` — Trạng thái trong phiên kiểm kê (reset mỗi phiên)
```
Phiên bắt đầu → TẤT CẢ tài sản = not_available (chưa xác nhận)
Quét QR tài sản → tài sản đó = available (đã xác nhận có mặt)
Phiên kết thúc → tài sản vẫn not_available → bị liệt vào "Thiếu"
```

---

## 3. Luồng Single Check — Quét tra cứu nhanh

**Mục đích:** Bất kỳ ai muốn xem nhanh thông tin 1 tài sản bằng cách quét QR trên thiết bị. Không ghi gì vào database.

```
┌─────────────────────────────────────────────────────────────────┐
│ BƯỚC 1 — Mở trang                                               │
│                                                                  │
│ User click menu "Single Check"                                   │
│   → Trình duyệt gửi GET /asset/single_check                     │
│   → Server trả về trang HTML + JS camera                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ BƯỚC 2 — Camera bật                                              │
│                                                                  │
│ html5-qrcode khởi động camera sau (facingMode: 'environment')   │
│   → Browser hỏi xin quyền camera → User bấm Allow              │
│   → Camera bắt đầu quét liên tục ở 20 fps                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ BƯỚC 3 — Đọc QR                                                  │
│                                                                  │
│ Đưa QR tài sản vào camera                                       │
│ BarcodeDetector (native Chrome API) hoặc JS decode text          │
│                                                                  │
│ Text nhận được có thể là:                                        │
│   • URL: "https://careers.rikai.technology/...?asset_code=RK01" │
│   • Hoặc text thuần: "RK-001"                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────┴───────────┐
             URL có                    Text thuần
          asset_code=X                (asset_code)
                    │                       │
                    └──────────┬────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│ BƯỚC 4 — Redirect                                                │
│                                                                  │
│ GET /asset/redirect_by_code?asset_code=RK-001                   │
│   → Server tìm rikai.asset theo asset_code                      │
│   ┌─ Tìm thấy ─→ Redirect đến form tài sản trong Odoo (/web#…) │
│   └─ Không thấy ─→ Trả lỗi 404                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Luồng Inventory Session — Kiểm kê định kỳ

**Mục đích:** Xác nhận toàn bộ tài sản của công ty có mặt đầy đủ. Cuối phiên biết được tài sản nào đang thiếu/mất.

### Bước 1 — Admin tạo phiên

```
Admin vào: Rikai Assets → Inventory Check → Inventory Sessions → New
    │
    ▼
Điền tên phiên, vd: "Kiểm kê tháng 3/2026"
    State hiện tại: DRAFT (chưa bắt đầu)
    checked_asset_ids: rỗng
    missing_asset_ids: rỗng
```

### Bước 2 — Bắt đầu phiên (action_start)

```
Admin bấm nút "Start"
    │
    ├─ Kiểm tra: state phải là 'draft'
    │   └─ Nếu không → hiện lỗi "Session already started!"
    │
    ├─ Tìm TẤT CẢ tài sản chưa thanh lý (state != 'retired')
    │   └─ Gán cho mỗi tài sản:
    │       • inventory_status = 'not_available'   ← chưa ai quét
    │       • last_inventory_session_id = phiên này ← đánh dấu thuộc phiên nào
    │
    ├─ Xóa kết quả cũ (nếu chạy lại):
    │   • checked_asset_ids = []
    │   • missing_asset_ids = []
    │
    └─ Cập nhật session:
        • start_date = bây giờ
        • state = 'running'   ← Sẵn sàng để quét
```

### Bước 3 — Quét tài sản

```
┌──────────────────────────────────────────────────────┐
│   Chỉ Admin mới quét được (Inventory Check chỉ hiện với Admin) │
│                                                      │
│  Inventory Check → Inventory Sessions                │
│                   → Inventory Assets (xem tất cả)   │
│                   → Inventory Scan (quét camera)     │
└──────────────────────────────────────────────────────┘
                        │
                        ▼
        Camera bật, đưa QR tài sản vào quét
                        │
                        ▼
    JavaScript gọi API: POST /asset/session_scan_process
    Gửi: { session_id: X, decoded_text: "RK-001" }
                        │
                        ▼
    Server chạy action_scan_qr():
        │
        ├─ Session có đang 'running' không?
        │   └─ Không → trả lỗi "Session not running"
        │
        ├─ Tìm tài sản từ QR text:
        │   • URL có asset_code=X → parse lấy asset_code
        │   • Số nguyên → tìm trực tiếp theo ID
        │   • Text khác → tìm theo asset_code
        │
        ├─ Tài sản không tồn tại?
        │   └─ Trả lỗi "Asset not found"
        │
        ├─ Đã quét rồi? (có trong checked_asset_ids)
        │   └─ Trả lỗi "Asset already scanned"
        │
        └─ OK → Ghi nhận:
            • asset.inventory_status = 'available'
            • checked_asset_ids thêm asset này
            • Trả về { success: True, asset_name: "Laptop Dell XPS" }
                        │
                        ▼
    Trình duyệt hiển thị kết quả (1.5 giây):
        ✔ Thành công: nền xanh + tên tài sản + Beep cao (1800Hz)
        ✘ Lỗi:       nền đỏ  + thông báo lỗi + Beep thấp (600Hz)
                        │
                        ▼
    Tự reset → sẵn sàng quét tài sản tiếp theo
```

### Bước 4 — Kết thúc phiên (action_end)

```
Admin bấm nút "End"
    │
    ├─ Kiểm tra: state phải là 'running'
    │
    ├─ Tìm tài sản THIẾU:
    │   Điều kiện:
    │     • last_inventory_session_id = phiên này (thuộc phiên này)
    │     • inventory_status = 'not_available'     (chưa được quét)
    │   → Đây là danh sách tài sản không có mặt khi kiểm kê
    │
    ├─ Lưu vào missing_asset_ids
    │
    └─ Cập nhật:
        • end_date = bây giờ
        • state = 'done'
                        │
                        ▼
    Admin xem kết quả trên form session:
    ┌──────────────────────────────────────┐
    │ Tab "Checked Assets" (đã quét)   ✔  │
    │ Tab "Missing Assets" (vắng mặt)  ✘  │
    └──────────────────────────────────────┘
```

---

## 5. Luồng sinh QR Code tự động

```
Admin tạo tài sản mới hoặc sửa asset_code
    │
    ▼
Odoo phát hiện asset_code thay đổi (@api.depends)
    │
    ▼
Gọi _compute_qr_code() tự động
    │
    ├─ Không có asset_code → qr_code = False (xóa QR cũ)
    │
    └─ Có asset_code → sinh QR:
        │
        ├─ 1. Tạo QR từ URL:
        │      "https://careers.rikai.technology/tuyen-dung?asset_code=XXX"
        │      (URL này công khai — ai quét cũng xem được)
        │
        ├─ 2. Mở logo.png từ static/src/img/
        │
        ├─ 3. Resize logo = 1/5 kích thước QR
        │
        ├─ 4. Paste logo vào GIỮA QR
        │      (dùng error_correction=H: chịu được che 30% vẫn đọc được)
        │
        └─ 5. Encode PNG → base64 → lưu vào field qr_code
    │
    ▼
QR hiển thị ngay trong form tài sản → Admin in ra → Dán lên thiết bị
```

---

## 6. Luồng truy cập từ Điện thoại

```
CHUẨN BỊ (1 lần, trên PC):
─────────────────────────────────────────────────────────────────
Docker đang chạy Odoo tại localhost:9999
    │
    ▼
Mở PowerShell, chạy:
    & "D:\Dowloads\cloudflared.exe" tunnel --url http://localhost:9999
    │
    ▼
Cloudflare cấp 1 URL HTTPS miễn phí, vd:
    https://suffering-boxing-twiki-reveal.trycloudflare.com
    (URL thay đổi mỗi lần chạy lại)

TRÊN ĐIỆN THOẠI:
─────────────────────────────────────────────────────────────────
Mở Chrome → Vào URL → Đăng nhập Odoo
    │
    ▼
Truy cập scanner:
    Admin: .../asset/session_scan/<session_id>
    User:  Menu → Inventory Scan

    Lý do cần HTTPS: Browser chỉ cho phép dùng camera
    trên HTTPS hoặc localhost — HTTP bị chặn hoàn toàn.
```

> ⚠️ URL Cloudflare **thay đổi mỗi lần** khởi động lại `cloudflared`. Cần copy URL mới và chia sẻ lại với người dùng điện thoại.
