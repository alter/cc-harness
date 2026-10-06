# calc.py
import time


def add(a, b):
    return a + b


def fetch_with_retry(fetch, retries=3, wait=1.0):
    for attempt in range(retries):
        value = fetch()
        if value is not None:
            return value
        time.sleep(wait)
    return None
