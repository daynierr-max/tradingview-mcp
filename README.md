# TradingView MCP Server

Servidor **MCP (Model Context Protocol)** que recibe alertas de TradingView por webhook, las guarda en SQLite y las expone como herramientas para que un asistente de IA (Claude) consulte y analice las señales de una estrategia Pine Script.

```
TradingView (alerta Pine Script)
        │  HTTPS POST /webhook  (secreto compartido)
        ▼
FastAPI ──► SQLite (alerts.db)
                 ▲
                 │  consultas de solo lectura
FastMCP ─────────┘ ◄── Claude: tv_get_alerts · tv_get_stats · tv_analyze_signals
```

**Stack:** Python · FastAPI · FastMCP (SDK oficial `mcp`) · SQLite · Pydantic · Pine Script v6

## Por qué lo construí

Quería que un asistente de IA pudiera responder preguntas sobre mis estrategias de trading ("¿cuántas señales de compra generó hoy QQQ?", "¿esta estrategia está sobre-señalizando?") a partir de **datos reales y trazables**, sin copiar y pegar capturas. MCP permite dar al modelo herramientas acotadas y de solo lectura en lugar de acceso libre a los datos.

## Herramientas MCP

| Herramienta | Qué hace | Tipo |
|---|---|---|
| `tv_get_alerts` | Lista alertas con filtros (ticker, acción, estrategia) y paginación | Solo lectura |
| `tv_get_stats` | Totales, desglose buy/sell y última señal | Solo lectura |
| `tv_analyze_signals` | Frecuencia, ratio buy/sell, rango de precios, tiempo medio entre señales y diagnóstico automático | Solo lectura |

Todas las entradas se validan con modelos Pydantic (`extra="forbid"`, límites de rango) y las consultas SQL son parametrizadas.

## Seguridad

- **Autenticación que falla en cerrado:** si `TV_WEBHOOK_SECRET` no está configurado, el webhook rechaza todas las peticiones y el servidor no arranca. `TV_ALLOW_INSECURE=1` existe solo para pruebas locales.
- **Dos modos de autenticación:**
  - campo `secret` dentro del JSON: necesario porque TradingView **no permite cabeceras personalizadas** en los webhooks;
  - cabecera `x-tv-secret` con HMAC-SHA256 del cuerpo, para clientes propios.
- Comparaciones en tiempo constante (`hmac.compare_digest`).
- **El secreto nunca se guarda** en la base de datos.
- Herramientas MCP marcadas como `readOnlyHint`: el modelo no puede modificar ni borrar datos.
- Secretos fuera del repositorio (`.env` ignorado). En mi equipo, el secreto se lee del Llavero de macOS mediante un script envoltorio, no de un fichero en texto plano.
- Allowlist opcional de las IPs oficiales de TradingView para producción.

## Tests

```bash
python -m unittest discover -s tests -p "test_server.py" -v
```

11 tests: autenticación (sin secreto, secreto incorrecto, secreto en el cuerpo, HMAC en cabecera), comportamiento de fallo en cerrado y las tres herramientas MCP. Los tests detectaron un bug real en `tv_get_stats` (fallaba siempre que había alertas guardadas), ya corregido.

`tests/test_webhook.py` es un simulador que envía alertas falsas a un servidor en ejecución.

## Instalación

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Genera un secreto fuerte y ponlo en TV_WEBHOOK_SECRET:
python -c "import secrets; print(secrets.token_hex(32))"

python src/server.py            # webhook en :8000
python tests/test_webhook.py    # envía 10 alertas de prueba
python src/server.py mcp        # servidor MCP (stdio) para Claude
```

Para registrar el servidor en Claude Desktop, consulta `docs/claude_desktop_config.json`.

## Conectar TradingView

1. Carga `scripts/strategy_template.pine` en TradingView y adapta la lógica de señal.
2. En el campo **Webhook secret** del script, pon el mismo valor que en `TV_WEBHOOK_SECRET`.
3. Crea una alerta con la URL `https://TU_DOMINIO/webhook`. TradingView exige HTTPS en el puerto 443, así que expón el servidor con Cloudflare Tunnel, ngrok o un proxy inverso con TLS.

Formato del mensaje:

```json
{
  "secret": "…",
  "ticker": "QQQ",
  "action": "buy",
  "strategy": "ZScore_Scalper_v2",
  "price": 484.50,
  "timeframe": "3",
  "zscore": -1.72,
  "bar_time": "2026-06-09T14:30:00Z"
}
```

## Ejemplos de uso con Claude

- "Muéstrame las últimas 20 alertas de QQQ"
- "Analiza la calidad de las señales de ZScore_Scalper_v2"
- "¿Cuántas señales de compra y de venta hubo hoy en SPY?"

## Próximos pasos

- Herramienta `tv_compare_strategies` para comparar estrategias
- Docker Compose para desplegar en un VPS
- Endpoint `/replay` para reproducir señales históricas de backtest

---

Daynier Rodríguez · Madrid · 2026
