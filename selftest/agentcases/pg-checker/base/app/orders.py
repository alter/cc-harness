# orders.py
import psycopg2
import requests


def charge(dsn, order_id, user_id, total):
    conn = psycopg2.connect(dsn)
    cur = conn.cursor()
    cur.execute("SELECT email FROM users WHERE id = %s", (user_id,))
    email = cur.fetchone()[0]
    receipt = requests.post("https://payments.example/charge", json={"email": email, "total": total}, timeout=30)
    cur.execute("INSERT INTO orders (id, user_id, total) VALUES (%s, %s, %s)", (order_id, user_id, total))
    conn.commit()
    conn.close()
    return receipt.json()


def orders_of(dsn, user_id):
    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SELECT id, total FROM orders WHERE user_id = %s ORDER BY created_at DESC", (user_id,))
    rows = cur.fetchall()
    conn.close()
    return rows
