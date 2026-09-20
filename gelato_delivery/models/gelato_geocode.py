import json
import logging
import re
from datetime import timedelta

import requests

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
TIMEOUT = 8


class GelatoGeocode(models.Model):
    """Addresses already turned into map coordinates.

    OpenStreetMap's geocoder is free but asks not to be hammered, so every
    answer is kept. The same street typed by the next customer costs nothing
    and the page answers instantly.
    """

    _name = "gelato.geocode"
    _description = "Geocoded Address"
    _order = "id desc"

    query = fields.Char(string="Address asked for", required=True, index=True)
    latitude = fields.Float(string="Latitude", digits=(10, 7))
    longitude = fields.Float(string="Longitude", digits=(10, 7))
    found = fields.Boolean(string="Found")
    label = fields.Char(string="What the map says")
    last_used = fields.Datetime(string="Last used")

    _sql_constraints = [
        ("query_unique", "unique(query)", "This address is already stored."),
    ]

    @api.model
    def _normalise(self, address, postcode=None):
        parts = [(address or "").strip()]
        if postcode:
            parts.append(postcode.strip())
        return " ".join(", ".join(part for part in parts if part).split())

    @api.model
    def _candidates(self, address, postcode=None):
        """What to ask the map, best guess first.

        Most people ordering from a shop in Karlovy Vary type a street and
        nothing else, so the town is tried first - "Hlavní 1" must not land
        in some village at the other end of the country. Next comes the
        address exactly as typed, which is what catches someone genuinely
        writing a Prague address: it is found, falls outside every zone, and
        is refused rather than shrugged at.

        After that come looser and looser tries. A flat number, a doorbell
        name or a floor glued onto the street is enough to make the map give
        up on an address that is perfectly real, and the zone only needs to
        know the street.
        """
        address = (address or "").strip()
        postcode = (postcode or "").strip()
        if not address:
            return []

        base = ", ".join(part for part in (address, postcode) if part)
        in_kv = "karlovy vary" in base.lower()

        tries = []
        if not in_kv:
            tries.append(f"{base}, Karlovy Vary")
        tries.append(base)

        # Street and house number only - drop the floor, the doorbell and
        # whatever else came after.
        street = self._street_only(address)
        if street and street.lower() != address.lower():
            if not in_kv:
                tries.append(f"{street}, Karlovy Vary")
            tries.append(street)

        # Street without the number at all. Puts the pin somewhere along the
        # street, which is more than good enough to pick a zone.
        bare = self._drop_number(street or address)
        if bare and bare.lower() not in (address.lower(), (street or "").lower()):
            if not in_kv:
                tries.append(f"{bare}, Karlovy Vary")
            tries.append(bare)

        seen = set()
        unique = []
        for item in tries:
            key = " ".join(item.split()).lower()
            if key and key not in seen:
                seen.add(key)
                unique.append(" ".join(item.split()))
        return unique

    @staticmethod
    def _street_only(address):
        """Everything up to the first comma - street and number."""
        return address.split(",")[0].strip()

    @staticmethod
    def _drop_number(text):
        """The street without any house number."""
        cleaned = re.sub(r"\b\d+[a-zA-Z]?(/\d+[a-zA-Z]?)?\b", " ", text or "")
        return " ".join(cleaned.split()).strip(" ,-")

    @api.model
    def locate(self, address, postcode=None):
        """Coordinates for an address. Returns a dict, never raises.

        ``found`` False means we could not put the address on the map. That
        is not the same as "we do not deliver there" - the order still goes
        through and the shop sorts it out on the phone.
        """
        query = self._normalise(address, postcode)
        if not query:
            return {"found": False, "query": query}

        cached = self.sudo().search([("query", "=", query)], limit=1)
        if cached and not cached._is_stale():
            cached.last_used = fields.Datetime.now()
            return {
                "found": cached.found,
                "lat": cached.latitude,
                "lng": cached.longitude,
                "label": cached.label,
                "query": query,
            }

        result = {"found": False}
        for candidate in self._candidates(address, postcode):
            result = self._ask_nominatim(candidate)
            if result.get("found"):
                break
            if result.get("service_error"):
                # The map itself is down. That is our problem, not the
                # customer's - do not remember it and do not blame them.
                result["query"] = query
                return result

        values = {
            "query": query,
            "latitude": result.get("lat") or 0.0,
            "longitude": result.get("lng") or 0.0,
            "found": result.get("found", False),
            "label": result.get("label"),
            "last_used": fields.Datetime.now(),
        }
        if cached:
            cached.write(values)
        else:
            self.sudo().create(values)
        result["query"] = query
        return result

    def _is_stale(self):
        """Should we ask the map again?

        A hit is kept for good - a street does not move. A miss is kept only
        for a day, because the usual reason for a miss is the map being
        briefly unreachable, and a permanently cached failure would refuse a
        perfectly good address forever.
        """
        self.ensure_one()
        if self.found:
            return False
        if not self.last_used:
            return True
        return (fields.Datetime.now() - self.last_used) > timedelta(days=1)

    @api.model
    def _ask_nominatim(self, query):
        try:
            response = requests.get(
                NOMINATIM_URL,
                params={
                    "q": query,
                    "format": "json",
                    "limit": 1,
                    "countrycodes": "cz",
                },
                headers={
                    # OpenStreetMap asks every caller to say who they are.
                    "User-Agent": "Gelato Karlovy Vary delivery "
                    "(gelatokv@seznam.cz)",
                    "Accept-Language": "cs",
                },
                timeout=TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError, json.JSONDecodeError) as error:
            # The map being unreachable must never stop an order. Kept apart
            # from "the map answered and knows no such place", because only
            # the second one is something the customer can fix.
            _logger.warning("Could not look up “%s”: %s", query, error)
            return {"found": False, "service_error": True}

        if not data:
            return {"found": False}

        first = data[0]
        try:
            return {
                "found": True,
                "lat": float(first["lat"]),
                "lng": float(first["lon"]),
                "label": first.get("display_name"),
            }
        except (KeyError, TypeError, ValueError):
            return {"found": False}
