# 🤖 Bitget Futures Signal Bot

A sophisticated **signals-only** trading bot for Bitget USDT Futures that combines multi-factor technical analysis with real-time WebSocket market data to generate high-conviction trade signals.

**Key Features:**
- ✅ **Signals Only** — Never places orders, requires no API credentials
- 📊 **Multi-Factor Analysis** — EMA crossovers, RSI, ATR, breakouts, volume spikes
- 🔄 **Dual Timeframe** — Higher (4H) trend + Lower (1H) signal confirmation
- 📡 **Live WebSocket Feed** — Real-time market data with automatic reconnection
- 💾 **SQLite Tracking** — Full signal history with win/loss analysis
- 🚨 **Telegram Alerts** — Instant notifications with precise entry/SL/TP levels
- 📈 **Outcome Tracking** — Automated TP/SL hit detection and P&L calculation
- ⚙️ **Production Ready** — Systemd integration, WAL mode DB, graceful shutdown

---

## 📋 System Requirements

- **Python** 3.10+
- **Linux/Mac/Windows** with Python installed
- **Telegram** account (for alerts)
- **Internet** connection (public API only — no Bitget account needed)

---

## 🚀 Quick Start

### 1. Clone & Setup

```bash
git clone https://github.com/pintupodder64/Testing-.git
cd Testing-
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements-1.txt
```

### 2. Configure `.env`

Copy the example and fill in your values:

```bash
cp .env.example .env
```

**Minimal `.env` setup:**

```dotenv
# Get these from @BotFather on Telegram
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# Trading pairs to scan
WHITELIST_SYMBOLS=BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT

# Polling interval (900s = 15 min)
POLL_INTERVAL_SECONDS=900
```

### 3. Run the Bot

```bash
python main.py
```

You'll see:
```
2026-07-02 18:52:00 [INFO] main: Bot started. Poll interval: 900s. Symbols: BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT
2026-07-02 18:52:00 [INFO] bitget_websocket: WebSocket client started for symbols: BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT
✅ Signal bot started
Watching 4 pairs: BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT
Poll interval: 15min
```

Stop with **Ctrl-C** (graceful shutdown).

---

## 📊 How It Works

### Signal Generation Flow

1. **Liquidity Gate** → Skips pairs with <$20M 24h volume
2. **Market Data Fetch** → REST API for candles (4H trend, 1H signal)
3. **Indicator Compute** → EMA, RSI, ATR, breakout levels
4. **Higher TF Trend** → 4H EMA crossover determines direction
5. **Lower TF Signal** → 1H EMA must align with 4H trend
6. **RSI Filter** → Rejects overextended moves (overbought/oversold)
7. **Breakout + Volume** → Entry requires recent high/low break + volume spike
8. **Funding Rate Check** → Rejects overcrowded positions
9. **Cooldown Check** → Prevents spam (min 4h between same pair/direction)
10. **Send Alert** → Telegram + SQLite record

### Risk Management (Signals Only)

Each signal includes:
- **Entry Price** — Current close on breakout
- **Stop Loss** — 1.5× ATR below entry (LONG) / above entry (SHORT)
- **Take Profit** — 2.5× ATR above/below entry
- **Reward:Risk Ratio** — TP distance / SL distance (e.g., 1.67:1)
- **Suggested Leverage** — Max 5x (user still controls position size)
- **Confidence Notes** — EMA alignment, volume, RSI status

---

## ⚙️ Configuration Guide

### `.env` Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `WHITELIST_SYMBOLS` | `BTCUSDT,ETHUSDT,...` | Comma-separated pairs to scan |
| `TREND_TIMEFRAME` | `4H` | Higher timeframe for trend direction |
| `SIGNAL_TIMEFRAME` | `1H` | Lower timeframe for entry signals |
| `EMA_FAST` / `EMA_SLOW` | `20 / 50` | Fast/slow EMA periods |
| `RSI_PERIOD` | `14` | RSI lookback period |
| `RSI_OVERBOUGHT` / `OVERSOLD` | `70 / 30` | RSI thresholds |
| `ATR_PERIOD` | `14` | ATR lookback period |
| `ATR_STOP_MULTIPLIER` | `1.5` | Stop loss = entry ± (ATR × this) |
| `ATR_TARGET_MULTIPLIER` | `2.5` | Take profit = entry ± (ATR × this) |
| `VOLUME_SPIKE_MULTIPLIER` | `1.5` | Volume must exceed avg by this factor |
| `MAX_ABS_FUNDING_RATE` | `0.0008` | Max funding rate to allow (0.08%) |
| `POLL_INTERVAL_SECONDS` | `900` | Scan interval in seconds |
| `MIN_MINUTES_BETWEEN_REPEAT_SIGNAL` | `240` | Cooldown between signals (minutes) |
| `MIN_24H_QUOTE_VOLUME_USDT` | `20000000` | Min 24h volume gate ($20M) |

