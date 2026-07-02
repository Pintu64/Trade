"""
example_signals.py — Generate example premium signal outputs for demonstration.

Shows what the bot's Telegram messages look like with professional glassmorphic design.
Run: python example_signals.py
"""

from dataclasses import dataclass
from notifier import _build_premium_signal_message, _build_status_message_premium


@dataclass
class ExampleSignal:
    """Mock signal object for demonstration."""
    symbol: str
    direction: str
    entry: float
    stop_loss: float
    take_profit: float
    reward_risk: float
    suggested_leverage: int
    funding_rate: float
    rsi: float
    confidence_notes: list


def print_separator(title: str = ""):
    """Print a nice separator."""
    if title:
        print(f"\n{'=' * 80}")
        print(f"  {title}")
        print(f"{'=' * 80}\n")
    else:
        print(f"\n{'-' * 80}\n")


def example_btc_long():
    """Example: Bitcoin long signal with high confidence."""
    print_separator("EXAMPLE 1: Bitcoin LONG (High Confidence)")
    
    signal = ExampleSignal(
        symbol="BTCUSDT",
        direction="LONG",
        entry=65432.50,
        stop_loss=64500.25,
        take_profit=67123.75,
        reward_risk=1.67,
        suggested_leverage=5,
        funding_rate=0.00045,
        rsi=48.5,
        confidence_notes=[
            "EMA20/50 aligned LONG on both 4H and 1H",
            "RSI 48.5 — healthy mid-range, not extended",
            "Breakout above 65000 resistance with 1.6x volume spike",
            "Funding rate +0.045% — positive but not excessive",
            "ATR 145.67 → SL 218.5 below, TP 364.2 above entry",
        ]
    )
    
    message = _build_premium_signal_message(signal)
    print("Telegram Message (HTML formatted):")
    print(message)
    print_separator()


def example_eth_short():
    """Example: Ethereum short signal with moderate confidence."""
    print_separator("EXAMPLE 2: Ethereum SHORT (Moderate Confidence)")
    
    signal = ExampleSignal(
        symbol="ETHUSDT",
        direction="SHORT",
        entry=3245.30,
        stop_loss=3312.45,
        take_profit=3089.15,
        reward_risk=1.52,
        suggested_leverage=3,
        funding_rate=-0.00015,
        rsi=62.3,
        confidence_notes=[
            "EMA20/50 bearish crossover on 4H timeframe",
            "1H signal confirms with EMA20 below EMA50",
            "RSI 62.3 — approaching overbought, potential pullback",
            "Breakdown below 3250 support with volume increase",
            "Funding rate -0.015% — slightly negative (favor shorts)",
        ]
    )
    
    message = _build_premium_signal_message(signal)
    print("Telegram Message (HTML formatted):")
    print(message)
    print_separator()


def example_sol_breakout():
    """Example: Solana breakout long with strong confidence."""
    print_separator("EXAMPLE 3: Solana LONG Breakout (Strong Confidence)")
    
    signal = ExampleSignal(
        symbol="SOLUSDT",
        direction="LONG",
        entry=145.32,
        stop_loss=138.75,
        take_profit=160.25,
        reward_risk=2.15,
        suggested_leverage=5,
        funding_rate=0.00062,
        rsi=55.2,
        confidence_notes=[
            "4H: EMA20 above EMA50 — strong uptrend bias",
            "1H: Fresh breakout above resistance zone 143.00",
            "Volume spike 2.8x average — institutional interest",
            "RSI 55 — balanced, room to move up before overbought",
            "Funding rate 0.062% — reasonable for long direction",
        ]
    )
    
    message = _build_premium_signal_message(signal)
    print("Telegram Message (HTML formatted):")
    print(message)
    print_separator()


def example_startup_message():
    """Example: Bot startup notification."""
    print_separator("EXAMPLE 4: Startup Notification")
    
    text = (
        f"✅ <b>Premium Signal Bot Online</b>\n\n"
        f"📊 <b>Market Scan Active</b>\n"
        f"<code>Pairs: 8 monitored</code>\n"
        f"<code>Update: Every 15min</code>\n\n"
        f"⚡ Ready to detect trading setups!\n"
        f"<i>Awaiting market opportunities...</i>"
    )
    message = _build_status_message_premium(text, status_type="start")
    print("Telegram Message (Startup):")
    print(message)
    print_separator()


