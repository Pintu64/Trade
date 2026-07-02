"""
setup.py — Interactive bot setup wizard with premium UI.

Guides new users through configuration with validation,
emoji feedback, and professional onboarding experience.
"""

import os
import sys
from pathlib import Path


def print_header():
    """Print premium animated header."""
    print("\n")
    print("╔" + "═" * 50 + "╗")
    print("║" + " 🚀  BITGET SIGNAL BOT - SETUP WIZARD  🚀  ".center(50) + "║")
    print("║" + " Premium Edition | iPhone 17 Aesthetic ".center(50) + "║")
    print("╚" + "═" * 50 + "╝")
    print()


def print_section(title: str):
    """Print a section header."""
    print(f"\n┌─ {title}")
    print("│")


def print_end_section():
    """Print section footer."""
    print("│")
    print("└─────────────────────────────────────────────────")


def validate_telegram_token(token: str) -> bool:
    """Validate Telegram bot token format."""
    if not token or len(token) < 20:
        return False
    parts = token.split(":")
    return len(parts) == 2 and parts[0].isdigit() and len(parts[1]) > 0


def validate_telegram_chat_id(chat_id: str) -> bool:
    """Validate Telegram chat ID format."""
    try:
        int(chat_id)
        return True
    except ValueError:
        return False


def validate_symbols(symbols_str: str) -> bool:
    """Validate trading symbols format."""
    if not symbols_str:
        return False
    symbols = [s.strip() for s in symbols_str.split(",")]
    return all(s and len(s) >= 6 for s in symbols)


def get_telegram_setup() -> tuple:
    """Interactive Telegram configuration."""
    print_section("🤖 TELEGRAM CONFIGURATION")
    print("│ Get your bot token from @BotFather on Telegram")
    print("│")
    
    # Get bot token
    while True:
        token = input("│ 🔑 Bot Token: ").strip()
        if validate_telegram_token(token):
            print("│    ✅ Token validated")
            break
        else:
            print("│    ❌ Invalid token format (should be: 123456:ABC...)")
    
    print("│")
    
    # Get chat ID
    print("│ To get your Chat ID:")
    print("│ 1. Message your bot anything")
    print("│ 2. Visit: https://api.telegram.org/bot{token}/getUpdates")
    print("│ 3. Find the 'id' field in the response")
    print("│")
    
    while True:
        chat_id = input("│ 💬 Chat ID: ").strip()
        if validate_telegram_chat_id(chat_id):
            print("│    ✅ Chat ID validated")
            break
        else:
            print("│    ❌ Invalid Chat ID (must be numeric)")
    
    print_end_section()
    return token, chat_id


def get_trading_setup() -> tuple:
    """Interactive trading configuration."""
    print_section("📊 TRADING CONFIGURATION")
    
    # Trading pairs
    print("│ Enter trading pairs (comma-separated)")
    print("│ Example: BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT")
    print("│")
    
    while True:
        symbols = input("│ 📈 Trading Pairs: ").strip()
        if validate_symbols(symbols):
            print("│    ✅ Symbols validated")
            break
        else:
            print("│    ❌ Invalid format (use SYMBOL format, comma-separated)")
    
    print("│")
    print("│ Poll interval: How often to scan (in seconds)")
    print("│ • 600s  = 10 min (aggressive, more signals)")
    print("│ • 900s  = 15 min (recommended, balanced)")
    print("│ • 1800s = 30 min (conservative, fewer signals)")
    print("│")
    
    while True:
        poll_str = input("│ ⏱️  Poll Interval (seconds) [900]: ").strip()
        if not poll_str:
            poll_interval = 900
            break
        try:
            poll_interval = int(poll_str)
            if 300 <= poll_interval <= 3600:
                break
            else:
                print("│    ❌ Must be between 300s and 3600s")
        except ValueError:
            print("│    ❌ Must be a number")
    
    print(f"│    ✅ Poll interval: {poll_interval}s ({poll_interval // 60}min)")
    
    print_end_section()
    return symbols, poll_interval


def get_risk_setup() -> tuple:
    """Interactive risk management configuration."""
    print_section("⚖️  RISK MANAGEMENT")
    
    print("│ Account risk per trade (as % of account)")
    print("│ • 0.5% = Conservative")
    print("│ • 1.0% = Balanced (recommended)")
    print("│ • 2.0% = Aggressive")
    print("│")
    
    while True:
        risk_str = input("│ 💰 Account Risk % [1.0]: ").strip()
        if not risk_str:
            risk_pct = 1.0
            break
        try:
            risk_pct = float(risk_str)
            if 0.1 <= risk_pct <= 5.0:
                break
            else:
                print("│    ❌ Must be between 0.1% and 5.0%")
        except ValueError:
            print("│    ❌ Must be a decimal number")
    
    print(f"│    ✅ Risk per trade: {risk_pct}%")
    
    print("│")
    print("│ Maximum leverage for signal generation")
    print("│ • 1x  = No leverage (spot trading style)")
    print("│ • 3x  = Conservative")
    print("│ • 5x  = Balanced (recommended)")
    print("│ • 10x = Aggressive")
    print("│")
    
    while True:
        leverage_str = input("│ 📊 Max Leverage [5]: ").strip()
        if not leverage_str:
            max_leverage = 5
            break
        try:
            max_leverage = int(leverage_str)
            if 1 <= max_leverage <= 20:
                break
            else:
                print("│    ❌ Must be between 1x and 20x")
        except ValueError:
            print("│    ❌ Must be a whole number")
    
    print(f"│    ✅ Max leverage: {max_leverage}x")
    
    print_end_section()
    return risk_pct, max_leverage


