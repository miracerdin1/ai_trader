"""
AI Trader - Risk Yönetimli İnteraktif Bot v1.3
════════════════════════════════════════════════════════════════
"""

import sys
import io
import asyncio
from datetime import datetime
from loguru import logger
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, 
    CallbackQueryHandler, 
    MessageHandler, 
    ContextTypes, 
    filters
)

import config
from signal_generator import generate_signal, format_telegram_message
from telegram_bot import send_startup_message, get_signal_keyboard
from signal_logger import (
    log_signal, 
    log_trade_action, 
    get_last_open_trade, 
    get_last_signal_levels
)
from data_fetcher import get_current_price

# Windows konsol encoding düzeltmesi
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Global Durumlar
USER_STATES = {}
ACTIVE_TRADES = {} # {user_id: {symbol, entry_price, amount, sl, tp1, tp2, tp3, direction}}

# ─── Loguru yapılandırma ────────────────────────────────────────────────────────
logger.add(
    "ai_trader_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="7 days",
    level="INFO",
    encoding="utf-8",
    format="{time:HH:mm:ss} | {level: <8} | {message}",
)


async def scan_job(context: ContextTypes.DEFAULT_TYPE):
    """15 dakikalık ana tarama işi."""
    try:
        signal = generate_signal()
        if signal is None: return

        message = format_telegram_message(signal)
        await context.bot.send_message(
            chat_id=config.TELEGRAM_CHAT_ID,
            text=message,
            parse_mode="Markdown",
            reply_markup=get_signal_keyboard()
        )
        log_signal(signal)
    except Exception as e:
        logger.error(f"❌ Tarama hatası: {e}")


