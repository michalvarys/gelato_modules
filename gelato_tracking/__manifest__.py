{
    "name": "Gelato - Conversion tracking",
    "version": "18.0.1.0.0",
    "category": "Website",
    "summary": "Google Tag Manager and the Meta Pixel, including a completed order event.",
    "description": """
Gelato - Conversion tracking
============================

Adds **Google Tag Manager** and the **Meta Pixel** to the website and tells
them when somebody completes a delivery order.

Both are switched on simply by filling in an ID under
*Website -> Configuration -> Gelato conversion tracking*.

* When a field is empty nothing at all is added to the page and nothing is sent anywhere. There is no extra on/off switch, the ID alone decides.
* When only one of them is filled in, only that one works.

The completed order event is sent at the moment the server has actually
stored the order. It carries the order number, the total, the discount, the
delivery fee and the line items, so it matches up as an ordinary purchase in
GA4 and in Meta Ads Manager.

The order number is sent as the event ID as well, so the conversion is not
counted twice if server-side tracking (the Conversions API) is added later.

Tracking deliberately does not fire inside the website editor, so editing
pages does not pollute the statistics.
""",
    "author": "Michal Varys",
    "website": "https://www.michalvarys.eu",
    "license": "LGPL-3",
    "depends": ["website"],
    "data": [
        "views/res_config_settings_views.xml",
        "views/tracking_templates.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "gelato_tracking/static/src/js/gelato_track.js",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