def create_env_file(token: str, chat_id: str, symbols: str, poll_interval: int,
                    risk_pct: float, max_leverage: int):
    """Create .env file with user configuration."""
    env_content = f"""# ══════════════════════════════════════════════════════════════
# BITGET SIGNAL BOT - CONFIGURATION
# Generated by setup wizard
# ══════════════════════════════════════════════════════════════

# ── TELEGRAM CONFIGURATION ────────────────────────────────────
TELEGRAM_BOT_TOKEN={token}
TELEGRAM_CHAT_ID={chat_id}

# ── TRADING PAIRS ─────────────────────────────────────────────
WHITELIST_SYMBOLS={symbols}

# ── TIMEFRAMES ────────────────────────────────────────────────
# Valid: 1m,3m,5m,15m,30m,1H,4H,6H,12H,1D,3D,1W,1M
TREND_TIMEFRAME=4H
SIGNAL_TIMEFRAME=1H
CANDLE_LIMIT=200

# ── TECHNICAL INDICATORS ─────────────────────────────────────
EMA_FAST=20
EMA_SLOW=50
RSI_PERIOD=14
RSI_OVERBOUGHT=70
RSI_OVERSOLD=30
ATR_PERIOD=14
BREAKOUT_LOOKBACK=20
VOLUME_SPIKE_MULTIPLIER=1.5

# ── FUNDING RATE FILTER ───────────────────────────────────────
MAX_ABS_FUNDING_RATE=0.0008

# ── RISK MANAGEMENT ───────────────────────────────────────────
ATR_STOP_MULTIPLIER=1.5
ATR_TARGET_MULTIPLIER=2.5
ACCOUNT_RISK_PERCENT={risk_pct}
MAX_LEVERAGE_SUGGESTED={max_leverage}

# ── POLLING CONFIGURATION ─────────────────────────────────────
POLL_INTERVAL_SECONDS={poll_interval}
MIN_MINUTES_BETWEEN_REPEAT_SIGNAL=240
SCAN_ERROR_BACKOFF_SECONDS=30

# ── DATABASE ──────────────────────────────────────────────────
DB_PATH=signal_bot.db
DB_BUSY_TIMEOUT_SECONDS=30

# ── LOGGING ───────────────────────────────────────────────────
LOG_FILE=signal_bot.log
LOG_LEVEL=INFO
LOG_MAX_BYTES=10485760
LOG_BACKUP_COUNT=5

# ── BITGET API ────────────────────────────────────────────────
BITGET_BASE_URL=https://api.bitget.com
REQUEST_TIMEOUT_SECONDS=10
HTTP_MAX_RETRIES=3
HTTP_RETRY_BACKOFF_SECONDS=1.5
MIN_SECONDS_BETWEEN_REQUESTS=0.2

# ── PRODUCT TYPE ──────────────────────────────────────────────
# Use: USDT-FUTURES (perpetual) or SPOT
PRODUCT_TYPE=USDT-FUTURES
"""
    
    env_path = Path(".env")
    env_path.write_text(env_content)
    return env_path


def print_summary(token: str, chat_id: str, symbols: str, poll_interval: int,
                 risk_pct: float, max_leverage: int):
    """Print configuration summary."""
    print("\n")
    print("╔" + "═" * 50 + "╗")
    print("║" + " ✅ CONFIGURATION COMPLETE ".center(50) + "║")
    print("╚" + "═" * 50 + "╝")
    print()
    
    print("📋 SUMMARY")
    print("┌─────────────────────────────────────────────────")
    print(f"│ 🤖 Telegram Token   : {token[:20]}...***")
    print(f"│ 💬 Chat ID          : {chat_id}")
    print(f"│ 📈 Trading Pairs    : {symbols}")
    print(f"│ ⏱️  Poll Interval    : {poll_interval}s ({poll_interval // 60}min)")
    print(f"│ 💰 Risk/Trade      : {risk_pct}%")
    print(f"│ 📊 Max Leverage    : {max_leverage}x")
    print("└─────────────────────────────────────────────────")
    print()


def print_next_steps():
    """Print next steps for user."""
    print("🚀 NEXT STEPS")
    print("┌─────────────────────────────────────────────────")
    print("│ 1. Install dependencies:")
    print("│    pip install -r requirements.txt")
    print("│")
    print("│ 2. Start the bot:")
    print("│    python main.py")
    print("│")
    print("│ 3. Watch for signals in Telegram!")
    print("│")
    print("│ 4. Optional: Run stats viewer")
    print("│    python stats.py recent")
    print("│    python stats.py performance")
    print("└─────────────────────────────────────────────────")
    print()
    print("📚 Documentation: See README.md for detailed guide")
    print()


def main():
    """Run interactive setup wizard."""
    print_header()
    
    # Check if .env already exists
    if Path(".env").exists():
        response = input("⚠️  .env file already exists. Overwrite? (y/n): ").strip().lower()
        if response != "y":
            print("❌ Setup cancelled")
            return
    
    print("Welcome to Bitget Signal Bot setup! 🎉\n")
    print("This wizard will help you configure the bot in 3 steps.\n")
    
    # Step 1: Telegram
    token, chat_id = get_telegram_setup()
    
    # Step 2: Trading
    symbols, poll_interval = get_trading_setup()
    
    # Step 3: Risk Management
    risk_pct, max_leverage = get_risk_setup()
    
    # Create .env file
    print("\n⏳ Creating .env file...")
    env_path = create_env_file(token, chat_id, symbols, poll_interval, risk_pct, max_leverage)
    print(f"✅ Configuration saved to {env_path}")
    
    # Print summary
    print_summary(token, chat_id, symbols, poll_interval, risk_pct, max_leverage)
    
    # Print next steps
    print_next_steps()
    
    print("💡 Tip: Test your setup with 'python main.py' — the bot will validate everything!")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Setup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error during setup: {e}")
        sys.exit(1)
