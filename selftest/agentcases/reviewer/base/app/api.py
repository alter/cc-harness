# api.py
from pricing import price_after_discount, ratio


def handle_checkout(params):
    total = int(params["total"])
    return {"price": total}
