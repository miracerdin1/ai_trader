"""
Teknik Analiz modülü
- pandas_ta ile EMA20, EMA50, RSI, ATR hesaplama
- Sinyal mantığı: EMA kesişimleri + RSI + TradingView özet
"""

import pandas as pd
import pandas_ta as ta
from loguru import logger

import config
from data_fetcher import get_ohlcv_data


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    DataFrame'e teknik göstergeleri ekler: EMA20, EMA50, RSI, ATR.
    """
    df = df.copy()

    df["ema20"] = ta.ema(df["close"], length=config.EMA_FAST)
    df["ema50"] = ta.ema(df["close"], length=config.EMA_SLOW)
    df["rsi"] = ta.rsi(df["close"], length=config.RSI_PERIOD)
    df["atr"] = ta.atr(df["high"], df["low"], df["close"], length=config.ATR_PERIOD)

    return df


def analyze_with_pandas_ta(timeframe: str = "1h") -> dict | None:
    """
    ccxt + pandas_ta tabanlı yedek analiz.
    TradingView-TA başarısız olursa bu kullanılır.

    Returns:
        {
            "close": float,
            "ema20": float,
            "ema50": float,
            "rsi": float,
            "atr": float,
            "ema_signal": "LONG" | "SHORT" | "NEUTRAL",
            "rsi_signal": "OVERSOLD" | "OVERBOUGHT" | "NEUTRAL",
        }
    """
    df = get_ohlcv_data(timeframe=timeframe, limit=100)
    if df is None or df.empty:
        return None

    df = compute_indicators(df)
    last = df.iloc[-1]

    # EMA kesişim sinyali
    if pd.notna(last["ema20"]) and pd.notna(last["ema50"]):
        if last["ema20"] > last["ema50"]:
            ema_signal = "LONG"
        elif last["ema20"] < last["ema50"]:
            ema_signal = "SHORT"
        else:
            ema_signal = "NEUTRAL"
    else:
        ema_signal = "NEUTRAL"

    # RSI sinyali
    rsi_val = last.get("rsi", 50)
    if pd.notna(rsi_val):
        if rsi_val < config.RSI_OVERSOLD:
            rsi_signal = "OVERSOLD"
        elif rsi_val > config.RSI_OVERBOUGHT:
            rsi_signal = "OVERBOUGHT"
        else:
            rsi_signal = "NEUTRAL"
    else:
        rsi_signal = "NEUTRAL"

    result = {
        "close": round(float(last["close"]), 2),
        "ema20": round(float(last["ema20"]), 2) if pd.notna(last["ema20"]) else None,
        "ema50": round(float(last["ema50"]), 2) if pd.notna(last["ema50"]) else None,
        "rsi": round(float(rsi_val), 2) if pd.notna(rsi_val) else None,
        "atr": round(float(last["atr"]), 2) if pd.notna(last["atr"]) else None,
        "ema_signal": ema_signal,
        "rsi_signal": rsi_signal,
    }

    logger.info(f"[pandas_ta] {timeframe} → EMA: {ema_signal}, RSI: {rsi_signal} ({rsi_val:.1f})")
    return result


def evaluate_tradingview_signals(tv_data: dict) -> dict:
    """
    TradingView-TA verilerini değerlendirip puan ve yön hesaplar.

    Returns:
        {
            "direction": "LONG" | "SHORT" | None,
            "score": float (0-10 arası),
            "reasons": [str],
            "close": float,
            "atr": float,
            "rsi": float,
        }
    """
    score = 0.0
    reasons = []
    direction = None

    long_votes = 0
    short_votes = 0
    valid_tfs = 0

    close_price = None
    atr_value = None
    rsi_value = None

    for tf_name, data in tv_data.items():
        if data is None:
            continue

        valid_tfs += 1
        rec = data["recommendation"]

        # En son geçerli verileri sakla
        if data.get("close"):
            close_price = data["close"]
        if data.get("atr"):
            atr_value = data["atr"]
        if data.get("rsi"):
            rsi_value = data["rsi"]

        # ─── Recommendation puanlama ────────────────────────────────────
        if rec == "STRONG_BUY":
            long_votes += 2
            score += 2.0
            reasons.append(f"📈 {tf_name}: STRONG BUY sinyali")
        elif rec == "BUY":
            long_votes += 1
            score += 1.0
            reasons.append(f"📈 {tf_name}: BUY sinyali")
        elif rec == "STRONG_SELL":
            short_votes += 2
            score += 2.0
            reasons.append(f"📉 {tf_name}: STRONG SELL sinyali")
        elif rec == "SELL":
            short_votes += 1
            score += 1.0
            reasons.append(f"📉 {tf_name}: SELL sinyali")

        # ─── EMA Kesişim kontrolü ───────────────────────────────────────
        ema20 = data.get("ema20")
        ema50 = data.get("ema50")
        if ema20 and ema50:
            if ema20 > ema50:
                long_votes += 1
                reasons.append(f"✅ {tf_name}: EMA20 > EMA50 (Yükseliş)")
            elif ema20 < ema50:
                short_votes += 1
                reasons.append(f"⛔ {tf_name}: EMA20 < EMA50 (Düşüş)")

        # ─── RSI kontrolü ───────────────────────────────────────────────
        rsi = data.get("rsi")
        if rsi:
            if rsi < config.RSI_OVERSOLD:
                long_votes += 1
                score += 0.5
                reasons.append(f"💚 {tf_name}: RSI={rsi:.1f} (Aşırı Satım → Alım fırsatı)")
            elif rsi > config.RSI_OVERBOUGHT:
                short_votes += 1
                score += 0.5
                reasons.append(f"💔 {tf_name}: RSI={rsi:.1f} (Aşırı Alım → Satış fırsatı)")

    # ─── Yön belirleme ──────────────────────────────────────────────────────
    if long_votes > short_votes and long_votes >= 3:
        direction = "LONG"
    elif short_votes > long_votes and short_votes >= 3:
        direction = "SHORT"
    else:
        direction = None  # Belirsiz, sinyal gönderilmez

    # Skoru 10 üzerinden normalize et (teknik kısmı max 7 puan)
    if valid_tfs > 0:
        score = min(score, 7.0)
    else:
        score = 0.0

    return {
        "direction": direction,
        "score": round(score, 1),
        "reasons": reasons,
        "close": close_price,
        "atr": atr_value,
        "rsi": rsi_value,
    }
