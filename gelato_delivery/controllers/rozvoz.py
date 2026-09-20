import re

import werkzeug.exceptions

from odoo import _, fields, http
from odoo.http import request

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _sitemap_rozvoz(env, rule, qs):
    """Keep /rozvoz out of the sitemap of websites it does not belong to."""
    if not env["website"].get_current_website().gelato_delivery_site:
        return []
    return None


class GelatoRozvoz(http.Controller):
    """The public delivery page.

    An anonymous visitor has no rights on the delivery models, so everything
    is read and written through sudo(). In exchange, everything that arrives
    from the browser is validated again here - the price is always worked out
    on the server and never taken from the form.

    Every route here first checks that delivery belongs to the website being
    asked. A route is registered once per database, so without that check the
    gelateria's order form would answer on every other website in the same
    database - flavours, prices and all.
    """

    def _delivery_website(self):
        """The website asking, but only if delivery lives on it."""
        website = request.website
        if not website or not website.gelato_delivery_site:
            raise werkzeug.exceptions.NotFound()
        return website

    # ------------------------------------------------------------------
    # Data for the page
    # ------------------------------------------------------------------
    def _page_values(self):
        website = request.website
        env = request.env
        flavors = env["gelato.flavor"].sudo().search([("available", "=", True)])
        boxes = env["gelato.delivery.box"].sudo().search([])
        addons = env["gelato.delivery.addon"].sudo().search([])

        orders_open, hours_note = website.gelato_orders_open()

        return {
            "flavors": flavors,
            "flavors_by_category": self._group_by_category(flavors),
            "boxes": boxes,
            "addons": addons,
            "website": website,
            "delivery_enabled": website.gelato_delivery_enabled,
            "promo_note": website.gelato_delivery_promo_note or "",
            "zones": env["gelato.delivery.zone"].sudo().search([]),
            "orders_open": orders_open,
            "hours_note": hours_note,
        }

    def _group_by_category(self, flavors):
        """Sort flavours into groups by category, skipping empty groups.

        The groups follow the order set on the categories themselves, not the
        order the flavours happen to come in. Otherwise moving one flavour
        between categories would reshuffle the whole page - the section of
        whichever flavour sorts first would jump to the top.

        Flavours with no category go last.
        """
        groups = []
        seen = {}
        for flavor in flavors:
            key = flavor.category_id.id or 0
            if key not in seen:
                seen[key] = {
                    "category": flavor.category_id,
                    "name": flavor.category_id.name or _("Other"),
                    "flavors": [],
                }
                groups.append(seen[key])
            seen[key]["flavors"].append(flavor)

        def order(group):
            category = group["category"]
            if not category:
                return (1, 0, "")
            return (0, category.sequence, category.name or "")

        return sorted(groups, key=order)

    @http.route(
        ["/rozvoz"],
        type="http",
        auth="public",
        website=True,
        sitemap=_sitemap_rozvoz,
    )
    def rozvoz(self, **kwargs):
        self._delivery_website()
        return request.render("gelato_delivery.rozvoz", self._page_values())

    # ------------------------------------------------------------------
    # Promo code validation
    # ------------------------------------------------------------------
    @http.route(
        ["/rozvoz/overit-kod"],
        type="json",
        auth="public",
        website=True,
        methods=["POST"],
    )
    def overit_kod(self, code=None, **kwargs):
        self._delivery_website()
        promo = request.env["gelato.promo.code"].sudo().find_valid(code)
        if not promo:
            return {
                "valid": False,
                "message": _("We do not know this code, or it has expired."),
            }
        return {
            "valid": True,
            "code": promo.code,
            "discount_percent": promo.discount_percent,
            # What the code covers, so the page can show the same figure
            # the server will charge instead of taking the percentage off
            # everything.
            "scope": promo.scope,
            "box_ids": promo.box_ids.ids,
            "addon_ids": promo.addon_ids.ids,
            "message": _("The code is valid: %s.") % promo.scope_label,
        }

    # ------------------------------------------------------------------
    # Address check against the drawn zones
    # ------------------------------------------------------------------
    @http.route(
        ["/rozvoz/overit-adresu"],
        type="json",
        auth="public",
        website=True,
        methods=["POST"],
    )
    def overit_adresu(self, address=None, postcode=None, **kwargs):
        self._delivery_website()
        result = self._locate_address(address, postcode)
        zone = result["zone"]

        if not result["checked"]:
            return {"valid": True, "message": "", "fee": None}

        if not result["located"]:
            if result["service_error"]:
                # Our map is down, not their typing. Let them order.
                return {
                    "valid": True,
                    "unsure": True,
                    "fee": None,
                    "message": _(
                        "We cannot check the address right now. Send the order "
                        "anyway - we will get back to you and agree the delivery."
                    ),
                }
            return {
                "valid": False,
                "fee": None,
                "message": _(
                    "We could not find that address. Please check the street "
                    "and the house number."
                ),
            }

        if not zone:
            return {
                "valid": False,
                "fee": None,
                "message": _(
                    "We do not drive there. Call us and we will see what we "
                    "can do."
                ),
            }

        # Say the threshold out loud where there is one. Promising "delivery
        # 79 CZK" and then charging nothing reads like a mistake, and the
        # page cannot work it out on its own - the fee is decided here.
        if zone.free_from:
            message = _(
                "We deliver to %(zone)s, delivery %(fee)s CZK - free from "
                "%(free_from)s CZK."
            ) % {
                "zone": zone.name,
                "fee": int(zone.delivery_fee),
                "free_from": int(zone.free_from),
            }
        else:
            message = _("We deliver to %(zone)s, delivery %(fee)s CZK.") % {
                "zone": zone.name,
                "fee": int(zone.delivery_fee),
            }

        return {
            "valid": True,
            "fee": zone.delivery_fee,
            "free_from": zone.free_from,
            "zone": zone.name,
            "message": message,
        }

    def _locate_address(self, address, postcode):
        """Put an address on the map and find its zone.

        ``checked`` is False when the shop has drawn no zones at all - then
        nothing is refused and the flat fee from the settings applies.
        """
        env = request.env
        Zone = env["gelato.delivery.zone"]
        empty = {
            "checked": False,
            "located": False,
            "service_error": False,
            "zone": Zone.sudo().browse(),
            "lat": 0.0,
            "lng": 0.0,
        }
        if not Zone.sudo().search_count([]):
            return empty

        found = env["gelato.geocode"].sudo().locate(address, postcode)
        if not found.get("found"):
            return dict(
                empty,
                checked=True,
                service_error=bool(found.get("service_error")),
            )

        lat = found["lat"]
        lng = found["lng"]
        return {
            "checked": True,
            "located": True,
            "service_error": False,
            "zone": Zone.zone_for(lat, lng),
            "lat": lat,
            "lng": lng,
        }

    # ------------------------------------------------------------------
    # Placing an order
    # ------------------------------------------------------------------
    @http.route(
        ["/rozvoz/objednat"],
        type="json",
        auth="public",
        website=True,
        methods=["POST"],
    )
    def objednat(self, **payload):
        website = self._delivery_website()
        if not website.gelato_delivery_enabled:
            return {"success": False, "error": _("Delivery is paused right now.")}

        env = request.env
        errors = []

        # ---------- contact ----------
        customer_name = (payload.get("customer_name") or "").strip()
        customer_phone = (payload.get("customer_phone") or "").strip()
        customer_email = (payload.get("customer_email") or "").strip()
        delivery_address = (payload.get("delivery_address") or "").strip()

        if not customer_name:
            errors.append(_("Please fill in your name."))
        if not customer_phone:
            errors.append(_("Please fill in your phone number."))
        if not customer_email:
            errors.append(_("Please fill in your email."))
        elif not EMAIL_RE.match(customer_email):
            errors.append(_("That email address does not look right."))
        if not delivery_address:
            errors.append(_("Please fill in the delivery address."))

        # An order is for now. Nobody picks a day or a slot, so the date is
        # simply the day it came in.
        delivery_date = fields.Date.context_today(env["gelato.flavor"].sudo())

        # The page hides the form when the delivery is switched off, but a
        # stale tab could still post - so the switch holds here as well.
        orders_open, hours_note = website.gelato_orders_open()
        if not orders_open:
            errors.append(
                hours_note or _("We are not taking orders right now.")
            )

        # ---------- delivery zone ----------
        # The address goes on the map and the zone it lands in sets the fee.
        # An address the map does not know is sent back to be corrected: a
        # typo takes the customer two seconds to fix and would otherwise land
        # on the shop as an order nobody priced. The one case that still goes
        # through is the map being unreachable - that is our fault, not
        # theirs, and it must never stop an order.
        postcode = (payload.get("delivery_postcode") or "").strip()
        located = self._locate_address(delivery_address, postcode)
        zone = located["zone"]
        # An empty address was already complained about above; saying it is
        # also not on the map on top of that helps nobody.
        if (
            delivery_address
            and located["checked"]
            and not located["located"]
            and not located["service_error"]
        ):
            errors.append(
                _(
                    "We could not find that address. Please check the street "
                    "and the house number."
                )
            )
        if located["checked"] and located["located"] and not zone:
            errors.append(
                _(
                    "We do not deliver to that address. Give us a ring and we "
                    "will see what we can do."
                )
            )

        # ---------- the basket ----------
        item_commands, items_total, lines = self._build_items(
            payload.get("items") or [], errors
        )

        if errors:
            return {"success": False, "error": " ".join(errors)}

        # ---------- amounts (always server side) ----------
        subtotal = items_total
        promo = env["gelato.promo.code"].sudo().find_valid(payload.get("promo_code"))
        discount_percent = promo.discount_percent if promo else 0.0
        # A code only takes money off what it was written for: the whole
        # order, one product, or the drive.
        discount = promo.product_discount(lines) if promo else 0.0
        # The zone's own price wins; the flat fee from the settings is what
        # applies before any zone is drawn, or when the address is a mystery.
        if zone:
            base = subtotal
            if website.gelato_delivery_fee_base == "after_discount":
                base = subtotal - discount
            delivery_fee = zone.fee_for(base)
        else:
            delivery_fee = website.gelato_delivery_fee_for(subtotal, discount)

        # The fee has to be worked out before anything can come off it.
        if promo:
            discount += promo.delivery_discount(delivery_fee)

        if zone and zone.min_order and subtotal < zone.min_order:
            return {
                "success": False,
                "error": _(
                    "The minimum order for %(zone)s is %(amount)s CZK."
                )
                % {"zone": zone.name, "amount": int(zone.min_order)},
            }

        order = env["gelato.delivery.order"].sudo().create(
            {
                "customer_name": customer_name,
                "customer_phone": customer_phone,
                "customer_email": customer_email,
                "delivery_address": delivery_address,
                "delivery_postcode": postcode,
                "delivery_city": (payload.get("delivery_city") or "Karlovy Vary").strip(),
                "zone_id": zone.id if zone else False,
                "latitude": located["lat"],
                "longitude": located["lng"],
                "address_located": located["located"],
                "delivery_date": delivery_date,
                "note": (payload.get("note") or "").strip(),
                "item_ids": item_commands,
                "promo_code_id": promo.id if promo else False,
                "discount_percent": discount_percent,
                # The figure, not the rule: what the code covered is
                # settled here and now, so editing the code next month
                # does not reprice an order that has already been driven.
                "amount_discount": discount,
                "delivery_fee": delivery_fee,
                "website_id": website.id,
                "source": "website",
            }
        )

        if promo:
            promo.register_use()

        order._send_confirmation_email()

        return {
            "success": True,
            "order_ref": order.name,
            "message": _(
                "We have your order. We will get back to you to confirm the time."
            ),
            "tracking": order.tracking_payload(),
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _build_items(self, raw_items, errors):
        """Turn the basket the browser sent into order items.

        Every line names either a thermal box or a bundle/extra, and the
        ones that hold gelato carry their own flavours - two boxes in one
        basket are filled separately. Prices are read from Odoo here and
        never taken from the browser, so the page cannot make an order
        cheaper than it is.

        Returns the commands, the total, and the plain list of
        (record, quantity, unit price) - a promo code needs the records
        themselves to tell whether it covers them.
        """
        env = request.env
        commands = []
        total = 0.0
        lines = []

        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            quantity = self._to_int(raw.get("quantity")) or 1
            if quantity <= 0:
                continue

            kind = raw.get("kind")
            record_id = self._to_int(raw.get("id"))
            if not record_id:
                continue

            if kind == "box":
                product = env["gelato.delivery.box"].sudo().browse(record_id).exists()
                if not product or not product.active:
                    errors.append(_("One of the thermal boxes is no longer available."))
                    continue
                parts = product.max_flavors
                price = product.price
                values = {"box_id": product.id}
            else:
                product = env["gelato.delivery.addon"].sudo().browse(record_id).exists()
                if not product or not product.active:
                    errors.append(_("One of the extras is no longer available."))
                    continue
                if product.max_quantity and quantity > product.max_quantity:
                    quantity = product.max_quantity
                # A bundle brings its own thermal box, so it is filled with
                # flavours just like a box is.
                parts = product.bundle_box_id.max_flavors if product.bundle_box_id else 0
                # And it is charged as the whole thing. A bundle's `price`
                # is only the surcharge over its box, which made sense when
                # the box was a second line on the order; as one basket
                # line it has to carry the price on the leaflet.
                price = product.display_price()
                values = {"addon_id": product.id}

            flavor_commands = self._build_flavor_lines(
                raw.get("flavors") or [], parts, product.name, errors
            )
            values.update(
                {
                    "quantity": quantity,
                    "price_unit": price,
                    "flavor_line_ids": flavor_commands,
                }
            )
            commands.append((0, 0, values))
            lines.append((product, quantity, price))
            total += price * quantity

        if not commands:
            errors.append(_("Your order is empty. Please pick something first."))

        return commands, total, lines

    def _build_flavor_lines(self, raw_flavors, parts, product_name, errors):
        """Flavour lines for one box, with how much of it each one takes.

        The box is handed out in parts and the counts have to add up to
        exactly that many - anything else is an order nobody can fill. A
        product with no parts (a bottle of prosecco) takes no flavours.
        """
        env = request.env
        commands = []
        total_parts = 0
        seen = set()

        for raw in raw_flavors:
            flavor_id = self._to_int(
                raw.get("id") if isinstance(raw, dict) else raw
            )
            quantity = self._to_int(
                raw.get("quantity") if isinstance(raw, dict) else 1
            ) or 1
            if not flavor_id or quantity <= 0 or flavor_id in seen:
                continue
            seen.add(flavor_id)

            flavor = env["gelato.flavor"].sudo().browse(flavor_id).exists()
            if not flavor:
                continue
            # Never let through a flavour the staff has just switched off.
            if not flavor.available:
                errors.append(
                    _("We have run out of %s today. Please pick another one.")
                    % flavor.name
                )
                continue

            total_parts += quantity
            commands.append(
                (0, 0, {"flavor_id": flavor.id, "quantity": quantity})
            )

        if not parts:
            # Nothing to fill: an extra that is not a box takes no flavours.
            return []

        if not commands:
            errors.append(
                _("Please pick the flavours for %s.") % product_name
            )
            return commands

        if total_parts != parts:
            errors.append(
                _("%(product)s is split into %(parts)s, you have handed out "
                  "%(given)s. Please use them all.")
                % {"product": product_name, "parts": parts, "given": total_parts}
            )
        return commands

    @staticmethod
    def _to_int(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _parse_date(value):
        if not value:
            return False
        try:
            return fields.Date.to_date(value)
        except (ValueError, TypeError):
            return False