def example_tp_hit_message():
    """Example: Take profit hit notification."""
    print_separator("EXAMPLE 5: Take Profit Hit Notification")
    
    text = (
        f"✅ <b>TRADE CLOSED - PROFIT</b>\n\n"
        f"📈 <b>BTCUSDT LONG</b>\n"
        f"<code>Entry  : $65,432.50</code>\n"
        f"<code>Exit   : $67,123.75 (TP HIT!)</code>\n"
        f"<code>P&L    : +1.67R ($2,836.42 per $1,000 at risk)</code>\n\n"
        f"🎯 Excellent execution!"
    )
    message = _build_status_message_premium(text, status_type="success")
    print("Telegram Message (TP Hit):")
    print(message)
    print_separator()


def example_sl_hit_message():
    """Example: Stop loss hit notification."""
    print_separator("EXAMPLE 6: Stop Loss Hit Notification")
    
    text = (
        f"❌ <b>TRADE CLOSED - LOSS</b>\n\n"
        f"📉 <b>ETHUSDT SHORT</b>\n"
        f"<code>Entry  : $3,245.30</code>\n"
        f"<code>Exit   : $3,312.45 (SL HIT)</code>\n"
        f"<code>P&L    : -1.0R ($1,000 per $1,000 at risk)</code>\n\n"
        f"📊 Loss taken. Stay disciplined!"
    )
    message = _build_status_message_premium(text, status_type="error")
    print("Telegram Message (SL Hit):")
    print(message)
    print_separator()


def example_performance_summary():
    """Example: Weekly performance summary."""
    print_separator("EXAMPLE 7: Performance Summary")
    
    text = (
        f"📊 <b>WEEKLY PERFORMANCE</b>\n\n"
        f"✅ Profitable Trades : 14 (64%)\n"
        f"❌ Loss Trades       : 8 (36%)\n"
        f"➡️  Neutral/Expired  : 0\n\n"
        f"💰 Net Result        : +18.5R\n"
        f"📈 Win Rate          : 63.6%\n"
        f"🎯 Avg Win           : +1.32R\n"
        f"📉 Avg Loss          : -1.0R\n\n"
        f"🚀 Excellent week! Keep following the system."
    )
    message = _build_status_message_premium(text, status_type="info")
    print("Telegram Message (Performance):")
    print(message)
    print_separator()


def main():
    """Display all example signals."""
    print("\n")
    print("╔" + "═" * 78 + "╗")
    print("║" + " 📱 BITGET SIGNAL BOT - EXAMPLE TELEGRAM MESSAGES ".center(78) + "║")
    print("║" + " Premium iPhone 17 Pro Max Glassmorphic Design ".center(78) + "║")
    print("╚" + "═" * 78 + "╝")
    
    print("\nThese examples show what your Telegram notifications will look like:")
    print("(Colors and formatting render beautifully on iPhone and Android)")
    
    # Display all examples
    example_btc_long()
    example_eth_short()
    example_sol_breakout()
    example_startup_message()
    example_tp_hit_message()
    example_sl_hit_message()
    example_performance_summary()
    
    # Final summary
    print("\n" + "=" * 80)
    print("  SUMMARY")
    print("=" * 80)
    print("""
✨ Features Demonstrated:

  1. 📈 Premium glassmorphic signal format
     • Direction badges (LONG/SHORT with colors)
     • Price levels with box drawing (entry, SL, TP)
     • Risk metrics and reward:risk ratio
     • Confidence scoring with visual bars

  2. 🎯 Professional design patterns
     • Box-drawing characters for structure
     • Monospace code blocks for prices
     • Unicode visual indicators (█, ░, etc.)
     • Clear hierarchy and readability

  3. 🔔 Outcome notifications
     • TP hits (green, success indicator)
     • SL hits (red, error indicator)
     • Performance summaries

  4. 🚀 Status messages
     • Startup/shutdown notifications
     • Error messages
     • Performance updates

💡 Tips:
  • Install websocket-client: pip install -r requirements.txt
  • Run setup wizard: python setup.py
  • Start bot: python main.py
  • Watch Telegram for real signals!

🎓 Remember:
  • Signals are educational — trade at your own risk
  • Always use stop losses
  • Never risk more than you can afford
  • Position size is YOUR responsibility
  • Past performance ≠ future results

Happy trading! 🚀
""")
    print("=" * 80)
    print()


if __name__ == "__main__":
    main()
