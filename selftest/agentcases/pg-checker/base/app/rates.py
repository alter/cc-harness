# rates.py
import psycopg2
import requests


def refresh_rate(dsn, currency):
    rate = requests.get(f"https://rates.example/{currency}", timeout=10).json()["rate"]
    conn = psycopg2.connect(dsn)
    with conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE rates SET rate = %s WHERE currency = %s", (rate, currency))
    conn.close()
    return rate
