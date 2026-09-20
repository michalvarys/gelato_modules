{
    "name": "Gelato - Delivery",
    "version": "18.0.1.2.0",
    "category": "Website",
    "summary": "The /rozvoz page, delivery orders, thermal boxes, extras and promo codes.",
    "description": """
Gelato - Delivery
=================

The public **/rozvoz** page and the whole delivery workflow in Odoo.

What is managed in Odoo instead of in the website code:

* **Thermal boxes** - volumes, servings, prices and the bullet points on the cards.
* **Extras** - prosecco, bundles, eggnog. An extra can be switched off out of season.
* **Promo codes** - percentage, validity dates and a usage limit. The customer types the code into the form, the website checks it and shows the discount straight away.
* **Orders** - every submitted order becomes a record in Odoo with a status, an address, a delivery slot, the flavours and the calculated price. An email is sent as well.

The flavour list comes from the **Gelato - Flavours** module, so the website
only ever offers what the shop staff switched on.

A bundle stores the price advertised on the leaflet, including the thermal
box, and the surcharge added to the order is derived from it. Changing the
price of a box therefore cannot leave a bundle stuck on an old figure.

Every text is translatable, so once another language is added it can be
translated in the usual Odoo translation mode.
""",
    "author": "Michal Varys",
    "website": "https://www.michalvarys.eu",
    "license": "LGPL-3",
    "depends": ["website", "mail", "sms", "gelato_flavors"],
    "data": [
        "security/ir.model.access.csv",
        "security/ir_rule.xml",
        "data/ir_sequence_data.xml",
        "data/mail_template_data.xml",
        "data/gelato_delivery_box_data.xml",
        "data/gelato_delivery_addon_data.xml",
        "data/gelato_promo_code_data.xml",
        "views/gelato_flavor_board_inherit.xml",
        "data/gelato_delivery_zone_data.xml",
        "views/gelato_delivery_zone_views.xml",
        "views/gelato_delivery_box_views.xml",
        "views/gelato_delivery_addon_views.xml",
        "views/gelato_promo_code_views.xml",
        "views/gelato_customer_views.xml",
        "views/gelato_delivery_order_views.xml",
        "views/res_config_settings_views.xml",
        "views/menus.xml",
        "views/rozvoz_templates.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "gelato_delivery/static/lib/leaflet/leaflet.css",
            "gelato_delivery/static/lib/leaflet/leaflet.js",
            "gelato_delivery/static/src/scss/zone_map.scss",
            "gelato_delivery/static/src/js/zone_map.js",
            "gelato_delivery/static/src/xml/zone_map.xml",
            "gelato_delivery/static/src/scss/board_switch.scss",
            "gelato_delivery/static/src/js/board_switch.js",
            "gelato_delivery/static/src/xml/board_switch.xml",
        ],
        "web.assets_frontend": [
            "gelato_delivery/static/src/scss/rozvoz.scss",
            "gelato_delivery/static/src/js/rozvoz_form.js",
        ],
    },
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "installable": True,
    "application": True,
    "auto_install": False,
}
