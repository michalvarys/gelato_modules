from odoo import fields, models


class GelatoFlavorTag(models.Model):
    """A short badge shown next to a flavour on the website.

    Vegan, lactose free, no added sugar, new - whatever the shop wants to
    point out. The list is not fixed: tags are created and renamed in Odoo,
    and renaming one changes it on every flavour that carries it.
    """

    _name = "gelato.flavor.tag"
    _description = "Flavour Tag"
    _order = "sequence, name"

    name = fields.Char(
        string="Name",
        required=True,
        translate=True,
        help="Keep it short - it is shown as a small badge, for example "
        "“vegan” or “lactose free”.",
    )
    color = fields.Char(
        string="Colour",
        default="#84c5c3",
        help="Colour of the badge on the website. Use a HEX value, "
        "for example #84c5c3.",
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="An archived tag disappears from the website and from the "
        "flavour form, but stays on the flavours that already carry it.",
    )
    flavor_ids = fields.Many2many(
        comodel_name="gelato.flavor",
        relation="gelato_flavor_tag_rel",
        column1="tag_id",
        column2="flavor_id",
        string="Flavours",
    )
    flavor_count = fields.Integer(
        string="How many flavours",
        compute="_compute_flavor_count",
    )

    _sql_constraints = [
        (
            "name_uniq",
            "unique(name)",
            "A tag with this name already exists.",
        ),
    ]

    def _compute_flavor_count(self):
        for record in self:
            record.flavor_count = len(record.flavor_ids)
