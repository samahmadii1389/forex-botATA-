import asyncio
import logging
import os
import xml.etree.ElementTree as ET
from datetime import datetime
from zoneinfo import ZoneInfo
import httpx
from telegram import Bot
from telegram.constants import ParseMode

# Settings
BOT_TOKEN      = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
CHANNEL_ID     = os.getenv("CHANNEL_ID", "@your_channel_username")
FF_RSS_URL     = "https://nfs.faireconomy.media/ff_calendar_thisweek.xml"
IMPACT_FILTER  = {"High", "Medium"}
CURRENCY_FILTER = "USD"
TEHRAN_TZ      = ZoneInfo("Asia/Tehran")
ET_TZ          = ZoneInfo("America/New_York")
SEND_HOUR      = 7   # Tehran time
SEND_MINUTE    = 0

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler()],
)
log = logging.getLogger(__name__)


def to_tehran_time(time_str: str, event_date) -> str:
    """Convert Forex Factory ET time string (e.g. '8:30am') to Tehran HH:MM"""
    if not time_str or not time_str.strip():
        return "تمام روز"
    try:
        dt_et = datetime.strptime(
            f"{event_date} {time_str.strip()}", "%Y-%m-%d %I:%M%p"
        ).replace(tzinfo=ET_TZ)
        return dt_et.astimezone(TEHRAN_TZ).strftime("%H:%M")
    except Exception:
        return time_str


async def fetch_news() -> list[dict]:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(FF_RSS_URL)
        resp.raise_for_status()

    root = ET.fromstring(resp.text)
    today = datetime.now(TEHRAN_TZ).date()
    events = []

    for item in root.findall(".//event"):
        try:
            currency = (item.findtext("country") or "").strip()
            impact   = (item.findtext("impact")  or "").strip()
            if currency != CURRENCY_FILTER or impact not in IMPACT_FILTER:
                continue

            date_str = (item.findtext("date") or "").strip()
            time_str = (item.findtext("time") or "").strip()
            title    = (item.findtext("title")    or "").strip()
            forecast = (item.findtext("forecast") or "—").strip()
            previous = (item.findtext("previous") or "—").strip()

            # parse date
            for fmt in ("%m-%d-%Y", "%Y-%m-%d"):
                try:
                    event_date = datetime.strptime(date_str, fmt).date()
                    break
                except ValueError:
                    continue
            else:
                continue

            if event_date != today:
                continue

            tehran_time = to_tehran_time(time_str, event_date)

            events.append({
                "title":    title,
                "time":     tehran_time,
                "time_raw": time_str,
                "impact":   impact,
                "forecast": forecast,
                "previous": previous,
            })
        except Exception as e:
            log.warning(f"Event parse error: {e}")

    events.sort(key=lambda x: x["time_raw"])
    return events


def build_message(events: list[dict]) -> str:
    now = datetime.now(TEHRAN_TZ)
    weekday_map = {
        "Monday": "دوشنبه", "Tuesday": "سه‌شنبه", "Wednesday": "چهارشنبه",
        "Thursday": "پنج‌شنبه", "Friday": "جمعه",
    }
    weekday_fa = weekday_map.get(now.strftime("%A"), now.strftime("%A"))
    date_fa = now.strftime("%Y/%m/%d")

    lines = [
        f"🇺🇸 *اخبار فارکس آمریکا — {weekday_fa} {date_fa}*",
        "━━━━━━━━━━━━━━━━━━━",
    ]

    if not events:
        lines.append("📭 امروز خبر مهمی برای USD وجود ندارد.")
    else:
        for ev in events:
            icon = "🔴" if ev["impact"] == "High" else "🟠"
            lines.append(
                f"{icon} *{ev['title']}*\n"
                f"   🕐 `{ev['time']} تهران`  |  پیش‌بینی: `{ev['forecast']}`  |  قبلی: `{ev['previous']}`"
            )
            lines.append("")

    lines.append("━━━━━━━━━━━━━━━━━━━")
    lines.append("📊 [Forex Factory](https://www.forexfactory.com/calendar)")
    return "\n".join(lines)


async def send_daily_news():
    log.info("Fetching news...")
    try:
        events = await fetch_news()
        message = build_message(events)
        bot = Bot(token=BOT_TOKEN)
        await bot.send_message(
            chat_id=CHANNEL_ID,
            text=message,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True,
        )
        log.info(f"Sent {len(events)} events.")
    except Exception as e:
        log.error(f"Send error: {e}")


async def scheduler():
    log.info("Bot started...")
    try:
        bot = Bot(token=BOT_TOKEN)
        await bot.send_message(
            chat_id=CHANNEL_ID,
            text="✅ ربات با موفقیت روشن شد و در حال کار است.",
        )
    except Exception as e:
        log.error(f"Startup message error: {e}")

    while True:
        now = datetime.now(TEHRAN_TZ)
        if now.weekday() < 5 and now.hour == SEND_HOUR and now.minute == SEND_MINUTE:
            await send_daily_news()
            await asyncio.sleep(61)
        else:
            await asyncio.sleep(30)


if __name__ == "__main__":
    asyncio.run(scheduler())
    
