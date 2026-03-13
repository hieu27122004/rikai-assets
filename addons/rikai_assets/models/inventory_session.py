from odoo import models, fields
from odoo.exceptions import UserError
import urllib.parse


class RikaiInventorySession(models.Model):
    _name = 'rikai.inventory.session'
    _description = 'Inventory Check Session'
    _inherit = ['mail.thread']

    name = fields.Char(required=True)

    start_date = fields.Datetime()
    end_date = fields.Datetime()

    state = fields.Selection([
        ('draft', 'Draft'),
        ('running', 'Running'),
        ('done', 'Done')
    ], default='draft', tracking=True)

    qr_input = fields.Char(string="Scan QR")

    checked_asset_ids = fields.Many2many(
        'rikai.asset',
        'rikai_inventory_checked_rel',
        'session_id',
        'asset_id'
    )

    missing_asset_ids = fields.Many2many(
        'rikai.asset',
        'rikai_inventory_missing_rel',
        'session_id',
        'asset_id'
    )

    def action_open_scanner(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_url',
            'url': f'/asset/session_scan/{self.id}',
            'target': 'self',
        }

    def action_start(self):
        self.ensure_one()

        if self.state != 'draft':
            raise UserError("Session already started!")

        assets = self.env['rikai.asset'].search([
            ('state', '!=', 'retired')
        ])

        assets.write({
            'inventory_status': 'not_available',
            'last_inventory_session_id': self.id
        })

        self.write({
            'checked_asset_ids': [(5, 0, 0)],
            'missing_asset_ids': [(5, 0, 0)],
            'start_date': fields.Datetime.now(),
            'state': 'running'
        })

    def action_scan_qr(self, decoded_text):
        self.ensure_one()

        if self.state != 'running':
            return {'error': 'Session not running'}

        if not decoded_text:
            return {'error': 'QR empty'}

        decoded_text = decoded_text.strip()
        asset = False

        if "asset_code=" in decoded_text:
            try:
                parsed = urllib.parse.urlparse(decoded_text)
                params = urllib.parse.parse_qs(parsed.query)
                asset_code = params.get('asset_code', [False])[0]

                if asset_code:
                    asset = self.env['rikai.asset'].sudo().search([
                        ('asset_code', '=', asset_code)
                    ], limit=1)
            except Exception:
                pass

        elif decoded_text.isdigit():
            asset = self.env['rikai.asset'].sudo().browse(int(decoded_text))

        else:
            asset = self.env['rikai.asset'].sudo().search([
                ('asset_code', '=', decoded_text)
            ], limit=1)

        if not asset or not asset.exists():
            return {'error': 'Asset not found'}

        if asset in self.checked_asset_ids:
            return {'error': 'Asset already scanned'}

        asset.sudo().write({
            'inventory_status': 'available'
        })

        self.sudo().write({
            'checked_asset_ids': [(4, asset.id)]
        })

        return {
            'success': True,
            'asset_name': asset.name
        }

    def action_end(self):
        self.ensure_one()

        if self.state != 'running':
            raise UserError("Inventory not running!")

        missing_assets = self.env['rikai.asset'].search([
            ('last_inventory_session_id', '=', self.id),
            ('inventory_status', '=', 'not_available')
        ])

        self.write({
            'missing_asset_ids': [(6, 0, missing_assets.ids)],
            'end_date': fields.Datetime.now(),
            'state': 'done'
        })