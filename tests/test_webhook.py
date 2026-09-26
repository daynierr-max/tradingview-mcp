#!/usr/bin/env python3
"""
test_webhook.py
───────────────
Simula alertas de TradingView para testear el servidor localmente
sin necesidad de una cuenta Premium ni IP pública.

Uso:
    python tests/test_webhook.py
    python tests/test_webhook.py --host http://tu-vps.com:8000
"""

import argparse
import json
import os
import random
import time
from datetime import datetime, timezone

import httpx

BASE_SCENARIOS = [
    {"ticker": "QQQ", "action": "buy",         "strategy": "ZScore_Scalper_v2", "timeframe": "3"},
    {"ticker": "QQQ", "action": "sell",        "strategy": "ZScore_Scalper_v2", "timeframe": "3"},
    {"ticker": "QQQ", "action": "close_long",  "strategy": "ZScore_Scalper_v2", "timeframe": "3"},
    {"ticker": "SPY", "action": "buy",         "strategy": "EMA_Cross_v1",      "timeframe": "5"},
    {"ticker": "SPY", "action": "sell",        "strategy": "EMA_Cross_v1",      "timeframe": "5"},
]


def build_payload(scenario: dict) -> dict:
    base_price = 485.0 if scenario["ticker"] == "QQQ" else 540.0
    price = round(base_price + random.uniform(-2, 2), 2)
    return {
        **scenario,
        "price":    price,
        "close":    price,
        "high":     round(price + random.uniform(0.1, 0.5), 2),
        "low":      round(price - random.uniform(0.1, 0.5), 2),
        "volume":   random.randint(100_000, 5_000_000),
        "zscore":   round(random.uniform(-2.5, 2.5), 3),
        "bar_time": datetime.now(timezone.utc).isoformat(),
    }


def send_alert(host: str, payload: dict, secret: str) -> dict:
    r = httpx.post(
        f"{host}/webhook",
        json={**payload, "secret": secret},
        timeout=5.0,
    )
    r.raise_for_status()
    return r.json()


def main():
    parser = argparse.ArgumentParser(description="Test TradingView webhook")
    parser.add_argument("--host", default="http://localhost:8000")
    parser.add_argument("--count", type=int, default=10,
                        help="Número de alertas de prueba a enviar")
    parser.add_argument("--secret", default=os.getenv("TV_WEBHOOK_SECRET", ""),
                        help="Secreto del webhook (por defecto, TV_WEBHOOK_SECRET)")
    parser.add_argument("--delay", type=float, default=0.3,
                        help="Segundos entre alertas")
    args = parser.parse_args()

    print(f"\n🧪 Enviando {args.count} alertas de prueba a {args.host}/webhook\n")

    ok = 0
    for i in range(args.count):
        scenario = random.choice(BASE_SCENARIOS)
        payload  = build_payload(scenario)
        try:
            result = send_alert(args.host, payload, args.secret)
            ok += 1
            print(f"  #{i+1:02d} ✅ {payload['ticker']} {payload['action']:<12} "
                  f"price={payload['price']:.2f}  → alert_id={result.get('alert_id')}")
        except Exception as e:
            print(f"  #{i+1:02d} ❌ Error: {e}")
        time.sleep(args.delay)

    print(f"\n✅ Completado: {ok}/{args.count} alertas enviadas con éxito.\n")
    print(f"👉 Revisa el health: {args.host}/health")


if __name__ == "__main__":
    main()