async def price_monitor_job(context: ContextTypes.DEFAULT_TYPE):
    """Aktif işlemleri her 30 saniyede bir kontrol eden 'Gözcü'."""
    if not ACTIVE_TRADES: return
    
    current_price = get_current_price()
    if not current_price: return
    
    for user_id, trade in list(ACTIVE_TRADES.items()):
        symbol = trade["symbol"]
        sl = trade["sl"]
        tps = [trade["tp1"], trade["tp2"], trade["tp3"]]
        direction = trade["direction"]
        entry_price = trade["entry_price"]
        amount = trade["amount"]
        
        hit = False
        msg = ""
        
        # Kar/Zarar Durumu
        if direction == "LONG":
            if current_price <= sl:
                hit = True
                msg = f"🛑 *STOP-LOSS VURULDU*\nİşlem zarar kes ile kapatıldı."
            elif current_price >= tps[0]: # En azından TP1
                hit = True
                msg = f"🎯 *HEDEF (TP) VURULDU*\nKâr realize edildi!"
        else: # SHORT
            if current_price >= sl:
                hit = True
                msg = f"🛑 *STOP-LOSS VURULDU*\nİşlem zarar kes ile kapatıldı."
            elif current_price <= tps[0]:
                hit = True
                msg = f"🎯 *HEDEF (TP) VURULDU*\nKâr realize edildi!"
                
        if hit:
            # PnL Hesapla
            price_diff_pct = ((current_price - entry_price) / entry_price) * 100
            if direction == "SHORT": price_diff_pct *= -1
            pnl_usdt = (amount * price_diff_pct) / 100
            
            log_trade_action(symbol, "OTOMATİK KAPANIŞ", current_price, amount=amount, pnl=pnl_usdt, note=msg)
            
            final_msg = (
                f"{msg}\n\n"
                f"🪙 `{symbol}`\n"
                f"📊 *PnL:* `{pnl_usdt:+,.2f} USDT` (%{price_diff_pct:+.2f})\n"
                f"📍 Çıkış Fiyatı: `${current_price:,.2f}`"
            )
            
            await context.bot.send_message(chat_id=config.TELEGRAM_CHAT_ID, text=final_msg, parse_mode="Markdown")
            del ACTIVE_TRADES[user_id] # İşlemi listeden çıkar


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Buton tıklamalarını işler."""
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    if query.data == "trade_enter":
        levels = get_last_signal_levels(config.SYMBOL)
        if not levels:
            await query.message.reply_text("⚠️ Hata: Son sinyal seviyeleri bulunamadı.")
            return
            
        USER_STATES[user_id] = {
            "action": "awaiting_amount", 
            "price": get_current_price(),
            "levels": levels
        }
        await context.bot.send_message(
            chat_id=config.TELEGRAM_CHAT_ID,
            text=f"📥 *GİRİŞ SİNYALİ*\n💰 Fiyat: `${USER_STATES[user_id]['price']:,.2f}`\n\n👇 İşlem miktarını (USDT) yazın:",
            parse_mode="Markdown"
        )
    
    elif query.data == "trade_exit":
        if user_id in ACTIVE_TRADES:
            current_price = get_current_price()
            trade = ACTIVE_TRADES[user_id]
            
            price_diff_pct = ((current_price - trade["entry_price"]) / trade["entry_price"]) * 100
            if trade["direction"] == "SHORT": price_diff_pct *= -1
            pnl_usdt = (trade["amount"] * price_diff_pct) / 100
            
            log_trade_action(trade["symbol"], "MANUEL ÇIKIŞ", current_price, amount=trade["amount"], pnl=pnl_usdt)
            
            await context.bot.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                text=f"📤 *İŞLEM MANUEL KAPATILDI*\n📊 PnL: `{pnl_usdt:+,.2f} USDT` (%{price_diff_pct:+.2f})",
                parse_mode="Markdown"
            )
            del ACTIVE_TRADES[user_id]
        else:
            await query.message.reply_text("⚠️ Aktif işlem bulunamadı.")

    elif query.data == "trade_status":
        curr = get_current_price()
        txt = f"📊 *DURUM*\n🪙 `{config.SYMBOL}`: `${curr:,.2f}`"
        if user_id in ACTIVE_TRADES:
            t = ACTIVE_TRADES[user_id]
            diff = ((curr - t["entry_price"]) / t["entry_price"]) * 100
            if t["direction"] == "SHORT": diff *= -1
            txt += f"\n📉 Giriş: `${t['entry_price']:,.2f}`\n💰 Güncel PnL: `%{diff:+.2f}`"
            
        await context.bot.send_message(chat_id=config.TELEGRAM_CHAT_ID, text=txt, parse_mode="Markdown")


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Miktar girişini işler ve takibi başlatır."""
    user_id = update.effective_user.id
    if user_id in USER_STATES and USER_STATES[user_id]["action"] == "awaiting_amount":
        try:
            amount = float(update.message.text.replace(",", "."))
            state = USER_STATES[user_id]
            levels = state["levels"]
            
            # İşlemi Aktif Listeye Ekle (TAKİP BAŞLAR)
            ACTIVE_TRADES[user_id] = {
                "symbol": config.SYMBOL,
                "entry_price": state["price"],
                "amount": amount,
                "direction": levels["direction"],
                "sl": levels["stop_loss"],
                "tp1": levels["tp1"],
                "tp2": levels["tp2"],
                "tp3": levels["tp3"]
            }
            
            log_trade_action(config.SYMBOL, "GİRİŞ", state["price"], amount=amount)
            
            await update.message.reply_text(
                f"✅ *İŞLEM AKTİF VE TAKİPTE*\n\n"
                f"📍 Giriş: `${state['price']:,.2f}`\n"
                f"🛑 Stop-Loss: `${levels['stop_loss']:,.2f}`\n"
                f"🎯 Hedef 1: `${levels['tp1']:,.2f}`\n\n"
                f"🕵️ Bot fiyatı izliyor, hedeflere ulaşıldığında bildirim gönderecek.",
                parse_mode="Markdown"
            )
            del USER_STATES[user_id]
            
        except ValueError:
            await update.message.reply_text("❌ Geçerli bir sayı girin.")


async def main():
    """Ana giriş noktası."""
    print("""
    +======================================================+
    |           AI TRADER BOT v1.3 (GUARDIAN)              |
    |   7/24 Otomatik Fiyat & Risk Takibi Aktif            |
    +======================================================+
    """)

    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        logger.error("❌ Telegram bilgileri eksik! .env dosyasını kontrol edin.")
        return

    # PythonAnywhere Proxy Ayarı
    import os
    from telegram.request import HTTPXRequest
    trequest = None
    if "PYTHONANYWHERE_DOMAIN" in os.environ:
        logger.info("🌐 PythonAnywhere algılandı, proxy aktifleştiriliyor...")
        trequest = HTTPXRequest(proxy="http://proxy.server:3128")

    # Uygulamayı oluştur
    app = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).request(trequest).build()

    # Handlers
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), message_handler))

    # Joblar
    jq = app.job_queue
    jq.run_repeating(scan_job, interval=config.SCAN_INTERVAL_MINUTES * 60, first=10)
    jq.run_repeating(price_monitor_job, interval=30, first=15) # 30 saniyede bir fiyat takibi

    logger.info("🚀 Guardian Bot başlatıldı.")
    send_startup_message()

    async with app:
        await app.initialize()
        await app.start()
        await app.updater.start_polling()
        while True: await asyncio.sleep(1)

if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: logger.info("🛑 Bot durduruldu.")
