# reminders.py
MAX_ID = 2**63 - 1


def create_reminder(db, user_id, text):
    if type(user_id) is not int or not 1 <= user_id <= MAX_ID:
        raise ValueError("user_id out of range")
    if not isinstance(text, str) or not 1 <= len(text) <= 500:
        raise ValueError("text length")
    db.append({"user_id": user_id, "text": text})
    return len(db) - 1
