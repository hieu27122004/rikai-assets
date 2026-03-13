from odoo import http
from odoo.http import request


class AssetSingleCheck(http.Controller):

    @http.route(
        '/asset/single_check',
        type='http',
        website=True,
        auth='user'
    )
    def single_check_page(self, **kwargs):
        return request.render(
            'rikai_assets.single_check_template'
        )

    @http.route(
        '/asset/redirect_by_code',
        type='http',
        website=True,
        auth='public'  
    )
    def redirect_by_code(self, asset_code=None, **kwargs):

        if not asset_code:
            return request.not_found()

        asset = request.env['rikai.asset'].sudo().search(
            [('asset_code', '=', asset_code)],
            limit=1
        )

        if asset:
            return request.redirect(
                f"/web#id={asset.id}&model=rikai.asset&view_type=form"
            )

        return request.not_found()