# rates.py
import sqlite3


def fetch_rate(client, currency):
    return client.get_rate(currency)


def store_rate(db_path, client, currency):
    conn = sqlite3.connect(db_path)
    with conn:
        conn.execute("CREATE TABLE IF NOT EXISTS rates (currency TEXT, rate REAL)")
        rate = fetch_rate(client, currency)
        conn.execute("INSERT INTO rates VALUES (?, ?)", (currency, rate))
    conn.close()
    return rate
