# CODE_GUIDE — Giải thích chi tiết code Rikai Assets

> Tài liệu này giải thích từng phần code quan trọng trong module, bao gồm lý do thiết kế, cách hoạt động, và các khái niệm Odoo cần biết.

---

## Mục lục

1. [models/asset.py](#1-modelsassetpy)
2. [models/inventory_session.py](#2-modelsinventory_sessionpy)
3. [controllers/inventory_controller.py](#3-controllersinventory_controllerpy)
4. [controllers/single_check.py](#4-controllerssingle_checkpy)
5. [JavaScript trong Templates](#5-javascript-trong-templates)
6. [security/security.xml](#6-securitysecurityxml)
7. [security/ir.model.access.csv](#7-securityirmodelacccesscsv)
8. [views/menu.xml](#8-viewsmenuxml)

---

## 1. `models/asset.py`

### Khai báo Model

```python
class RikaiAsset(models.Model):
    _name = 'rikai.asset'
    _description = 'Rikai Asset'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'
```

**Giải thích từng dòng:**

- `_name = 'rikai.asset'`
  Tên kỹ thuật của model. Odoo dùng tên này ở khắp nơi: trong XML (`model="rikai.asset"`), trong Python (`self.env['rikai.asset']`), và tạo table PostgreSQL tên `rikai_asset` (dấu chấm → dấu gạch dưới).

- `_inherit = ['mail.thread', 'mail.activity.mixin']`
  Kế thừa 2 mixin sẵn có của Odoo:
  - `mail.thread`: Thêm **chatter** (khung tin nhắn ở dưới form). Khi field có `tracking=True`, Odoo tự ghi log mỗi lần thay đổi. Ví dụ: đổi `state` từ `available` → `in_use` → chatter tự thêm dòng "State: Available → In Use".
  - `mail.activity.mixin`: Cho phép tạo **activity** (nhắc việc) gắn vào tài sản, vd: "Nhắc bảo trì sau 6 tháng".

- `_order = 'name'`
  Khi query không có `ORDER BY`, Odoo tự sort theo `name`. Quan trọng vì ảnh hưởng thứ tự hiển thị trong list view.

---

### SQL Constraint — Bảo đảm asset_code không trùng

```python
_sql_constraints = [
    ('asset_code_unique', 'unique(asset_code)', 'Asset Code phải là duy nhất!')
]
```

**Tại sao dùng SQL constraint thay vì check trong Python?**

Nếu check trong Python (`@api.constrains`), có thể xảy ra race condition: 2 user tạo cùng lúc cùng asset_code → cả 2 đều pass check → database có 2 record trùng.

SQL constraint được tạo trong PostgreSQL (`CREATE UNIQUE INDEX`), nên database tự enforce ở tầng thấp nhất — không thể có trùng dù thế nào.

---

### `_compute_qr_code` — Sinh QR Code tự động

```python
@api.depends('asset_code')
def _compute_qr_code(self):
    logo_path = get_module_resource('rikai_assets', 'static/src/img', 'logo.png')

    for rec in self:
        if not rec.asset_code:
            rec.qr_code = False
            continue

        # Bước 1: Tạo nội dung QR
        qr_content = f"https://careers.rikai.technology/tuyen-dung?asset_code={rec.asset_code}"

        # Bước 2: Tạo QR với error correction cao nhất
        qr = qrcode.QRCode(
            error_correction=qrcode.constants.ERROR_CORRECT_H,  # H = 30% che vẫn đọc được
            box_size=10,
            border=2
        )
        qr.add_data(qr_content)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")

        # Bước 3: Nhúng logo vào giữa QR
        logo = Image.open(logo_path).convert("RGBA")
        qr_size = qr_img.size[0]
        logo_size = qr_size // 5   # Logo = 1/5 kích thước QR
        logo = logo.resize((logo_size, logo_size), Image.LANCZOS)

        # Tính vị trí dán logo (căn giữa)
        pos = ((qr_size - logo_size) // 2, (qr_size - logo_size) // 2)
        qr_img.paste(logo, pos, logo)   # Dùng logo làm mask nếu có nền trong suốt

        # Bước 4: Encode sang base64
        buffer = BytesIO()
        qr_img.save(buffer, format='PNG')
        rec.qr_code = base64.b64encode(buffer.getvalue())
```

**Tại sao URL trỏ về careers.rikai.technology?**
QR được dán lên tài sản vật lý (laptop, màn hình…). Khi nhân viên hoặc khách quét QR, họ không nhất thiết đang đăng nhập Odoo. URL public này cho phép xem thông tin tài sản mà không cần tài khoản. Route `/asset/redirect_by_code` (auth=public) từ URL này sẽ tìm tài sản và redirect về form Odoo.

**Error correction `H` là gì?**
QR code có cơ chế tự sửa lỗi. Level H = 30%: kể cả khi 30% QR bị che hoặc bẩn, scanner vẫn đọc được. Cần thiết vì logo Rikai che giữa QR.

---

### Các Field quan trọng — Giải thích sâu

#### `state` — Trạng thái hoạt động

```python
state = fields.Selection([
    ('available',        'Available'),
    ('in_use',           'In Use'),
    ('return_requested', 'Return Requested'),
    ('maintenance',      'Maintenance'),
    ('retired',          'Retired'),
], default='available', tracking=True)
```

`tracking=True` → mỗi lần state thay đổi, Odoo ghi vào chatter tự động.

**Luồng state điển hình:**
```
available → in_use          (cấp phát cho nhân viên)
in_use → return_requested   (gửi yêu cầu trả)
return_requested → available (nhân viên đã trả lại)
any → maintenance           (gửi bảo trì)
maintenance → available     (bảo trì xong)
any → retired               (thanh lý, không dùng nữa)
```

#### `inventory_status` — Trạng thái trong phiên kiểm kê

```python
inventory_status = fields.Selection([
    ('not_available', 'Not Available'),
    ('available',     'Available'),
], default='not_available')
```

Field này **độc lập hoàn toàn** với `state`. Mục đích duy nhất: theo dõi trong 1 phiên kiểm kê tài sản đó có được quét xác nhận chưa.

- Phiên bắt đầu → TẤT CẢ tài sản `inventory_status = not_available`
- Quét được tài sản → `inventory_status = available`
- Phiên kết thúc → tài sản vẫn `not_available` = thiếu/mất

#### `last_inventory_session_id` — Phiên kiểm kê gần nhất

```python
last_inventory_session_id = fields.Many2one('rikai.inventory.session')
```

Được gán khi phiên `action_start()` chạy. Dùng để khi kết thúc phiên, tìm chính xác tài sản thuộc phiên này mà chưa quét:

```python
# Không gán last_inventory_session_id → không thể lọc đúng tài sản thiếu
missing = search([
    ('last_inventory_session_id', '=', self.id),  # Thuộc phiên này
    ('inventory_status', '=', 'not_available')    # Chưa quét
])
```

---

### Class `RikaiAssetUsage` — Lịch sử sử dụng

```python
class RikaiAssetUsage(models.Model):
    _name = 'rikai.asset.usage'
    _order = 'start_date desc'   # Mới nhất hiển thị trước
```

Mỗi lần cấp phát tạo 1 record. Vì là One2many từ `rikai.asset`, có thể xem toàn bộ lịch sử trong tab của form tài sản.

```python
state = fields.Selection([
    ('using',     'Using'),    # Đang sử dụng
    ('returned',  'Returned'), # Đã trả lại
])
```

---

## 2. `models/inventory_session.py`

### Vòng đời Session

```python
state = fields.Selection([
    ('draft',   'Draft'),    # Vừa tạo, chưa bắt đầu
    ('running', 'Running'),  # Đang quét
    ('done',    'Done'),     # Đã kết thúc
], default='draft')
```

Chỉ đi 1 chiều: `draft → running → done`. Không thể quay lại.

---

### `action_start()` — Bắt đầu phiên

```python
def action_start(self):
    # Bảo vệ: không cho start nếu không phải draft
    if self.state != 'draft':
        raise UserError("Phiên đã được bắt đầu!")

    # Tìm TẤT CẢ tài sản còn hoạt động (trừ retired vì đã thanh lý)
    assets = self.env['rikai.asset'].search([('state', '!=', 'retired')])

    # Reset inventory_status về not_available cho tất cả
    # Đây là "màn trống" trước khi kiểm kê - ai chưa quét = chưa xác nhận
    assets.write({
        'inventory_status': 'not_available',
        'last_inventory_session_id': self.id
        # Gán session_id để sau khi kết thúc biết tài sản nào thuộc phiên này
    })

    # Xóa data cũ (nếu reset phiên để chạy lại)
    self.write({
        'checked_asset_ids': [(5, 0, 0)],  # Command (5) = xóa toàn bộ many2many
        'missing_asset_ids': [(5, 0, 0)],
        'start_date': fields.Datetime.now(),
        'state': 'running'
    })
```

**Many2many commands là gì?**
Odoo dùng list các tuple đặc biệt để thao tác many2many:

| Command         | Ý nghĩa                       |
|-----------------|-------------------------------|
| `(4, id)`       | Thêm 1 record vào danh sách  |
| `(5, 0, 0)`     | Xóa toàn bộ many2many         |
| `(6, 0, [ids])` | Gán lại toàn bộ = ids mới    |

---

### `action_scan_qr(decoded_text)` — Xử lý 1 lần quét

```python
def action_scan_qr(self, decoded_text):
    """Nhận text từ QR, xác định tài sản, ghi nhận vào session."""

    if self.state != 'running':
        return {'error': 'Session không đang chạy'}

    asset = None

    # Phân tích loại QR text nhận được
    if 'asset_code=' in decoded_text:
        # Trường hợp 1: URL đầy đủ từ QR
        # "https://careers.rikai.technology/tuyen-dung?asset_code=RK-001"
        parsed = urllib.parse.urlparse(decoded_text)
        params = urllib.parse.parse_qs(parsed.query)
        code = params.get('asset_code', [None])[0]
        if code:
            asset = self.env['rikai.asset'].search([('asset_code', '=', code)], limit=1)

    elif decoded_text.strip().isdigit():
        # Trường hợp 2: QR chứa ID số nguyên
        # Ít gặp nhưng cần handle để tương thích QR cũ
        asset = self.env['rikai.asset'].browse(int(decoded_text.strip()))
        if not asset.exists():
            asset = None

    else:
        # Trường hợp 3: asset_code thuần (không có URL)
        # Ví dụ: "RK-001"
        asset = self.env['rikai.asset'].search([('asset_code', '=', decoded_text.strip())], limit=1)

    # Xử lý kết quả
    if not asset:
        return {'error': f'Không tìm thấy tài sản: {decoded_text}'}

    if asset in self.checked_asset_ids:
        return {
            'error': 'already_scanned',
            'asset_name': asset.name,
            'message': f'{asset.name} đã được quét trước đó!'
        }

    # Ghi nhận: đánh dấu tài sản đã có mặt
    asset.write({'inventory_status': 'available'})
    self.write({'checked_asset_ids': [(4, asset.id)]})

    return {
        'success': True,
        'asset_name': asset.name,
        'asset_code': asset.asset_code,
        'state': asset.state,
    }
```

---

### `action_end()` — Kết thúc phiên

```python
def action_end(self):
    if self.state != 'running':
        raise UserError("Phiên chưa đang chạy!")

    # Tài sản THIẾU = thuộc phiên này + chưa quét
    # (last_inventory_session_id đảm bảo chỉ lấy tài sản của phiên này,
    #  không lấy tài sản từ phiên trước hoặc tài sản mới thêm sau)
    missing = self.env['rikai.asset'].search([
        ('last_inventory_session_id', '=', self.id),
        ('inventory_status', '=', 'not_available'),
    ])

    self.write({
        'missing_asset_ids': [(6, 0, missing.ids)],  # Command (6) = gán lại toàn bộ
        'end_date': fields.Datetime.now(),
        'state': 'done'
    })
```

---

## 3. `controllers/inventory_controller.py`

### Khái niệm Controller trong Odoo

Controller = class Python định nghĩa URL routes. Browser gọi URL → Odoo route → function Python xử lý → trả về HTML hoặc JSON.

```python
from odoo import http
from odoo.http import request

class InventoryScanner(http.Controller):
    # Mỗi method được map với 1 URL bằng @http.route
```

---

### `session_scan()` — Trang scanner admin

```python
@http.route(
    '/asset/session_scan/<int:session_id>',
    type='http',       # Trả về HTML
    auth='user',       # Phải đăng nhập
    website=True       # Dùng website context
)
def session_scan(self, session_id, **kwargs):

    # browse() tìm record theo ID, KHÔNG raise lỗi nếu không có
    # → phải check exists() riêng
    session = request.env['rikai.inventory.session'].browse(session_id)
    if not session.exists():
        return request.not_found()  # HTTP 404

    # Kiểm tra quyền 2 tầng:
    # Tầng 1: Admin của module rikai_assets
    is_admin = request.env.user.has_group('rikai_assets.group_rikai_asset_admin')
    # Tầng 2: System Administrator của Odoo (tài khoản admin gốc)
    # → Cần thiết vì admin Odoo có thể chưa được thêm vào group_rikai_asset_admin
    is_system = request.env.user.has_group('base.group_system')

    if not is_admin and not is_system:
        return request.not_found()  # Trả 404 thay vì 403 để không lộ URL

    return request.render(
        'rikai_assets.inventory_session_scan_template',
        {
            'session': session,     # Truyền session vào template để hiển thị tên/state
            'is_user_mode': False,  # False = admin mode (có session_id)
        }
    )
```

---

### `session_scan_process()` — JSON API xử lý QR

```python
@http.route(
    '/asset/session_scan_process',
    type='json',    # Nhận và trả JSON (không cần parse thủ công)
    auth='user',
    csrf=False,     # Tắt CSRF vì JS gọi trực tiếp (không qua form HTML)
    methods=['POST']
)
def session_scan_process(self, session_id=None, decoded_text=None, **kwargs):

    if not decoded_text:
        return {'error': 'Không có dữ liệu QR'}

    # CHẾ ĐỘ USER (không có session_id):
    # Chỉ tra cứu thông tin tài sản, KHÔNG ghi nhận vào database
    if not session_id:
        asset = request.env['rikai.asset'].sudo().search(
            [('asset_code', '=', decoded_text.strip())], limit=1
        )
        if not asset:
            return {'error': 'Không tìm thấy tài sản'}
        return {
            'success': True,
            'asset_name': asset.name,
            'state': asset.state,
            'employee': asset.employee_id.name or 'Chưa cấp',
        }

    # CHẾ ĐỘ ADMIN (có session_id):
    # Ghi nhận vào session → cập nhật inventory_status
    session = request.env['rikai.inventory.session'].browse(int(session_id))
    if not session.exists():
        return {'error': 'Session không tồn tại'}

    return session.action_scan_qr(decoded_text)
```

---

## 4. `controllers/single_check.py`

### `single_check_page()` — Trang quét tra cứu

```python
@http.route('/asset/single_check', type='http', auth='user', website=True)
def single_check_page(self, **kwargs):
    return request.render('rikai_assets.single_check_template')
    # Không truyền data → template tự fetch qua JS/redirect
```

### `redirect_by_code()` — Redirect theo asset_code

```python
@http.route('/asset/redirect_by_code', type='http', auth='public', website=True)
def redirect_by_code(self, asset_code=None, **kwargs):
```

**`auth='public'`** = Không cần đăng nhập. Quan trọng vì:
- QR được dán lên tài sản vật lý trong văn phòng
- Bất kỳ ai cầm điện thoại quét QR đều cần xem được thông tin
- Nếu đặt `auth='user'`, người chưa đăng nhập sẽ bị redirect về login → UX kém

```python
    if not asset_code:
        return request.not_found()

    # sudo() = bỏ qua access control (cần vì user là public, không có quyền read)
    asset = request.env['rikai.asset'].sudo().search(
        [('asset_code', '=', asset_code)], limit=1
    )

    if asset:
        # Redirect về Odoo web client với hash parameters
        # Odoo Web Client đọc hash URL (#...) để mở đúng record
        return request.redirect(
            f"/web#id={asset.id}&model=rikai.asset&view_type=form"
        )

    return request.not_found()
```

---

## 5. JavaScript trong Templates

### Vấn đề Autoplay Audio và giải pháp

**Vấn đề:** Các trình duyệt hiện đại (Chrome, Safari) chặn âm thanh phát tự động cho đến khi người dùng có tương tác (click, touch). Nếu trang load camera thẳng mà không có click → lần quét đầu tiên không có tiếng beep.

**Giải pháp:** Tạo `AudioContext` sẵn và unlock nó ngay khi người dùng chạm màn hình lần đầu (kể cả khi bấm "Allow" cho camera là đủ):

```javascript
var audioCtx = null;

function getAudioCtx() {
    // Tạo 1 lần duy nhất trong suốt vòng đời trang
    if (!audioCtx) {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    }
    // Resume nếu bị tạm dừng (xảy ra khi tab bị ẩn)
    if (audioCtx.state === 'suspended') {
        audioCtx.resume();
    }
    return audioCtx;
}

function unlockAudio() {
    // Tạo và ngay lập tức resume → "unlock" cho browser
    var ctx = getAudioCtx();
    // Tạo oscillator câm để kích hoạt context
    var buf = ctx.createBuffer(1, 1, 22050);
    var src = ctx.createBufferSource();
    src.buffer = buf;
    src.connect(ctx.destination);
    src.start(0);
}

// Lắng nghe tương tác đầu tiên, { once: true } = chỉ chạy 1 lần
document.addEventListener('touchstart', unlockAudio, { once: true });
document.addEventListener('mousedown',  unlockAudio, { once: true });
```

---

### Sinh tiếng Beep bằng Web Audio API

```javascript
function playBeep(isSuccess) {
    var ctx = getAudioCtx();

    // Oscillator = bộ tạo sóng âm
    var osc = ctx.createOscillator();
    // Gain Node = điều chỉnh âm lượng theo thời gian
    var gain = ctx.createGain();

    // Nối: oscillator → gain → loa
    osc.connect(gain);
    gain.connect(ctx.destination);

    // Square wave nghe sắc như máy quét cửa hàng
    osc.type = 'square';

    // Tần số:
    // 1800Hz = nốt cao → âm thanh thành công, dễ nghe
    // 400Hz  = nốt thấp → âm thanh lỗi, cảnh báo
    osc.frequency.value = isSuccess ? 1800 : 400;

    var now = ctx.currentTime;
    // Bắt đầu ở âm lượng 0.25 (25%)
    gain.gain.setValueAtTime(0.25, now);
    // Giảm exponential về gần 0 sau 0.08 giây → tạo cảm giác "sắc", không kéo dài
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.08);

    osc.start(now);
    osc.stop(now + 0.08);  // Dừng sau 80ms
}
```

**Tại sao dùng `exponentialRamp` thay vì `linearRamp`?**
Tai người cảm nhận âm lượng theo logarithm, không tuyến tính. `exponentialRamp` nghe tự nhiên hơn (giống thực tế), `linearRamp` nghe cứng và nhân tạo.

---

### Cấu hình QR Scanner

```javascript
function startScanner() {
    html5QrCode = new Html5Qrcode('reader');  // 'reader' = id của div chứa camera

    // Tính ô quét tỉ lệ với màn hình
    // 85% chiều rộng, nhưng giới hạn tối thiểu 280px và tối đa 480px
    // → Hoạt động tốt cả trên điện thoại nhỏ (320px) lẫn tablet (768px+)
    var boxSize = Math.min(480, Math.max(280, Math.round(window.innerWidth * 0.85)));

    html5QrCode.start(
        { facingMode: 'environment' },     // Camera SAU ('user' = camera trước)
        {
            fps: 20,          // 20 frame/giây → phát hiện QR 2x nhanh hơn mặc định 10fps
            qrbox: boxSize,   // Kích thước ô quét (pixel)
            experimentalFeatures: {
                useBarCodeDetectorIfSupported: true
                // Native BarcodeDetector API của Chrome/Android:
                // - Chạy ở tầng C++ thay vì JavaScript → nhanh hơn 3-5x
                // - Tự động fallback về JS nếu browser không hỗ trợ (Safari iOS)
            }
        },
        onScanSuccess,    // Callback khi đọc được QR
        onScanFailure     // Callback khi không tìm thấy QR (gọi liên tục)
    );
}
```

---

### Luồng xử lý sau khi quét

```javascript
var scanned = false;  // Flag ngăn xử lý nhiều lần cùng 1 lần quét

function onScanSuccess(decodedText) {
    if (scanned) return;  // Bỏ qua nếu đang xử lý
    scanned = true;

    // Gọi API backend
    fetch('/asset/session_scan_process', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify({
            jsonrpc: '2.0',
            method: 'call',
            params: {
                session_id: SESSION_ID,    // Biến inject từ Odoo template
                decoded_text: decodedText
            }
        })
    })
    .then(r => r.json())
    .then(data => {
        var result = data.result;

        if (result.success) {
            playBeep(true);                           // Beep cao
            showMessage(result.asset_name, 'green');  // Hiện tên màu xanh
        } else {
            playBeep(false);                          // Beep thấp
            showMessage(result.error, 'red');         // Hiện lỗi màu đỏ
        }

        // Sau 1.5 giây → reset để quét tài sản tiếp theo
        setTimeout(() => {
            scanned = false;
            hideMessage();
        }, 1500);
    });
}
```

---

## 6. `security/security.xml`

```xml
<odoo>
    <!-- Group 1: User thường -->
    <record id="group_rikai_asset_user" model="res.groups">
        <field name="name">Rikai Asset User</field>
        <field name="category_id" ref="base.module_category_hidden"/>
    </record>

    <!-- Group 2: Admin - TỰ ĐỘNG kế thừa quyền User -->
    <record id="group_rikai_asset_admin" model="res.groups">
        <field name="name">Rikai Asset Admin</field>
        <field name="category_id" ref="base.module_category_hidden"/>
        <field name="implied_ids" eval="[(4, ref('group_rikai_asset_user'))]"/>
        <!-- implied_ids + (4, id) = "Admin implies User"
             Odoo tự động thêm User vào ai được gán Admin.
             Không cần gán 2 group riêng lẻ. -->
    </record>
</odoo>
```

**`base.module_category_hidden`** — Ẩn group khỏi category list trong Settings UI. Vì đây là group nội bộ của module, không cần user thấy trong danh sách category.

---

## 7. `security/ir.model.access.csv`

File CSV định nghĩa quyền CRUD cho từng model theo từng group.

```csv
id, name, model_id:id, group_id:id, perm_read, perm_write, perm_create, perm_unlink
```

| Cột           | Ý nghĩa                            |
|---------------|------------------------------------||
| `id`          | External ID duy nhất trong module  |
| `name`        | Tên mô tả (không ảnh hưởng logic) |
| `model_id:id` | External ID của model              |
| `group_id:id` | Group được áp dụng quyền         |
| `perm_read`   | 1 = có quyền đọc                   |
| `perm_write`  | 1 = có quyền sửa                   |
| `perm_create` | 1 = có quyền tạo mới               |
| `perm_unlink` | 1 = có quyền xóa                   |

**Ví dụ dòng User:**
```csv
access_rikai_asset_user, rikai.asset.user, model_rikai_asset, rikai_assets.group_rikai_asset_user, 1, 0, 0, 0
```
→ User chỉ đọc (`read=1`), không sửa/tạo/xóa được.

**Ví dụ dòng Admin:**
```csv
access_rikai_asset_admin, rikai.asset.admin, model_rikai_asset, rikai_assets.group_rikai_asset_admin, 1, 1, 1, 1
```
→ Admin có đầy đủ quyền.

---

## 8. `views/menu.xml`

Định nghĩa cây menu trong thanh điều hướng của Odoo.

```xml
<!-- Root menu (không có parent = top-level) -->
<menuitem id="menu_rikai_root"
          name="Rikai Assets"
          sequence="10"/>

<!-- Assets: cả User và Admin đều thấy -->
<menuitem id="menu_rikai_asset"
          name="Assets"
          parent="menu_rikai_root"
          action="action_rikai_asset"
          sequence="1"
          groups="rikai_assets.group_rikai_asset_user"/>

<!-- Single Check: cả User và Admin đều thấy -->
<menuitem id="menu_rikai_single_check"
          name="Single Check"
          parent="menu_rikai_root"
          action="action_single_check_url"   ← action_url redirect đến /asset/single_check
          sequence="2"
          groups="rikai_assets.group_rikai_asset_user"/>

<!-- Inventory Check: CHỈ Admin thấy (submenu container) -->
<menuitem id="menu_inventory_root"
          name="Inventory Check"
          parent="menu_rikai_root"
          sequence="3"
          groups="rikai_assets.group_rikai_asset_admin"/>

<!-- Inventory Sessions: quản lý phiên kiểm kê -->
<menuitem id="menu_inventory_session"
          name="Inventory Sessions"
          parent="menu_inventory_root"
          action="action_inventory_session"
          sequence="1"
          groups="rikai_assets.group_rikai_asset_admin"/>

<!-- Inventory Assets: xem danh sách tất cả tài sản + inventory_status -->
<menuitem id="menu_inventory_assets"
          name="Inventory Assets"
          parent="menu_inventory_root"
          action="action_inventory_assets"
          sequence="2"
          groups="rikai_assets.group_rikai_asset_admin"/>

<!-- Inventory Scan: mở camera quét QR (chỉ Admin) -->
<menuitem id="menu_inventory_user_scan"
          name="Inventory Scan"
          parent="menu_inventory_root"
          action="action_inventory_user_scan_url"
          sequence="3"
          groups="rikai_assets.group_rikai_asset_admin"/>
```

**Kết quả trên thanh menu:**
```
Rikai Assets
├── Assets                    [User + Admin]
├── Single Check              [User + Admin]
└── Inventory Check           [Admin only]
    ├── Inventory Sessions    ← Quản lý phiên kiểm kê
    ├── Inventory Assets      ← Xem tất cả tài sản + inventory_status
    └── Inventory Scan        ← Mở camera quét QR
```

> **Lưu ý:** Field `inventory_status` trong form tài sản (asset_view.xml) được đặt `groups="rikai_assets.group_rikai_asset_admin"` → User xem form tài sản sẽ không thấy cột này.
