"""
Tests unitarios del servidor: autenticación del webhook y herramientas MCP.

Ejecutar:  python -m unittest discover -s tests -v
"""

import asyncio
import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

SECRET = "test-secret-123"


def load_server(secret: str, allow_insecure: bool = False):
    """Importa server.py con una configuración y una BD temporales."""
    tmp = tempfile.mkdtemp()
    os.environ["TV_DB_PATH"] = str(Path(tmp) / "alerts.db")
    os.environ["TV_WEBHOOK_SECRET"] = secret
    os.environ["TV_ALLOW_INSECURE"] = "1" if allow_insecure else "0"
    import server
    server = importlib.reload(server)
    server.init_db()
    return server


class WebhookAuthTest(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        self.server = load_server(SECRET)
        self.client = TestClient(self.server.webhook_app)

    def test_rechaza_sin_secreto(self):
        r = self.client.post("/webhook", json={"ticker": "QQQ", "action": "buy"})
        self.assertEqual(r.status_code, 401)

    def test_rechaza_secreto_incorrecto(self):
        r = self.client.post("/webhook", json={"ticker": "QQQ", "secret": "otro"})
        self.assertEqual(r.status_code, 401)

    def test_acepta_secreto_en_body_y_no_lo_guarda(self):
        r = self.client.post("/webhook", json={"ticker": "QQQ", "action": "buy",
                                               "price": 480.5, "secret": SECRET})
        self.assertEqual(r.status_code, 200)
        stored = self.server.query_alerts(ticker="QQQ")[0]
        self.assertNotIn(SECRET, stored["raw_payload"])

    def test_acepta_hmac_en_header(self):
        import hashlib, hmac
        body = json.dumps({"ticker": "SPY", "action": "sell"}).encode()
        sig = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
        r = self.client.post("/webhook", content=body, headers={"x-tv-secret": sig})
        self.assertEqual(r.status_code, 200)


class FailClosedTest(unittest.TestCase):
    def test_secreto_por_defecto_rechaza_todo(self):
        from fastapi.testclient import TestClient
        server = load_server(secret="changeme_secret_2024")
        r = TestClient(server.webhook_app).post("/webhook", json={"ticker": "QQQ"})
        self.assertEqual(r.status_code, 401)

    def test_modo_inseguro_explicito_para_desarrollo(self):
        from fastapi.testclient import TestClient
        server = load_server(secret="changeme_secret_2024", allow_insecure=True)
        r = TestClient(server.webhook_app).post("/webhook", json={"ticker": "QQQ"})
        self.assertEqual(r.status_code, 200)

    def test_run_webhook_no_arranca_sin_secreto(self):
        server = load_server(secret="changeme_secret_2024")
        with self.assertRaises(SystemExit):
            server.run_webhook()


class McpToolsTest(unittest.TestCase):
    def setUp(self):
        self.server = load_server(SECRET)
        for action in ["buy", "buy", "sell", "close_long"]:
            self.server.insert_alert({"ticker": "QQQ", "action": action,
                                      "price": 480.0, "strategy": "ZScore"})
        self.server.insert_alert({"ticker": "SPY", "action": "buy", "price": 540.0})

    def run_tool(self, coro):
        return json.loads(asyncio.run(coro))

    def test_get_alerts_filtra_por_ticker(self):
        out = self.run_tool(self.server.tv_get_alerts(self.server.GetAlertsInput(ticker="qqq")))
        self.assertEqual(out["count"], 4)

    def test_get_stats_cuenta_por_accion(self):
        out = self.run_tool(self.server.tv_get_stats(self.server.GetStatsInput(ticker="QQQ")))
        self.assertEqual(out["total_alerts"], 4)
        self.assertEqual(out["by_action"]["buy"], 2)

    def test_analyze_signals_ratio(self):
        out = self.run_tool(self.server.tv_analyze_signals(
            self.server.AnalyzeSignalsInput(ticker="QQQ", last_n=10)))
        self.assertEqual(out["signal_counts"], {"buy": 2, "sell": 1, "other": 1})
        self.assertEqual(out["buy_sell_ratio"], 2.0)

    def test_analyze_signals_sin_datos(self):
        out = self.run_tool(self.server.tv_analyze_signals(
            self.server.AnalyzeSignalsInput(ticker="AAPL")))
        self.assertIn("error", out)


if __name__ == "__main__":
    unittest.main()
