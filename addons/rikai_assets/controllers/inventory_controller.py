from odoo import http
from odoo.http import request
import urllib.parse


class InventoryScanner(http.Controller):

    @http.route(
        '/asset/session_scan/<int:session_id>',
        type='http',
        auth='user'
    )
    def session_scan(self, session_id, **kwargs):

        session = request.env['rikai.inventory.session'].browse(session_id)

        if not session.exists():
            return request.not_found()

        is_admin = request.env.user.has_group('rikai_assets.group_rikai_asset_admin')
        is_system_admin = request.env.user.has_group('base.group_system')
        if not is_admin and not is_system_admin:
            return request.not_found()

        return request.render(
            'rikai_assets.inventory_session_scan_template',
            {
                'session': session,
                'is_user_mode': False
            }
        )

    @http.route(
        '/asset/user_inventory_scan',
        type='http',
        auth='user'
    )
    def user_inventory_scan(self, **kwargs):

        return request.render(
            'rikai_assets.inventory_session_scan_template',
            {
                'session': False,
                'is_user_mode': True
            }
        )

    @http.route(
        '/asset/session_scan_process',
        type='json',
        auth='user',
        csrf=False
    )
    def session_scan_process(self, session_id=None, decoded_text=None):

        if not decoded_text:
            return {'success': False, 'error': 'QR empty'}

        decoded_text = decoded_text.strip()
        asset = False

        if not session_id:

            if "asset_code=" in decoded_text:
                try:
                    parsed = urllib.parse.urlparse(decoded_text)
                    params = urllib.parse.parse_qs(parsed.query)
                    asset_code = params.get('asset_code', [False])[0]

                    if asset_code:
                        asset = request.env['rikai.asset'].sudo().search([
                            ('asset_code', '=', asset_code)
                        ], limit=1)
                except Exception:
                    pass

            else:
                asset = request.env['rikai.asset'].sudo().search([
                    ('asset_code', '=', decoded_text)
                ], limit=1)

            if not asset:
                return {'success': False, 'error': 'Không tìm thấy tài sản'}

            if asset.state == 'retired':
                return {'success': False, 'error': 'Tài sản đã retired'}

            return {
                'success': True,
                'asset_name': asset.name,
                'state': asset.state
            }

        session = request.env['rikai.inventory.session'].sudo().browse(session_id)

        if not session.exists():
            return {'success': False, 'error': 'Session not found'}

        result = session.action_scan_qr(decoded_text)

        if result.get('error'):
            return {'success': False, 'error': result['error']}

        return result