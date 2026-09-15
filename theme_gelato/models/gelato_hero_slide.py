from odoo import api, fields, models


class GelatoHeroSlide(models.Model):
    _name = 'gelato.hero.slide'
    _description = 'Gelato Hero Slide'
    _order = 'sequence, id'
    _rec_name = 'display_name'

    name = fields.Char(string='Badge', translate=True)
    headline = fields.Char(string='Headline', translate=True)
    display_name = fields.Char(compute='_compute_display_name', store=True)

    @api.depends('name', 'headline')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name or rec.headline or f'Slide #{rec.id}'
    headline_accent = fields.Char(string='Headline accent', translate=True,
                                  help='Highlighted part of headline')
    subtitle = fields.Text(string='Subtitle', translate=True)
    button_text = fields.Char(string='Button text', translate=True)
    button_url = fields.Char(string='Button URL', default='#')
    image = fields.Image(string='Background image', max_width=1920, max_height=1080)
    image_only = fields.Boolean(
        string='Image only',
        help='Show this slide as a pure image: hides badge, headline, subtitle, '
             'button and the hero logos.')
    hide_overlay = fields.Boolean(
        string='Hide overlay',
        help='Disable the dark gradient overlay for this slide so the image '
             'shows at full brightness.')
    display_time = fields.Float(string='Display time (s)', default=8.0,
                                help='How long this slide stays visible before switching to the next one')
    page_ids = fields.Many2many('website.page', string='Pages',
                                help='Show this slide only on selected pages. '
                                     'Leave empty to show on all pages.')
    page_url = fields.Char(string='Page URL filter',
                           help='Comma-separated page URLs (e.g. /,/v2). '
                                'Used as fallback when Pages field is empty.')
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(default=True)
    website_id = fields.Many2one('website', string='Website', ondelete='cascade')
