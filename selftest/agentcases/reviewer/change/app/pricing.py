# pricing.py


def price_after_discount(total, percent):
    return total - total * percent // 100


def ratio(part, whole):
    return part / whole
