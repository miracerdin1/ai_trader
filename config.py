"""
Yapılandırma modülü - Tüm sabitler ve ortam değişkenleri burada tanımlanır.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─── Telegram ───────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

# ─── İşlem Çifti ────────────────────────────────────────────────────────────────
SYMBOL = "BTCUSDT"                  # TradingView formatı
CCXT_SYMBOL = "BTC/USDT"           # ccxt formatı
EXCHANGE_NAME = "binance"           # ccxt borsa adı

# ─── Zaman Dilimleri ────────────────────────────────────────────────────────────
TIMEFRAMES = {
    "15m": "Interval.INTERVAL_15_MINUTES",
    "1h":  "Interval.INTERVAL_1_HOUR",
    "4h":  "Interval.INTERVAL_4_HOURS",
}

# ─── Teknik Analiz Parametreleri ────────────────────────────────────────────────
EMA_FAST = 20
EMA_SLOW = 50
RSI_PERIOD = 14
ATR_PERIOD = 14

RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30

# ─── Sinyal Parametreleri ───────────────────────────────────────────────────────
# ATR çarpanları: stop-loss ve hedefler
SL_ATR_MULTIPLIER = 1.5       # Stop-Loss = 1.5 × ATR
TP1_ATR_MULTIPLIER = 1.0      # TP1 = 1 × ATR
TP2_ATR_MULTIPLIER = 2.0      # TP2 = 2 × ATR
TP3_ATR_MULTIPLIER = 3.0      # TP3 = 3 × ATR

# Minimum güven skoru (10 üzerinden) sinyal göndermek için
MIN_CONFIDENCE_SCORE = 5

# ─── Tarama Sıklığı ────────────────────────────────────────────────────────────
SCAN_INTERVAL_MINUTES = 15

# ─── Dosya Yolları ──────────────────────────────────────────────────────────────
SIGNALS_LOG_FILE = "signals_log.csv"

# ─── API URL'leri ───────────────────────────────────────────────────────────────
FEAR_GREED_API = "https://api.alternative.me/fng/?limit=1"
CRYPTOPANIC_RSS = "https://cryptopanic.com/news/rss/"
