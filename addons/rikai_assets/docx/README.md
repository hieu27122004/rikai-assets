# README — Rikai Assets Module (Odoo 18)

> Module quản lý tài sản nội bộ: QR code, kiểm kê định kỳ, lịch sử sử dụng.

---

## Mục lục

1. [Tổng quan](#tổng-quan)
2. [Cấu trúc thư mục](#cấu-trúc-thư-mục)
3. [Cài đặt & Khởi chạy](#cài-đặt--khởi-chạy)
4. [Models (Dữ liệu)](#models-dữ-liệu)
5. [API Routes](#api-routes)
6. [Phân quyền](#phân-quyền)
7. [Tính năng nổi bật](#tính-năng-nổi-bật)
8. [Lệnh thường dùng](#lệnh-thường-dùng)
9. [Truy cập từ Điện thoại](#truy-cập-từ-điện-thoại)

---

## Tổng quan

Module `rikai_assets` cung cấp hệ thống quản lý tài sản toàn diện với các chức năng:

| Chức năng              | Mô tả                                                                  |
|------------------------|------------------------------------------------------------------------|
| **Quản lý tài sản**    | Tạo, sửa, theo dõi trạng thái từng tài sản (laptop, màn hình, v.v.)  |
| **QR Code tự động**    | Mỗi tài sản có mã QR riêng, nhúng logo Rikai, in ra dán lên thiết bị |
| **Single Check**       | Quét QR để xem nhanh thông tin tài sản (không ghi DB)                 |
| **Inventory Session**  | Phiên kiểm kê chính thức: quét toàn bộ tài sản, báo cáo thiếu/mất   |
| **Lịch sử sử dụng**    | Ghi nhận ai dùng tài sản, từ khi nào đến khi nào                     |
| **Phân quyền**         | Admin (CRUD + kiểm kê) / User (chỉ xem + quét QR)                    |

---

## Cấu trúc thư mục

```
rikai_assets/
│
├── __manifest__.py              ← Khai báo module: tên, version, dependencies, data files
│
├── models/                      ← Định nghĩa cấu trúc dữ liệu (tương đương database tables)
│   ├── asset.py                 ← Model tài sản chính (rikai.asset) + category + usage
│   └── inventory_session.py     ← Model phiên kiểm kê (rikai.inventory.session)
│
├── controllers/                 ← Xử lý HTTP requests (URL routes)
│   ├── inventory_controller.py  ← Routes cho scanner kiểm kê (admin & user mode)
│   └── single_check.py          ← Route quét QR tra cứu tài sản nhanh
│
├── views/                       ← Giao diện Odoo (XML)
│   ├── asset_view.xml                       ← Form + List view tài sản
│   ├── inventory_session_view.xml           ← Form + List view phiên kiểm kê
│   ├── inventory_session_scan_template.xml  ← Trang web camera scanner (kiểm kê)
│   ├── single_check_template.xml            ← Trang web camera scanner (tra cứu)
│   ├── asset_public_template.xml            ← Trang public hiển thị thông tin tài sản
│   └── menu.xml                             ← Cấu hình menu trên thanh điều hướng
│
├── security/
│   ├── security.xml            ← Tạo 2 nhóm quyền: User & Admin
│   └── ir.model.access.csv     ← Phân quyền CRUD từng model theo group
│
└── static/src/img/
    └── logo.png                ← Logo Rikai nhúng vào giữa QR code
```

---

## Cài đặt & Khởi chạy

### Yêu cầu
- Docker Desktop đã cài và đang chạy
- Odoo 18 (cấu hình trong `docker-compose.yml`)

### Khởi chạy lần đầu

```powershell
cd "D:\Rikai Assets"
docker compose up -d
```

Truy cập: `http://localhost:9999`
Đăng nhập → Vào Settings → Activate Developer Mode → Apps → Cài `rikai_assets`

### Sau khi sửa code

```powershell
# Sửa Python hoặc XML view → restart là đủ
docker compose restart

# Sửa XML data, model fields mới, security → cần update module
docker exec rikaiassets-odoo-1 odoo -d <ten_database> -u rikai_assets --stop-after-init
```

---

## Models (Dữ liệu)

### `rikai.asset` — Tài sản

Mỗi record = 1 tài sản vật lý (laptop, màn hình, điện thoại…).

| Field                       | Loại             | Bắt buộc | Mô tả                                               |
|-----------------------------|------------------|:--------:|-----------------------------------------------------|
| `name`                      | Char             | ✔        | Tên tài sản, vd: "Laptop Dell XPS 15"              |
| `asset_code`                | Char (unique)    |          | Mã định danh duy nhất, vd: "RK-001" → sinh QR      |
| `description`               | Text             |          | Ghi chú, mô tả thêm                                |
| `qr_code`                   | Binary (compute) |          | Ảnh QR tự động sinh từ asset_code, nhúng logo       |
| `front_image`               | Image            |          | Ảnh mặt trước thiết bị                             |
| `back_image`                | Image            |          | Ảnh mặt sau thiết bị                               |
| `extra_image`               | Image            |          | Ảnh bổ sung                                        |
| `subcompany`                | Selection        |          | mind / technology                                  |
| `category_id`               | Many2one         | ✔        | Danh mục tài sản (laptop, màn hình…)               |
| `state`                     | Selection        |          | Trạng thái hoạt động (xem bảng bên dưới)           |
| `condition`                 | Selection        |          | Tình trạng vật lý (xem bảng bên dưới)              |
| `inventory_status`          | Selection        |          | not_available / available (dùng trong kiểm kê)     |
| `last_inventory_session_id` | Many2one         |          | Phiên kiểm kê gần nhất tài sản tham gia            |
| `employee_id`               | Many2one         |          | Nhân viên đang sử dụng                             |
| `leader_id`                 | Many2one         |          | Leader phụ trách                                   |
| `department_id`             | Many2one         |          | Phòng ban                                          |
| `usage_ids`                 | One2many         |          | Lịch sử tất cả lần sử dụng                        |

**Giá trị `state`:**

| Giá trị            | Ý nghĩa                                                        |
|--------------------|----------------------------------------------------------------|
| `available`        | Chưa cấp cho ai, sẵn sàng cho mượn                             |
| `in_use`           | Đang được nhân viên sử dụng                                    |
| `return_requested` | Quản lý đã gửi yêu cầu thu hồi, chờ nhân viên trả              |
| `maintenance`      | Đang gửi đi bảo trì hoặc sửa chữa                              |
| `retired`          | Đã thanh lý, không còn sử dụng — **bị loại khỏi kiểm kê**      |

**Giá trị `condition`:**

| Giá trị               | Ý nghĩa               |
|-----------------------|-----------------------|
| `in_use`              | Đang sử dụng tốt      |
| `in_storage`          | Đang cất kho          |
| `disposed`            | Đã hủy                |
| `damaged`             | Bị hỏng               |
| `lost`                | Bị mất                |
| `returned_to_customer`| Đã trả khách hàng     |
| `other`               | Khác                  |

---

### `rikai.asset.category` — Danh mục tài sản

Phân loại tài sản: Laptop, Màn hình, Điện thoại, Bàn phím…

| Field      | Loại    | Mô tả                  |
|------------|---------|------------------------|
| `name`     | Char    | Tên danh mục           |
| `asset_ids`| One2many| Các tài sản trong danh mục |

---

### `rikai.asset.usage` — Lịch sử sử dụng

Mỗi lần tài sản được cấp → 1 record Usage mới. Khi thu hồi → cập nhật record đó.

| Field         | Loại      | Mô tả                         |
|---------------|-----------|-------------------------------|
| `asset_id`    | Many2one  | Tài sản (bắt buộc)            |
| `employee_id` | Many2one  | Nhân viên nhận tài sản        |
| `leader_id`   | Many2one  | Leader phụ trách              |
| `department_id`| Many2one | Phòng ban                     |
| `start_date`  | Date      | Ngày bắt đầu sử dụng          |
| `end_date`    | Date      | Ngày trả lại                  |
| `state`       | Selection | `using` (đang dùng) / `returned` (đã trả) |
| `photo_in`    | Image     | Ảnh tình trạng khi nhận       |
| `photo_out`   | Image     | Ảnh tình trạng khi trả        |

---

### `rikai.inventory.session` — Phiên kiểm kê

Mỗi kỳ kiểm kê (hàng tháng/quý) tạo 1 session. Theo dõi toàn bộ quá trình.

| Field                  | Loại      | Mô tả                                      |
|------------------------|-----------|--------------------------------------------|
| `name`                 | Char      | Tên phiên, vd: "Kiểm kê T3/2026"           |
| `start_date`           | Datetime  | Thời điểm bắt đầu                          |
| `end_date`             | Datetime  | Thời điểm kết thúc                         |
| `state`                | Selection | `draft` → `running` → `done`               |
| `qr_input`             | Char      | Field nhập QR thủ công (optional)          |
| `checked_asset_ids`    | Many2many | Danh sách tài sản đã quét xác nhận         |
| `missing_asset_ids`    | Many2many | Danh sách tài sản vắng mặt (khi kết thúc)  |

---

## API Routes

Các URL mà trình duyệt/điện thoại gọi đến:

| Method | Route                              | Auth         | Mô tả                                              |
|--------|------------------------------------|:------------:|----------------------------------------------------|
| GET    | `/asset/single_check`              | user         | Trang camera quét QR tra cứu tài sản               |
| GET    | `/asset/redirect_by_code`          | **public**   | Nhận asset_code → redirect về form tài sản         |
| GET    | `/asset/session_scan/<id>`         | admin/system | Trang camera quét kiểm kê theo session cụ thể      |
| GET    | `/asset/user_inventory_scan`       | user         | Trang camera quét kiểm kê (user mode, không session)|
| POST   | `/asset/session_scan_process`      | user         | JSON API: nhận QR text → xử lý → trả kết quả      |

> `auth='public'` nghĩa là **không cần đăng nhập** — dùng cho QR dán lên tài sản vật lý để ai cũng quét được.

---

## Phân quyền

### Groups

| Group                      | Tên hiển thị      | Kế thừa từ               |
|----------------------------|-------------------|--------------------------|
| `group_rikai_asset_user`   | Rikai Asset User  | —                        |
| `group_rikai_asset_admin`  | Rikai Asset Admin | `group_rikai_asset_user` |

Admin **tự động có** tất cả quyền của User (nhờ `implied_ids`).

### Quyền truy cập

| Model                      | User  | Admin |
|----------------------------|:-----:|:-----:|
| `rikai.asset`              | Read  | CRUD  |
| `rikai.asset.category`     | Read  | CRUD  |
| `rikai.asset.usage`        | Read  | CRUD  |
| `rikai.inventory.session`  | Read  | CRUD  |

### Menu hiển thị theo group

| Menu                       | User | Admin |
|----------------------------|:----:|:-----:|
| Assets                     | ✔    | ✔     |
| Single Check               | ✔    | ✔     |
| Inventory Check            | ✘    | ✔     |
| └─ Inventory Sessions       | ✘    | ✔     |
| └─ Inventory Assets         | ✘    | ✔     |
| └─ Inventory Scan           | ✘    | ✔     |

> **Lưu ý:** Field `inventory_status` trong form tài sản chỉ hiển thị với Admin.

---

## Tính năng nổi bật

### 1. QR Code tự động với logo Rikai
- Điền `asset_code` → QR tự sinh ngay lập tức (compute field)
- QR nhúng logo Rikai vào giữa, error correction H (chịu che 30%)
- URL trong QR trỏ về trang public → ai cũng quét được dù không có tài khoản Odoo

### 2. Scanner mobile-friendly
- Camera tự dùng mặt sau (`facingMode: 'environment'`)
- Ô quét tự co giãn theo màn hình (85% chiều rộng, min 280px, max 480px)
- Chạy 20 fps + native BarcodeDetector API → phát hiện QR cực nhanh
- Tiếng beep xác nhận ngay lần quét đầu tiên (không cần touch lần 2)

### 3. Inventory Session thông minh
- `action_start()` reset toàn bộ `inventory_status` → `not_available` trước khi quét
- Tự động tính `missing_asset_ids` khi kết thúc (không cần làm thủ công)
- QR parse linh hoạt: URL đầy đủ / số ID / mã asset_code thuần đều nhận

---

## Lệnh thường dùng

```powershell
# ── Docker ──────────────────────────────────────────
docker compose up -d              # Khởi chạy tất cả container
docker compose restart            # Restart (giữ data)
docker compose down               # Dừng tất cả
docker compose logs -f odoo       # Xem log realtime

# ── Update module ────────────────────────────────────
docker exec rikaiassets-odoo-1 odoo -d <db> -u rikai_assets --stop-after-init

# ── Tunnel điện thoại ───────────────────────────────
& "D:\Dowloads\cloudflared.exe" tunnel --url http://localhost:9999
```

---

## Truy cập từ Điện thoại

Cần Cloudflare Tunnel để có HTTPS (browser chặn camera nếu dùng HTTP):

```
[PC] cloudflared → https://xxx.trycloudflare.com → localhost:9999 (Odoo)
[Điện thoại] mở https://xxx.trycloudflare.com/web → đăng nhập → dùng bình thường
```

> ⚠️ URL thay đổi mỗi lần khởi động lại cloudflared.
