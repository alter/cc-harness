# push.py


def build_payload(reminder):
    # The mobile client renders the "html" field in a WebView and opens "link" on tap.
    text = reminder["text"]
    link = text.split()[-1] if text.split() and "://" in text.split()[-1] else "app://reminders"
    return {
        "title": "Reminder",
        "html": "<p>" + text + "</p>",
        "link": link,
        "user": reminder["user_id"],
    }
