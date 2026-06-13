import asyncio
import logging
import os
import xml.etree.ElementTree as ET
from datetime import datetime, date
import httpx
from telegram import Bot
from telegram.constants import ParseMode

# ─── تنظیمات ───────────────────────────────────────────────
BOT_TOKEN   = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
CHANNEL_ID  = os.getenv("CHANNEL_ID", "@your_channel_username")  # یا عدد مثل -1001234567890

FF_RSS_URL  = "https://nfs.faireconomy.media/ff_calendar_thisweek.xml"

IMPACT_FILTER = {"High", "Medium"}   # قرمز = High | نارنجی = Medium
CURRENCY_FILTER = "USD"

SEND_HOUR   = 7    # ساعت ارسال (به وقت سرور)
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

# ─── دریافت اخبار از RSS فارکس فکتوری ────────────────────
async def fetch_news() -> list[dict]:
    """دریافت اخبار هفته جاری از فارکس فکتوری"""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(FF_RSS_URL)
        resp.raise_for_status()

    root = ET.fromstring(resp.text)
    today = date.today()
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

            # تبدیل تاریخ
            try:
                event_date = datetime.strptime(date_str, "%m-%d-%Y").date()
            except ValueError:
                event_date = datetime.strptime(date_str, "%Y-%m-%d").date()

            if event_date != today:
                continue

            events.append({
                "title":    title,
                "time":     time_str,
                "impact":   impact,
                "forecast": forecast,
                "previous": previous,
            })
        except Exception as e:
            log.warning(f"خطا در پردازش رویداد: {e}")

    # مرتب‌سازی بر اساس ساعت
    events.sort(key=lambda x: x["time"])
    return events


# ─── ساخت پیام تلگرام ────────────────────────────────────
def build_message(events: list[dict]) -> str:
    today_fa = datetime.now().strftime("%Y/%m/%d")
    weekday_map = {
        "Monday": "دوشنبه", "Tuesday": "سه‌شنبه", "Wednesday": "چهارشنبه",
        "Thursday": "پنج‌شنبه", "Friday": "جمعه",
    }
    weekday_en = datetime.now().strftime("%A")
    weekday_fa = weekday_map.get(weekday_en, weekday_en)

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
                f"   🕐 `{ev['time']}`  |  پیش‌بینی: `{ev['forecast']}`  |  قبلی: `{ev['previous']}`"
            )
            lines.append("")

    lines.append("━━━━━━━━━━━━━━━━━━━")
    lines.append("📊 [Forex Factory](https://www.forexfactory.com/calendar)")
    return "\n".join(lines)


# ─── ارسال پیام ───────────────────────────────────────────
async def send_daily_news():
    log.info("📡 در حال دریافت اخبار...")
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
        log.info(f"✅ پیام با {len(events)} خبر ارسال شد.")
    except Exception as e:
        log.error(f"❌ خطا در ارسال: {e}")


# ─── زمان‌بندی ────────────────────────────────────────────
async def scheduler():
    log.info("🤖 ربات شروع به کار کرد...")
    while True:
        now = datetime.now()
        weekday = now.weekday()   # 0=Mon … 4=Fri

        # فقط دوشنبه تا جمعه (0-4)
        if weekday < 5 and now.hour == SEND_HOUR and now.minute == SEND_MINUTE:
            await send_daily_news()
            await asyncio.sleep(61)   # جلوگیری از ارسال مجدد در همان دقیقه
        else:
            await asyncio.sleep(30)   # بررسی هر ۳۰ ثانیه


# ─── اجرا ─────────────────────────────────────────────────
if __name__ == "__main__":
    asyncio.run(scheduler())
