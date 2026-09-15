from odoo import fields, models


class GelatoGalleryImage(models.Model):
    _name = 'gelato.gallery.image'
    _description = 'Gelato Gallery Image'
    _order = 'sequence, id'

    name = fields.Char(string='Caption', required=True, translate=True)
    image = fields.Image(string='Image', required=True, max_width=1200, max_height=1200)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(default=True)
    website_id = fields.Many2one('website', string='Website', ondelete='cascade')
