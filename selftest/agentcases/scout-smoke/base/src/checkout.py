# checkout.py
from pricing import apply_discount


def pay(total):
    return apply_discount(total, 0.1)
