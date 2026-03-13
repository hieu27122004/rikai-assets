from odoo import models, fields, api
from odoo.modules.module import get_module_resource
import qrcode
import base64
from io import BytesIO
import os
from PIL import Image
import logging

_logger = logging.getLogger(__name__)


class RikaiAsset(models.Model):
    _name = 'rikai.asset'
    _description = 'Rikai Asset'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    _sql_constraints = [
        ('asset_code_unique', 'unique(asset_code)', 'Asset Code đã tồn tại!')
    ]

    name = fields.Char(required=True, tracking=True)

    asset_code = fields.Char(
        string="Asset Code",
        tracking=True,
        index=True
    )

    description = fields.Text(tracking=True)

    available = fields.Boolean(default=True)
    checked = fields.Boolean(default=False)

    qr_code = fields.Binary(
        compute="_compute_qr_code",
        store=False
    )

    @api.depends('asset_code')
    def _compute_qr_code(self):
        for rec in self:
            if not rec.asset_code:
                rec.qr_code = False
                continue

            qr_data = (
                f"https://careers.rikai.technology/"
                f"tuyen-dung?asset_code={rec.asset_code}"
            )

            qr = qrcode.QRCode(
                version=None,
                error_correction=qrcode.constants.ERROR_CORRECT_H,
                box_size=10,
                border=4,
            )

            qr.add_data(qr_data)
            qr.make(fit=True)

            qr_img = qr.make_image(
                fill_color="black",
                back_color="white"
            ).convert("RGB")

            logo_path = get_module_resource(
                'rikai_assets',
                'static/src/img',
                'logo.png'
            )

            if logo_path and os.path.exists(logo_path):
                try:
                    logo = Image.open(logo_path)

                    qr_width, qr_height = qr_img.size
                    logo_size = qr_width // 5
                    logo = logo.resize(
                        (logo_size, logo_size),
                        Image.LANCZOS
                    )

                    pos = (
                        (qr_width - logo_size) // 2,
                        (qr_height - logo_size) // 2
                    )

                    qr_img.paste(
                        logo,
                        pos,
                        mask=logo if logo.mode == 'RGBA' else None
                    )

                except Exception as e:
                    _logger.error("QR logo error: %s", e)

            buffer = BytesIO()
            qr_img.save(buffer, format="PNG")
            rec.qr_code = base64.b64encode(buffer.getvalue())

    front_image = fields.Image(max_width=1920, max_height=1920)
    back_image = fields.Image(max_width=1920, max_height=1920)
    extra_image = fields.Image(max_width=1920, max_height=1920)

    subcompany = fields.Selection([
        ('mind', 'Rikai Mind'),
        ('technology', 'Rikai Technology'),
    ], tracking=True)

    category_id = fields.Many2one(
        'rikai.asset.category',
        required=True,
        tracking=True
    )

    condition = fields.Selection([
        ('in_use', 'In Use'),
        ('in_storage', 'In Storage'),
        ('disposed', 'Disposed'),
        ('damaged', 'Damaged'),
        ('lost', 'Lost'),
        ('returned_to_customer', 'Returned To Customer'),
        ('other', 'Other'),
    ], tracking=True)

    state = fields.Selection([
        ('available', 'Available'),
        ('in_use', 'In Use'),
        ('return_requested', 'Return Requested'),
        ('maintenance', 'Maintenance'),
        ('retired', 'Retired'),
    ], default='available', tracking=True)

    inventory_status = fields.Selection([
        ('not_available', 'Not Available'),
        ('available', 'Available'),
    ], default='not_available', tracking=True)

    last_inventory_session_id = fields.Many2one(
        'rikai.inventory.session'
    )

    employee_id = fields.Many2one(
        'hr.employee',
        ondelete='set null',
        tracking=True
    )

    leader_id = fields.Many2one(
        'hr.employee',
        tracking=True
    )

    department_id = fields.Many2one(
        'hr.department',
        tracking=True
    )

    usage_ids = fields.One2many(
        'rikai.asset.usage',
        'asset_id'
    )


class RikaiAssetCategory(models.Model):
    _name = 'rikai.asset.category'
    _description = 'Asset Category'
    _rec_name = 'name'

    name = fields.Char(required=True)

    asset_ids = fields.One2many(
        'rikai.asset',
        'category_id'
    )


class RikaiAssetUsage(models.Model):
    _name = 'rikai.asset.usage'
    _description = 'Asset Usage History'

    asset_id = fields.Many2one(
        'rikai.asset',
        required=True,
        ondelete='cascade'
    )

    employee_id = fields.Many2one('hr.employee')
    leader_id = fields.Many2one('hr.employee')
    department_id = fields.Many2one('hr.department')

    start_date = fields.Date()
    end_date = fields.Date()

    state = fields.Selection([
        ('using', 'Using'),
        ('returned', 'Returned')
    ], default='using')

    photo_in = fields.Image(max_width=1920, max_height=1920)
    photo_out = fields.Image(max_width=1920, max_height=1920)