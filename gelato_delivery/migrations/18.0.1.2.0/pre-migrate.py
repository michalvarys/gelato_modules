"""Turn every old one-box order into a basket with one item.

Until now an order was a single thermal box written on the order itself,
with the extras on their own table. The website now sells several boxes in
one go, each with its own flavours, so everything moved onto
gelato.delivery.order.item. This copies the old orders over before the new
fields are loaded, so nothing that was already ordered is lost.

Every step checks that what it is about to read actually exists. The
module has been installed at several points in its life and the databases
it runs on are not all the same shape: one has flavour lines, an older one
still has the plain many2many, a fresh demo has neither. A migration that
assumes one of those shapes takes the whole upgrade down with it.
"""

import logging

_logger = logging.getLogger(__name__)


def _table(cr, name):
    cr.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_name = %s", (name,)
    )
    return bool(cr.fetchone())


def _column(cr, table, column):
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
         WHERE table_name = %s AND column_name = %s
        """,
        (table, column),
    )
    return bool(cr.fetchone())


def migrate(cr, version):
    if not version:
        return

    if _table(cr, "gelato_delivery_order_item"):
        _logger.info("gelato: items table already there, nothing to move")
        return

    cr.execute("""
        CREATE TABLE gelato_delivery_order_item (
            id serial PRIMARY KEY,
            order_id integer NOT NULL
                REFERENCES gelato_delivery_order(id) ON DELETE CASCADE,
            box_id integer REFERENCES gelato_delivery_box(id),
            addon_id integer REFERENCES gelato_delivery_addon(id),
            quantity integer NOT NULL DEFAULT 1,
            price_unit numeric,
            vat_rate numeric,
            price_subtotal numeric,
            label varchar,
            create_uid integer,
            create_date timestamp without time zone,
            write_uid integer,
            write_date timestamp without time zone
        )
    """)

    moved_boxes = 0
    if _column(cr, "gelato_delivery_order", "box_id"):
        # The box that was on the order becomes the first item. Older
        # databases carried the price and the VAT rate beside it; a newer
        # one has already dropped the VAT.
        price = ("box_price" if _column(cr, "gelato_delivery_order", "box_price")
                 else "NULL")
        vat = ("box_vat_rate"
               if _column(cr, "gelato_delivery_order", "box_vat_rate") else "NULL")
        cr.execute(f"""
            INSERT INTO gelato_delivery_order_item
                (order_id, box_id, quantity, price_unit, vat_rate,
                 price_subtotal, create_date, write_date)
            SELECT id, box_id, 1, {price}, {vat}, {price}, NOW(), NOW()
              FROM gelato_delivery_order
             WHERE box_id IS NOT NULL
             ORDER BY id
        """)
        moved_boxes = cr.rowcount

    # The flavours hung off the order; they now hang off that first item.
    if _table(cr, "gelato_delivery_order_flavor"):
        cr.execute("""
            ALTER TABLE gelato_delivery_order_flavor
              ADD COLUMN IF NOT EXISTS item_id integer
                  REFERENCES gelato_delivery_order_item(id) ON DELETE CASCADE
        """)
        cr.execute("""
            UPDATE gelato_delivery_order_flavor f
               SET item_id = i.id
              FROM gelato_delivery_order_item i
             WHERE i.order_id = f.order_id
               AND i.box_id IS NOT NULL
        """)
        # A flavour with no box to belong to cannot be kept - the column
        # is about to become required.
        cr.execute(
            "DELETE FROM gelato_delivery_order_flavor WHERE item_id IS NULL"
        )

    # Every extra becomes an item of its own.
    moved_addons = 0
    if _table(cr, "gelato_delivery_order_addon"):
        vat = ("vat_rate"
               if _column(cr, "gelato_delivery_order_addon", "vat_rate") else "NULL")
        cr.execute(f"""
            INSERT INTO gelato_delivery_order_item
                (order_id, addon_id, quantity, price_unit, vat_rate,
                 price_subtotal, create_date, write_date)
            SELECT order_id, addon_id, quantity, price_unit, {vat},
                   price_subtotal, NOW(), NOW()
              FROM gelato_delivery_order_addon
             ORDER BY id
        """)
        moved_addons = cr.rowcount
        cr.execute("DROP TABLE gelato_delivery_order_addon")

    _logger.info(
        "gelato: moved %s boxes and %s extras onto order items",
        moved_boxes, moved_addons,
    )
