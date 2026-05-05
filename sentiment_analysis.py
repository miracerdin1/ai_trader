"""
Duygu Analizi (Sentiment) modülü
- Alternative.me Fear & Greed Index (API key gerektirmez)
- CryptoPanic RSS haberleri ile piyasa duyarlılığı
"""

import os
import re
import requests
import xml.etree.ElementTree as ET
from loguru import logger

import config


def get_requests_options():
    """PythonAnywhere uyumlu requests ayarları döner."""
    options = {"timeout": 10}
    if "PYTHONANYWHERE_DOMAIN" in os.environ:
        options["proxies"] = {
            "http": "http://proxy.server:3128",
            "https": "http://proxy.server:3128",
        }
    # Bot engellemesini aşmak için User-Agent ekle
    options["headers"] = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    return options


def get_fear_greed_index() -> dict | None:
    """
    Alternative.me Fear & Greed Index API'sinden veri çeker.
    """
    try:
        opts = get_requests_options()
        response = requests.get(config.FEAR_GREED_API, **opts)
        response.raise_for_status()
        data = response.json()

        if "data" not in data or len(data["data"]) == 0:
            logger.warning("[Sentiment] Fear & Greed API boş yanıt döndü.")
            return None

        entry = data["data"][0]
        value = int(entry["value"])
        label = entry["value_classification"]

        if value <= 20:
            sentiment_score = 3.0
            description = f"🟢 Aşırı Korku ({value}/100) → Tepki alımı beklentisi yüksek"
        elif value <= 35:
            sentiment_score = 2.0
            description = f"🟡 Korku ({value}/100) → Alım fırsatı olabilir"
        elif value <= 55:
            sentiment_score = 0.5
            description = f"⚪ Nötr ({value}/100) → Piyasa kararsız"
        elif value <= 75:
            sentiment_score = 1.5
            description = f"🟠 Açgözlülük ({value}/100) → Dikkatli olunmalı"
        else:
            sentiment_score = 2.5
            description = f"🔴 Aşırı Açgözlülük ({value}/100) → Düzeltme riski var"

        return {
            "value": value,
            "label": label,
            "sentiment_score": sentiment_score,
            "description": description,
            "bias": "LONG" if value <= 35 else ("SHORT" if value >= 65 else "NEUTRAL"),
        }

    except Exception as e:
        logger.error(f"[Sentiment] Fear & Greed API hatası: {e}")
        return None


def get_crypto_news_sentiment() -> dict:
    """
    CryptoPanic RSS beslemesinden haber başlıklarını çeker.
    """
    positive_keywords = ["bull", "surge", "rally", "pump", "breakout", "soar", "gain", "recovery", "adoption"]
    negative_keywords = ["bear", "crash", "dump", "plunge", "hack", "ban", "regulation", "sell-off", "scam"]

    try:
        opts = get_requests_options()
        response = requests.get(config.CRYPTOPANIC_RSS, **opts)
        response.raise_for_status()

        # XML parse
        try:
            root = ET.fromstring(response.content)
            titles_raw = [item.find("title").text for item in root.findall(".//item")[:15] if item.find("title") is not None]
        except ET.ParseError:
            titles_raw = re.findall(r"<title>(?:<![CDATA[)?(.*?)(?:]]>)?</title>", response.text)
            titles_raw = [t.strip() for t in titles_raw[:15] if t.strip()]

        positive_count = 0
        negative_count = 0
        headlines = []

        for raw_title in titles_raw:
            title = raw_title.lower()
            headlines.append(raw_title)
            if any(kw in title for kw in positive_keywords): positive_count += 1
            if any(kw in title for kw in negative_keywords): negative_count += 1

        if positive_count > negative_count:
            overall, news_score = "Pozitif", 0.5
        elif negative_count > positive_count:
            overall, news_score = "Negatif", 0.5
        else:
            overall, news_score = "Nötr", 0.0

        logger.info(f"[Sentiment] Haberler: +{positive_count} / -{negative_count} → {overall}")
        return {
            "positive_count": positive_count,
            "negative_count": negative_count,
            "overall": overall,
            "headlines": headlines[:10],
            "news_score": news_score,
        }

    except Exception as e:
        logger.warning(f"[Sentiment] Haber çekme hatası (devam ediliyor): {e}")
        return {"positive_count": 0, "negative_count": 0, "overall": "Nötr", "headlines": [], "news_score": 0.0}


def get_combined_sentiment() -> dict:
    """Fear & Greed + Haber duyarlılığını birleştirir."""
    fg = get_fear_greed_index()
    news = get_crypto_news_sentiment()
    total_score = (fg["sentiment_score"] if fg else 0) + news["news_score"]
    bias = fg["bias"] if fg else "NEUTRAL"
    summary = (fg["description"] if fg else "") + (" | Haberler: " + news["overall"] if news["overall"] != "Nötr" else "")
    
    return {
        "fear_greed": fg,
        "news": news,
        "total_sentiment_score": round(min(total_score, 3.0), 1),
        "sentiment_bias": bias,
        "summary": summary or "Duyarlılık verisi yok",
    }
