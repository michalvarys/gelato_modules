import logging
import werkzeug

from markupsafe import Markup, escape

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class GelatoController(http.Controller):

    @http.route('/theme_gelato/hero_slides', type='json', auth='public', website=True)
    def get_hero_slides(self, page_url=None):
        website = request.website
        domain = [
            ('active', '=', True),
            '|', ('website_id', '=', False), ('website_id', '=', website.id),
        ]
        all_slides = request.env['gelato.hero.slide'].sudo().search(domain, order='sequence, id')
        if page_url:
            page = request.env['website.page'].sudo().search([('url', '=', page_url)], limit=1)
            def _matches(s):
                if s.page_ids:
                    return page and page in s.page_ids
                if s.page_url:
                    urls = [u.strip() for u in s.page_url.split(',')]
                    return page_url in urls
                return True
            slides = all_slides.filtered(_matches)
        else:
            slides = all_slides.filtered(lambda s: not s.page_ids and not s.page_url)
        return [{
            'id': s.id,
            'name': s.name,
            'headline': s.headline,
            'headline_accent': s.headline_accent or '',
            'subtitle': s.subtitle or '',
            'button_text': s.button_text or '',
            'button_url': s.button_url or '#',
            'image_url': f'/web/image/gelato.hero.slide/{s.id}/image' if s.image else '',
            'display_time': s.display_time or 8.0,
            'image_only': s.image_only,
            'hide_overlay': s.hide_overlay,
        } for s in slides]

    @http.route(['/gelato/contact', '/gelato/contact/submit'], type='http',
                auth='public', website=True, methods=['GET', 'POST'], csrf=False)
    def contact_form(self, **kwargs):
        if request.httprequest.method == 'GET':
            return werkzeug.utils.redirect('/#poptavka')
        if kwargs.get('website_url'):
            return werkzeug.utils.redirect('/#poptavka')

        name = kwargs.get('name', '').strip()
        email = kwargs.get('email', '').strip()
        phone = kwargs.get('phone', '').strip()
        event_type = kwargs.get('event-type', '').strip()
        date = kwargs.get('date', '').strip()
        guests = kwargs.get('guests', '').strip()
        message = kwargs.get('message', '').strip()

        if not name or not email:
            return werkzeug.utils.redirect('/?form=error#poptavka')

        recipient = request.env['ir.config_parameter'].sudo().get_param(
            'theme_gelato.inquiry_email', 'poptavka@gelatokv.cz'
        )

        label_style = ('padding:8px 16px 8px 0;border-bottom:1px solid #eee;'
                       'font-weight:bold;white-space:nowrap;width:130px;'
                       'min-width:130px;vertical-align:top;text-align:left;')
        value_style = 'padding:8px;border-bottom:1px solid #eee;vertical-align:top;'
        rows = [
            ('Jméno', escape(name)),
            ('E-mail', Markup(f'<a href="mailto:{escape(email)}">{escape(email)}</a>')),
            ('Telefon', escape(phone or '–')),
            ('Typ akce', escape(event_type or '–')),
            ('Termín', escape(date or '–')),
            ('Počet hostů', escape(guests or '–')),
            ('Zpráva', escape(message or '–')),
        ]
        body_rows = Markup('').join(
            Markup('<tr><th scope="row" style="{ls}">{label}</th>'
                   '<td style="{vs}">{value}</td></tr>').format(
                ls=label_style, vs=value_style, label=label, value=value)
            for label, value in rows
        )
        body = Markup(
            '<h3>Nová poptávka z webu Gelato!</h3>'
            '<table style="border-collapse:collapse;width:100%;max-width:600px;">{rows}</table>'
        ).format(rows=body_rows)
        # Store the contact so the team can follow up later
        try:
            Partner = request.env['res.partner'].sudo()
            partner = Partner.search([('email', '=ilike', email)], limit=1)
            if not partner:
                partner = Partner.create({
                    'name': name,
                    'email': email,
                    'phone': phone or False,
                })
            elif phone and not partner.phone:
                partner.phone = phone
            category = request.env.ref(
                'theme_gelato.partner_category_web_inquiry', raise_if_not_found=False)
            if category and category.id not in partner.category_id.ids:
                partner.write({'category_id': [(4, category.id)]})
            note_lines = ['<b>Poptávka z webu</b>']
            for label, value in (('Typ akce', event_type), ('Termín', date),
                                 ('Počet hostů', guests), ('Zpráva', message)):
                if value:
                    note_lines.append(f'<b>{label}:</b> {escape(value)}')
            partner.message_post(body=Markup('<br/>'.join(note_lines)))
        except Exception:
            _logger.exception("Failed to store gelato inquiry contact")

        # Send from an address the SMTP relay is allowed to use (SPF/DMARC);
        # the customer's address goes to Reply-To so replies still reach them.
        icp = request.env['ir.config_parameter'].sudo()
        mail_server = request.env['ir.mail_server'].sudo().search(
            [('active', '=', True)], order='sequence', limit=1)
        email_from = icp.get_param(
            'theme_gelato.inquiry_from',
            mail_server.smtp_user or request.env.company.email or recipient,
        )
        try:
            request.env['mail.mail'].sudo().create({
                'subject': f'Poptávka catering – {name}',
                'body_html': body,
                'email_from': email_from,
                'reply_to': f'{name} <{email}>',
                'email_to': recipient,
                'auto_delete': True,
            }).send()
        except Exception:
            _logger.exception("Failed to send gelato contact form email")
            return werkzeug.utils.redirect('/?form=error#poptavka')

        return werkzeug.utils.redirect('/?form=ok#poptavka')

    @http.route('/theme_gelato/gallery_images', type='json', auth='public', website=True)
    def get_gallery_images(self):
        website = request.website
        domain = [
            ('active', '=', True),
            '|', ('website_id', '=', False), ('website_id', '=', website.id),
        ]
        images = request.env['gelato.gallery.image'].sudo().search(domain, order='sequence, id')
        return [{
            'id': img.id,
            'name': img.name,
            'image_url': f'/web/image/gelato.gallery.image/{img.id}/image' if img.image else '',
        } for img in images]
