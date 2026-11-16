
import os
import time
import logging
import requests
from datetime import datetime, timezone

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID", "1090739308")

MIN_MC = 0
MAX_MC = 100000
MIN_LIQUIDITY = 5000
MIN_VOLUME_5M = 500
MIN_BUYS_5M = 5
MAX_AGE_MINUTES = 10
SCAN_INTERVAL = 10

BASE_URL = "https://api.dexscreener.com"
session = requests.Session()
sent_alerts = set()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s"
)

def send_telegram(message):
    if not BOT_TOKEN:
        logging.error("BOT_TOKEN ayarlanmamis")
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    try:
        response = session.post(
            url,
            data={
                "chat_id": CHAT_ID,
                "text": message,
                "disable_web_page_preview": True
            },
            timeout=15
        )
        response.raise_for_status()
    except Exception as error:
        logging.error("Telegram hatasi: %s", error)

def get_profiles():
    url = f"{BASE_URL}/token-profiles/latest/v1"
    response = session.get(url, timeout=20)
    response.raise_for_status()
    return response.json()

def get_pairs(address):
    url = f"{BASE_URL}/token-pairs/v1/solana/{address}"
    response = session.get(url, timeout=20)
    response.raise_for_status()
    return response.json()

def check_token(token):
    address = token.get("tokenAddress")

    if not address or address in sent_alerts:
        return

    pairs = get_pairs(address)

    if not isinstance(pairs, list) or not pairs:
        return

    pair = max(
        pairs,
        key=lambda item: item.get("liquidity", {}).get("usd", 0) or 0
    )

    created = pair.get("pairCreatedAt")
    if not created:
        return

    age_minutes = (
        datetime.now(timezone.utc).timestamp() * 1000 - created
    ) / 60000

    if age_minutes < 0 or age_minutes > MAX_AGE_MINUTES:
        return

    mc = pair.get("marketCap") or pair.get("fdv") or 0
    liquidity = pair.get("liquidity", {}).get("usd", 0) or 0
    volume = pair.get("volume", {}).get("m5", 0) or 0
    buys = pair.get("txns", {}).get("m5", {}).get("buys", 0) or 0
    sells = pair.get("txns", {}).get("m5", {}).get("sells", 0) or 0

    if not MIN_MC <= mc <= MAX_MC:
        return
    if liquidity < MIN_LIQUIDITY:
        return
    if volume < MIN_VOLUME_5M:
        return
    if buys < MIN_BUYS_5M:
        return

    name = pair.get("baseToken", {}).get("name", "Unknown")
    symbol = pair.get("baseToken", {}).get("symbol", "???")
    dex = pair.get("dexId", "Unknown")
    pair_address = pair.get("pairAddress", "")

    score = 50
    if buys > sells:
        score += 15
    if liquidity >= 10000:
        score += 10
    if volume >= 2000:
        score += 10
    score = min(score, 100)

    message = (
        "🚨 ALPHA INTELLIGENCE\n\n"
        f"🪙 {name} ({symbol})\n"
        f"💰 Market Cap: ${mc:,.0f}\n"
        f"💧 Liquidity: ${liquidity:,.0f}\n"
        f"📊 5m Volume: ${volume:,.0f}\n"
        f"🟢 Buys: {buys} | 🔴 Sells: {sells}\n"
        f"⏱ Age: {age_minutes:.1f} minutes\n"
        f"🧠 Rule-based Score: {score}/100\n"
        f"🏦 DEX: {dex}\n\n"
        f"🔗 https://dexscreener.com/solana/{pair_address}\n\n"
        "⚠️ Early signal only. Not financial advice."
    )

    send_telegram(message)
    sent_alerts.add(address)
    logging.info("Alert sent: %s", symbol)

def scan_tokens():
    profiles = get_profiles()

    if not isinstance(profiles, list):
        return

    for token in profiles:
        if token.get("chainId") != "solana":
            continue

        try:
            check_token(token)
            time.sleep(0.2)
        except Exception as error:
            logging.warning("Token scan error: %s", error)

def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable missing")

    send_telegram("🟢 Alpha Intelligence is online!")

    while True:
        try:
            scan_tokens()
            logging.info("Scan complete. Waiting...")
        except Exception:
            logging.exception("General scan error")

        time.sleep(SCAN_INTERVAL)

if __name__ == "__main__":
    main()
