"""
Veri çekme modülü
- TradingView-TA üzerinden sinyal analizi
- ccxt üzerinden halka açık mum (OHLCV) verileri
"""

import os
from tradingview_ta import TA_Handler, Interval
import ccxt
import pandas as pd
from loguru import logger

import config


# ─── TradingView-TA Interval Eşlemesi ───────────────────────────────────────────
TV_INTERVALS = {
    "15m": Interval.INTERVAL_15_MINUTES,
    "1h":  Interval.INTERVAL_1_HOUR,
    "4h":  Interval.INTERVAL_4_HOURS,
}


def get_tradingview_analysis(symbol: str = config.SYMBOL) -> dict:
    """
    TradingView-TA kullanarak birden fazla zaman diliminde teknik analiz çeker.
    """
    results = {}

    for tf_name, tv_interval in TV_INTERVALS.items():
        try:
            handler = TA_Handler(
                symbol=symbol,
                screener="crypto",
                exchange="BINANCE",
                interval=tv_interval,
            )
            analysis = handler.get_analysis()

            results[tf_name] = {
                "recommendation": analysis.summary["RECOMMENDATION"],
                "buy_count": analysis.summary["BUY"],
                "sell_count": analysis.summary["SELL"],
                "neutral_count": analysis.summary["NEUTRAL"],
                "rsi": analysis.indicators.get("RSI", None),
                "ema20": analysis.indicators.get("EMA20", None),
                "ema50": analysis.indicators.get("EMA50", None),
                "close": analysis.indicators.get("close", None),
                "atr": analysis.indicators.get("ATR", None),
                "oscillators": analysis.oscillators["RECOMMENDATION"],
                "moving_averages": analysis.moving_averages["RECOMMENDATION"],
            }
            logger.info(f"[TradingView] {tf_name}: {results[tf_name]['recommendation']}")

        except Exception as e:
            logger.error(f"[TradingView] {tf_name} analizi başarısız: {e}")
            results[tf_name] = None

    return results


def get_exchange():
    """PythonAnywhere uyumlu ccxt exchange nesnesi oluşturur."""
    options = {"enableRateLimit": True}
    if "PYTHONANYWHERE_DOMAIN" in os.environ:
        options["proxies"] = {
            "http": "http://proxy.server:3128",
            "https": "http://proxy.server:3128",
        }
    return ccxt.binance(options)


def get_ohlcv_data(
    symbol: str = config.CCXT_SYMBOL,
    timeframe: str = "1h",
    limit: int = 100,
) -> pd.DataFrame | None:
    """
    ccxt üzerinden Binance'den halka açık OHLCV verisi çeker.
    API key gerektirmez.
    """
    try:
        exchange = get_exchange()
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)

        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)

        logger.info(f"[ccxt] {symbol} {timeframe} → {len(df)} mum verisi çekildi.")
        return df

    except Exception as e:
        logger.error(f"[ccxt] OHLCV veri çekme hatası: {e}")
        return None


def get_current_price(symbol: str = config.CCXT_SYMBOL) -> float | None:
    """
    ccxt üzerinden anlık fiyat çeker (ticker).
    """
    try:
        exchange = get_exchange()
        ticker = exchange.fetch_ticker(symbol)
        price = ticker["last"]
        logger.info(f"[ccxt] {symbol} anlık fiyat: ${price:,.2f}")
        return price
    except Exception as e:
        logger.error(f"[ccxt] Fiyat çekme hatası: {e}")
        return None
