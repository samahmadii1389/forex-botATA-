import os
import requests
from datetime import datetime, timezone, timedelta

# ---------- تنظیمات ----------
FEED_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
TEHRAN_TZ = timezone(timedelta(hours=3, minutes=30))

IMPACT_EMOJI = {
    "High": "🔴",
    "Medium": "🟠",
}

def send_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    resp = requests.post(url, data={
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }, timeout=15)
    resp.raise_for_status()

def format_event_line(event, event_time_local):
    emoji = IMPACT_EMOJI.get(event["impact"], "")
    title = event.get("title", "")
    forecast = event.get("forecast") or "—"
    previous = event.get("previous") or "—"
    time_str = event_time_local.strftime("%H:%M")
    return (
        f"{emoji} <b>{time_str}</b> - {title}\n"
        f"   📊 پیش‌بینی: {forecast} | 📌 قبلی: {previous}"
    )

def main():
    resp = requests.get(FEED_URL, timeout=20)
    resp.raise_for_status()
    events = resp.json()

    today_tehran = datetime.now(TEHRAN_TZ).date()

    todays_events = []
    for event in events:
        if event.get("country") != "USD":
            continue
        if event.get("impact") not in ("High", "Medium"):
            continue

        raw_date = event.get("date")
        if not raw_date:
            continue
        try:
            event_time = datetime.fromisoformat(raw_date)
        except ValueError:
            continue
        if event_time.tzinfo is None:
            event_time = event_time.replace(tzinfo=timezone.utc)

        event_time_local = event_time.astimezone(TEHRAN_TZ)
        if event_time_local.date() != today_tehran:
            continue

        todays_events.append((event_time_local, event))

    todays_events.sort(key=lambda x: x[0])

    if not todays_events:
        message = "📅 امروز خبر مهم قرمز یا نارنجی دلاری در تقویم نیست."
    else:
        header = f"📅 <b>اخبار USD امروز ({today_tehran.strftime('%Y-%m-%d')})</b>\n"
        lines = [format_event_line(ev, t) for t, ev in todays_events]
        message = header + "\n\n".join(lines)

    send_telegram(message)
    print("پیام ارسال شد.")

if __name__ == "__main__":
    main()
