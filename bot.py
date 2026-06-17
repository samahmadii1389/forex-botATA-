import asyncio
import logging
import os
import xml.etree.ElementTree as ET
from datetime import datetime, date
from zoneinfo import ZoneInfo
import httpx
from telegram import Bot
from telegram.constants import ParseMode

# ─── تنظیمات ───────────────────────────────────────────────
BOT_TOKEN   = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
CHANNEL_ID  = os.getenv("CHANNEL_ID", "@your_channel_username")

FF_RSS_URL  = "https://nfs.faireconomy.media/ff_calendar_thisweek.xml"

IMPACT_FILTER = {"High", "Medium"}
CURRENCY_FILTER = "USD"

TEHRAN_TZ   = ZoneInfo("Asia/Tehran")
ET_TZ       = ZoneInfo("America/New_York")
UTC_TZ      = ZoneInfo("UTC")

SEND_HOUR   = 7
SEND_MINUTE = 0

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

def convert_time(time_str: str, date_str: str) -> str:
    """تبدیل ساعت UTC به وقت نیویورک (همان چیزی که فارکس فکتوری نشون می‌ده)"""
    if not time_str or time_str.strip() == "":
        return "All Day"
    try:
        # فرمت RSS: "12:00am" یا "1:30pm"
        try:
            event_date = datetime.strptime(date_str, "%m-%d-%Y").date()
        except ValueError:
            event_date = datetime.strptime(date_str, "%Y-%m-%d").date()

        dt_str = f"{event_date} {time_str}"
        dt_utc = datetime.strptime(dt_str, "%Y-%m-%d %I:%M%p").replace(tzinfo=UTC_TZ)
        dt_et = dt_utc.astimezone(ET_TZ)
        return dt_et.strftime("%I:%M%p").lstrip("0")
    except Exception:
        return time_str

# ─── دریافت اخبار از RSS فارکس فکتوری ────────────────────
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
            title    = (item.findtext("title")   or "").strip()
            date_str = (item.findtext("date")    or "").strip()
            time_str = (item.findtext("time")    or "").strip()
            forecast = (item.findtext("forecast") or "—").strip()
            previous = (item.findtext("previous") or "—").strip()

            if currency != CURRENCY_FILTER:
                continue
            if impact not in IMPACT_FILTER:
                continue

            try:
                event_date = datetime.strptime(date_str, "%m-%d-%Y").date()
            except ValueError:
                event_date = datetime.strptime(date_str, "%Y-%m-%d").date()

            if event_date != today:
                continue

            display_time = convert_time(time_str, str(event_date))

            events.append({
                "title":    title,
                "time":     display_time,
                "time_raw": time_str,
                "impact":   impact,
                "forecast": forecast,
                "previous": previous,
            })
        except Exception as e:
            log.warning(f"Error processing event: {e}")

    events.sort(key=lambda x: x["time_raw"])
    return events


# ─── ساخت پیام تلگرام ────────────────────────────────────
def build_message(events: list[dict]) -> str:
    now = datetime.now(TEHRAN_TZ)
    today_fa = now.strftime("%Y/%m/%d")
    weekday_map = {
        "Monday": "دوشنبه", "Tuesday": "سه‌شنبه", "Wednesday": "چهارشنبه",
        "Thursday": "پنج‌شنبه", "Friday": "جمعه",
    }
    weekday_fa = weekday_map.get(now.strftime("%A"), now.strftime("%A"))

    lines = [
        f"🇺🇸 *اخبار فارکس آمریکا — {weekday_fa} {today_fa}*",
        "━━━━━━━━━━━━━━━━━━━",
    ]

    if not events:
        lines.append("📭 امروز خبر مهمی برای USD وجود ندارد.")
    else:
        for ev in events:
            impact_icon = "🔴" if ev["impact"] == "High" else "🟠"
            lines.append(
                f"{impact_icon} *{ev['title']}*\n"
                f"   🕐 `{ev['time']} ET`  |  پیش‌بینی: `{ev['forecast']}`  |  قبلی: `{ev['previous']}`"
            )
            lines.append("")

    lines.append("━━━━━━━━━━━━━━━━━━━")
    lines.append("📊 [Forex Factory](https://www.forexfactory.com/calendar)")
    return "\n".join(lines)


# ─── ارسال پیام ───────────────────────────────────────────
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
        log.info(f"✅ Sent {len(events)} events.")
    except Exception as e:
        log.error(f"❌ Send error: {e}")


# ─── زمان‌بندی ────────────────────────────────────────────
async def scheduler():
    log.info("🤖 Bot started...")

    try:
        bot = Bot(token=BOT_TOKEN)
        await bot.send_message(
            chat_id=CHANNEL_ID,
            text="✅ ربات با موفقیت روشن شد و در حال کار است.",
        )
        log.info("✅ Test message sent.")
    except Exception as e:
        log.error(f"❌ Test message error: {e}")

    while True:
        now = datetime.now(TEHRAN_TZ)
        weekday = now.weekday()

        if weekday < 5 and now.hour == SEND_HOUR and now.minute == SEND_MINUTE:
            await send_daily_news()
            await asyncio.sleep(61)
        else:
            await asyncio.sleep(30)


# ─── اجرا ─────────────────────────────────────────────────
if __name__ == "__main__":
    asyncio.run(scheduler())
                
