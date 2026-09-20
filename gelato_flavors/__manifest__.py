{
    "name": "Gelato - Flavours",
    "version": "18.0.1.1.0",
    "category": "Website",
    "summary": "Flavour list and a daily switch for what is on the menu today.",
    "description": """
Gelato - Flavours
=================

Gelato is mixed fresh every day and the menu changes with it. This module
gives the shop staff a single screen where each flavour has one button:
**mixing today / off**. Nothing else to click, nothing to save.

The flavour list is not fixed - flavours can be added, renamed or archived
at any time without touching the website code.

Flavours are the single source of truth for the public pages: the website
always shows exactly what is switched on. A flavour that is switched off
cannot be ordered, even by someone who has had the page open since morning.

Every text (name, description, allergens, category) is translatable, so once
another language is added it can be translated in the usual Odoo translation
mode.
""",
    "author": "Michal Varys",
    "website": "https://www.michalvarys.eu",
    "license": "LGPL-3",
    "depends": ["base", "web"],
    "data": [
        "security/groups.xml",
        "security/ir.model.access.csv",
        "views/gelato_flavor_tag_views.xml",
        "views/gelato_flavor_category_views.xml",
        "views/gelato_flavor_views.xml",
        "views/menus.xml",
        "data/gelato_flavor_tag_data.xml",
        "data/gelato_flavor_category_data.xml",
        "data/gelato_flavor_data.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "gelato_flavors/static/src/scss/flavor_board.scss",
            "gelato_flavors/static/src/js/gelato_color_field.js",
        ],
    },
    "installable": True,
    "application": True,
    "auto_install": False,
}
