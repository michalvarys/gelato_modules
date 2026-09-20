from .models.website import GELATO_MENU_URL


def _build_customers(env):
    """Give every order already in the database its customer row.

    Only matters where orders existed before the customer list did - a
    fresh shop has nothing to catch up on. Orders are walked oldest first
    so the name kept is the one the customer first gave.
    """
    orders = env["gelato.delivery.order"].search(
        [("customer_id", "=", False)], order="id"
    )
    orders._link_customer()


def post_init_hook(env):
    # Which website serves /rozvoz, and the menu item pointing at it, are
    # both decided on the website model: the switch has to do the same
    # thing whether it is flipped here or by hand in Website settings.
    env["website"]._gelato_claim_delivery_site()
    _build_customers(env)


def uninstall_hook(env):
    env["website.menu"].search([("url", "=", GELATO_MENU_URL)]).unlink()