### Telegram Setup

1. **Create bot:** Message `@BotFather` on Telegram → `/newbot` → follow prompts
2. **Get token:** BotFather will provide `TELEGRAM_BOT_TOKEN`
3. **Get chat ID:** 
   - Message your bot anything
   - Visit `https://api.telegram.org/bot<TOKEN>/getUpdates`
   - Find `"chat":{"id": YOUR_CHAT_ID}`
4. **Add to `.env`:**
   ```dotenv
   TELEGRAM_BOT_TOKEN=1234567890:ABCDEFghijklmnopqrstuvwxyz
   TELEGRAM_CHAT_ID=987654321
   ```

---

## 📊 Viewing Performance

### Check Recent Signals

```bash
python stats.py recent              # Last 20 signals
python stats.py recent BTCUSDT      # Filter by symbol
python stats.py recent BTCUSDT 50   # Last 50 for that symbol
```

### View Open Signals

```bash
python stats.py open
```

Output:
```
───────────────────────────────────────────────────
  Open Signals
───────────────────────────────────────────────────
  #    Time                 Symbol     Dir    Entry          SL             TP
  ─────────────────────────────────────────────────────────────────────────
  #42  2026-07-02 18:45:30  BTCUSDT    LONG   65432.1234     64500.2341     67123.4567
```

### Performance Summary

```bash
python stats.py performance
```

Output:
```
───────────────────────────────────────────────────
  Performance Summary (closed signals only)
───────────────────────────────────────────────────
  Status       Count    Avg R       Total R
  ─────────────────────────────────────────
  TP_HIT       12       1.45        17.40R
  SL_HIT       5        -1.00       -5.00R
  EXPIRED      2        0.00        0.00R

  Total closed:  19
  Win rate:      63.2%  (12 TP / 7 SL+expired)
  Net R:         12.40R
```

### Per-Symbol Breakdown

```bash
python stats.py pairs
```

---

## 🐳 Docker Deployment

### Build Image

```dockerfile
FROM python:3.11-slim
WORKDIR /bot
COPY requirements-1.txt .
RUN pip install --no-cache-dir -r requirements-1.txt
COPY . .
CMD ["python", "main.py"]
```

Build:
```bash
docker build -t bitget-signal-bot .
```

Run:
```bash
docker run -d \
  --name bitget-bot \
  -v $(pwd)/.env:/bot/.env \
  -v $(pwd)/signal_bot.db:/bot/signal_bot.db \
  -v $(pwd)/signal_bot.log:/bot/signal_bot.log \
  bitget-signal-bot
```

---

## 🖥️ Systemd Service (Linux)

### Install as Service

1. Copy bot to system location:
```bash
sudo mkdir -p /opt/bitget-signal-bot
sudo cp -r ./* /opt/bitget-signal-bot/
sudo cp .env /opt/bitget-signal-bot/
sudo chown -R botuser:botuser /opt/bitget-signal-bot
```

2. Copy service file:
```bash
sudo cp bitget-signal-bot.service.txt /etc/systemd/system/bitget-signal-bot.service
```

