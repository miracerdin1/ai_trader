"""
Telegram Bot modülü
- Sinyal mesajlarını Telegram'a gönderir
- python-telegram-bot kütüphanesi kullanır (async)
"""

import asyncio
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from loguru import logger

import config


async def _send_message_async(text: str, reply_markup: InlineKeyboardMarkup = None) -> bool:
    """
    Asenkron olarak Telegram mesajı gönderir.
    """
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        logger.warning(
            "⚠️  Telegram BOT_TOKEN veya CHAT_ID ayarlanmamış! "
            ".env dosyasını kontrol edin."
        )
        return False

    try:
        bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
        await bot.send_message(
            chat_id=config.TELEGRAM_CHAT_ID,
            text=text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup,
        )
        logger.success("📤 Telegram mesajı gönderildi!")
        return True

    except Exception as e:
        logger.error(f"❌ Telegram gönderme hatası: {e}")

        # Markdown parse hatası durumunda düz metin olarak dene
        try:
            bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
            await bot.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                text=text,
                reply_markup=reply_markup,
            )
            logger.success("📤 Telegram mesajı düz metin olarak gönderildi.")
            return True
        except Exception as e2:
            logger.error(f"❌ Telegram düz metin gönderme de başarısız: {e2}")
            return False


def get_signal_keyboard() -> InlineKeyboardMarkup:
    """Sinyal mesajı altına eklenecek butonları oluşturur."""
    keyboard = [
        [
            InlineKeyboardButton("📥 İŞLEME GİRDİM", callback_data="trade_enter"),
            InlineKeyboardButton("📤 İŞLEMİ KAPATTIM", callback_data="trade_exit"),
        ],
        [
            InlineKeyboardButton("📈 Durumu Güncelle", callback_data="trade_status"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def send_telegram_signal(message: str, with_buttons: bool = False) -> bool:
    """
    Senkron wrapper - schedule kütüphanesiyle uyumlu.
    """
    markup = get_signal_keyboard() if with_buttons else None
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                result = pool.submit(asyncio.run, _send_message_async(message, markup)).result()
            return result
        else:
            return loop.run_until_complete(_send_message_async(message, markup))
    except RuntimeError:
        return asyncio.run(_send_message_async(message, markup))


def send_startup_message() -> bool:
    """
    Bot başlatıldığında bilgilendirme mesajı gönderir.
    """
    message = """
🤖 *AI Trader Bot Aktif!*

📊 Tarama: BTC/USDT
⏱️ Periyot: Her 15 dakikada bir
📈 Zaman Dilimleri: 15m, 1h, 4h
🔧 Kaynaklar: TradingView-TA + Fear & Greed + Haber Analizi

_Bot çalışmaya başladı. Sinyal oluştuğunda bildirim alacaksınız._
"""
    return send_telegram_signal(message.strip())


def send_error_message(error_text: str) -> bool:
    """
    Hata durumunda bildirim gönderir.
    """
    message = f"""
⚠️ *AI Trader - Hata Bildirimi*

❌ `{error_text}`

_Bot çalışmaya devam ediyor..._
"""
    return send_telegram_signal(message.strip())
