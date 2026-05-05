"""
Sinyal loglama modülü
- Tüm sinyalleri signals_log.csv dosyasına kaydeder
- Performans takibi için kullanılır
"""

import os
import csv
from datetime import datetime, timezone
from loguru import logger

import config


CSV_HEADERS = [
    "timestamp",
    "symbol",
    "direction",
    "entry_price",
    "stop_loss",
    "tp1",
    "tp2",
    "tp3",
    "confidence_score",
    "fear_greed_value",
    "fear_greed_label",
    "news_sentiment",
    "rsi",
    "atr",
    "reasons",
    "fallback_used",
]


def _ensure_csv_exists():
    """CSV dosyası yoksa başlık satırıyla oluşturur."""
    if not os.path.exists(config.SIGNALS_LOG_FILE):
        with open(config.SIGNALS_LOG_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(CSV_HEADERS)
        logger.info(f"📁 {config.SIGNALS_LOG_FILE} oluşturuldu.")


def log_signal(signal: dict) -> bool:
    """
    Sinyal bilgilerini CSV dosyasına yazar.

    Args:
        signal: signal_generator.generate_signal() çıktısı

    Returns:
        True başarılıysa, False değilse
    """
    try:
        _ensure_csv_exists()

        row = [
            signal.get("timestamp", datetime.now(timezone.utc).isoformat()),
            signal.get("symbol", config.SYMBOL),
            signal.get("direction", ""),
            signal.get("entry_price", ""),
            signal.get("stop_loss", ""),
            signal.get("tp1", ""),
            signal.get("tp2", ""),
            signal.get("tp3", ""),
            signal.get("confidence_score", ""),
            signal.get("fear_greed_value", ""),
            signal.get("fear_greed_label", ""),
            signal.get("news_sentiment", ""),
            signal.get("rsi", ""),
            signal.get("atr", ""),
            " | ".join(signal.get("reasons", [])),
            signal.get("fallback_used", False),
        ]

        with open(config.SIGNALS_LOG_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(row)

        logger.info(f"💾 Sinyal {config.SIGNALS_LOG_FILE} dosyasına kaydedildi.")
        return True

    except Exception as e:
        logger.error(f"❌ CSV kayıt hatası: {e}")
        return False


TRADES_LOG_FILE = "trades_log.csv"
TRADE_HEADERS = ["timestamp", "symbol", "action", "price", "amount", "pnl", "note"]

def log_trade_action(symbol: str, action: str, price: float, amount: float = 0.0, pnl: float = 0.0, note: str = ""):
    """Kullanıcının giriş/çıkış işlemlerini miktar ve PnL ile kaydeder."""
    try:
        file_exists = os.path.exists(TRADES_LOG_FILE)
        with open(TRADES_LOG_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(TRADE_HEADERS)
            writer.writerow([
                datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                symbol,
                action,
                price,
                amount,
                round(pnl, 2),
                note
            ])
        logger.success(f"📝 {action} kaydedildi: ${price} (Miktar: {amount}, PnL: {pnl})")
    except Exception as e:
        logger.error(f"❌ İşlem kayıt hatası: {e}")


def get_last_open_trade(symbol: str) -> dict | None:
    """En son yapılan 'GİRİŞ' işlemini bulur."""
    try:
        if not os.path.exists(TRADES_LOG_FILE):
            return None
            
        with open(TRADES_LOG_FILE, "r", encoding="utf-8") as f:
            reader = list(csv.DictReader(f))
            # Tersten tara (en güncelden eskiye)
            for row in reversed(reader):
                if row["symbol"] == symbol and row["action"] == "GİRİŞ":
                    return {
                        "price": float(row["price"]),
                        "amount": float(row["amount"])
                    }
        return None
    except Exception as e:
        logger.error(f"❌ Son işlem okunurken hata: {e}")
        return None


def get_last_signal_levels(symbol: str) -> dict | None:
    """En son üretilen sinyaldeki SL ve TP seviyelerini getirir."""
    try:
        if not os.path.exists(config.SIGNALS_LOG_FILE):
            return None
            
        with open(config.SIGNALS_LOG_FILE, "r", encoding="utf-8") as f:
            reader = list(csv.DictReader(f))
            for row in reversed(reader):
                if row["symbol"] == symbol:
                    return {
                        "direction": row["direction"],
                        "stop_loss": float(row["stop_loss"]),
                        "tp1": float(row["tp1"]),
                        "tp2": float(row["tp2"]),
                        "tp3": float(row["tp3"]),
                    }
        return None
    except Exception as e:
        logger.error(f"❌ Sinyal seviyeleri okunurken hata: {e}")
        return None


def get_signal_count() -> int:
    """Toplam kaydedilmiş sinyal sayısını döndürür."""
    try:
        if not os.path.exists(config.SIGNALS_LOG_FILE):
            return 0
        with open(config.SIGNALS_LOG_FILE, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            return max(sum(1 for _ in reader) - 1, 0)  # Başlık satırını çıkar
    except Exception:
        return 0