3. Enable & start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable bitget-signal-bot
sudo systemctl start bitget-signal-bot
sudo systemctl status bitget-signal-bot
```

### View Logs

```bash
sudo journalctl -u bitget-signal-bot -f      # Live follow
sudo journalctl -u bitget-signal-bot -n 100  # Last 100 lines
```

---

## 📁 Project Structure

```
Testing-/
├── main.py                  # Entry point & scan loop
├── config.py                # Config validation & env parsing
├── bitget_client.py         # REST API wrapper (candles, tickers, funding rates)
├── bitget_websocket.py      # WebSocket connection for live updates
├── indicators.py            # Technical indicators (EMA, RSI, ATR)
├── signal_engine.py         # Multi-factor signal generation
├── notifier.py              # Telegram messaging
├── database.py              # SQLite persistence (WAL mode)
├── outcome_tracker.py       # TP/SL hit detection
├── stats.py                 # CLI database inspector
├── .env.example             # Config template
├── requirements-1.txt       # Python dependencies
├── bitget-signal-bot.service.txt  # Systemd service file
└── README.md                # This file
```

---

## 🔒 Security Notes

- ✅ **No Private Keys** — Only reads public market data (no API key needed)
- ✅ **No Order Placement** — Signals only, you execute trades manually
- ✅ **No Webscraping** — Uses official Bitget public REST/WebSocket APIs
- ⚠️ **Keep `.env` Private** — Contains Telegram bot token
- ⚠️ **Database Location** — `signal_bot.db` contains trade history (back it up)

---

## 🐛 Troubleshooting

### Bot won't start: `ConfigError: TELEGRAM_BOT_TOKEN not found`

**Fix:** Ensure `.env` has valid `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.

```bash
cat .env | grep TELEGRAM
```

### No signals generated

**Likely causes:**
1. Volume too low — check `MIN_24H_QUOTE_VOLUME_USDT` vs pair volume
2. Funding rate too high — adjust `MAX_ABS_FUNDING_RATE`
3. Indicators not warmed up — need 60+ candles first (wait ~10 polls)
4. No breakouts on selected pairs — adjust `BREAKOUT_LOOKBACK` or `VOLUME_SPIKE_MULTIPLIER`

**Debug:**
```bash
tail -f signal_bot.log | grep SKIP
```

### WebSocket connection failing

**Fix:** Falls back to REST API automatically. If needed, check:
```bash
python -c "import websocket; print('websocket-client OK')"
```

### Database locked

**Fix:** WAL checkpoint will auto-run. If stuck:
```bash
rm signal_bot.db-wal signal_bot.db-shm
```

---

## 📈 Performance Tips

1. **Reduce poll interval** (e.g., 600s) for more frequent scans
2. **Increase `CANDLE_LIMIT`** (up to 1000) for more reliable indicators
3. **Fine-tune ATR multipliers** — test on historical data first
4. **Whitelist high-volume pairs** — more liquidity = better signals
5. **Monitor win rate** — aim for 50%+ with positive expectancy

---

## 📚 API Reference

### `main.py`

- `scan_symbol(symbol)` — Complete scan cycle for one pair
- `run_once()` — Scan all symbols + check outcomes
- `main()` — Entry point with WebSocket init + graceful shutdown

### `bitget_client.py`

- `get_candles(symbol, granularity, limit)` → OHLCV list
- `get_ticker(symbol)` → 24h ticker dict
- `get_current_funding_rate(symbol)` → Funding rate dict

### `bitget_websocket.py`

- `init_websocket(on_ticker)` — Start live feed
- `get_live_ticker(symbol)` → Cached ticker from WebSocket
- `stop_websocket()` — Graceful shutdown

### `signal_engine.py`

- `evaluate_symbol(symbol, signal_df, trend_df, funding_rate)` → Signal or None

### `database.py`

- `record_scan()` — Log a scan attempt
- `record_signal()` — Save generated signal
- `close_signal_outcome()` — Mark signal TP/SL/EXPIRED
- `get_recent_signals()` — Query signals
- `get_performance_summary()` → Win rate + R-multiple

---

## 📝 License

MIT License — Use freely, modify as needed.

---

## 🤝 Contributing

Found a bug? Have an idea?

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/your-idea`)
3. Commit changes (`git commit -am 'Add feature'`)
4. Push (`git push origin feature/your-idea`)
5. Open a Pull Request

---

## ⚠️ Disclaimer

**This is a signals-only bot for educational purposes.**

- Futures trading carries **substantial risk of loss**
- Past performance ≠ future results
- **Always manage position size and risk yourself**
- Test on **paper trading** first
- **Never risk more than you can afford to lose**

Use at your own risk. The author assumes no liability for trading losses.

---

## 🙋 Support

- **Questions?** Check `.env.example` or the config validator
- **Stuck?** Review `signal_bot.log` for detailed error messages
- **Want to contribute?** PRs welcome!

---

**Happy trading! 🚀**
