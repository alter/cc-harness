# api.py
from pricing import price_after_discount, ratio


def handle_checkout(params):
    total = int(params["total"])
    percent = int(params.get("discount_percent", 0))
    return {"price": price_after_discount(total, percent)}


def handle_share(params):
    part = int(params["part"])
    whole = int(params["whole"])
    if whole <= 0:
        return {"error": "whole must be positive"}
    return {"share": ratio(part, whole)}
