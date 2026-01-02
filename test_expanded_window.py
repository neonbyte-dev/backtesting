"""
Expanded Entry Window Test - Last 30 Days

Entry window: 9:30 AM - 11:30 AM EST (US market open hours)
Entry trigger: -2% dump anytime in that window
Exit: 1.5% trailing stop, never sell for loss
Size: $10,000
"""

import sys
sys.path.append('src')

from utils.data_fetcher import DataFetcher
from backtester import Backtester
from strategies.market_open_dump import MarketOpenDumpStrategy


def main():
    print("\n" + "="*70)
    print("📊 EXPANDED ENTRY WINDOW - LAST 30 DAYS")
    print("="*70 + "\n")

    # Fetch 30 days of data
    print("Fetching Bitcoin data...\n")
    fetcher = DataFetcher()

    data = fetcher.fetch_ohlcv(
        symbol='BTC/USDT',
        timeframe='15m',
        days_back=30
    )

    print(f"\nData period: {data.index[0]} to {data.index[-1]}")
    print(f"Total candles: {len(data)}\n")

    # Configure strategy
    print("="*70)
    print("STRATEGY CONFIGURATION")
    print("="*70)
    print("\nEntry:")
    print("  - Entry window: 9:30 AM - 11:30 AM EST")
    print("  - Trigger: -2% dump anytime in that window")
    print("  - Compare to price before 9:30 AM")
    print("\nExit:")
    print("  - 1.5% trailing stop")
    print("  - NEVER sell for loss")
    print("\nPosition size:")
    print("  - $10,000 initial capital")
    print("\n" + "="*70 + "\n")

    # Create strategy with expanded window
    strategy = MarketOpenDumpStrategy(
        entry_mode='on_dump',
        exit_mode='trailing_stop_no_loss',
        dump_threshold_pct=-2.0,
        trailing_stop_pct=1.5,
        market_open_hour=9,      # Start at 9:30 AM
        entry_window_end=11,     # End at 11:30 AM
    )

    # Run backtest
    backtester = Backtester(
        initial_capital=10000,
        fee_percent=0.1
    )

    results = backtester.run(data, strategy)

    # Detailed analysis
    print("\n" + "="*70)
    print("📈 TRADE-BY-TRADE ANALYSIS")
    print("="*70 + "\n")

    buy_trades = [t for t in results['trades'] if t['type'] == 'BUY']
    sell_trades = [t for t in results['trades'] if t['type'] == 'SELL']

    print(f"Positions opened: {len(buy_trades)}")
    print(f"Positions closed: {len(sell_trades)}")
    print(f"Positions still open: {len(buy_trades) - len(sell_trades)}\n")

    if buy_trades:
        print("All entry times:")
        for i, trade in enumerate(buy_trades, 1):
            entry_time = trade['timestamp']
            print(f"  {i}. {entry_time} (${trade['price']:,.2f})")

    if sell_trades:
        print("\nClosed trades:")
        for i, trade in enumerate(sell_trades, 1):
            print(f"\n  Trade {i}:")
            print(f"    Profit: ${trade['pnl']:,.2f} ({trade['pnl_percent']:+.2f}%)")
            print(f"    Exit: {trade['timestamp']}")

        total_profit = sum(t['pnl'] for t in sell_trades)
        avg_profit = total_profit / len(sell_trades)
        print(f"\n  Total profit: ${total_profit:,.2f}")
        print(f"  Average: ${avg_profit:,.2f}")

    # Check for open positions
    if len(buy_trades) > len(sell_trades):
        print("\n⚠️  OPEN POSITION(S):")
        current_price = data['close'].iloc[-1]

        for i in range(len(sell_trades), len(buy_trades)):
            trade = buy_trades[i]
            unrealized_pnl = (current_price - trade['price']) / trade['price'] * 100

            print(f"\n  Position {i+1}:")
            print(f"    Entry: ${trade['price']:,.2f} on {trade['timestamp']}")
            print(f"    Current: ${current_price:,.2f}")
            print(f"    Unrealized P&L: {unrealized_pnl:+.2f}%")

            if unrealized_pnl < 0:
                print(f"    Status: Waiting for recovery")
            else:
                print(f"    Status: In profit, trailing stop active")

    # Summary
    print("\n" + "="*70)
    print("🎯 RESULTS COMPARISON")
    print("="*70 + "\n")

    print(f"Starting capital: ${results['initial_capital']:,.2f}")
    print(f"Ending value:     ${results['final_value']:,.2f}")
    print(f"Total return:     ${results['total_return']:,.2f} ({results['total_return_pct']:+.2f}%)")
    print(f"\nBuy & Hold:       {results['buy_hold_return_pct']:+.2f}%")

    outperformance = results['total_return_pct'] - results['buy_hold_return_pct']
    print(f"Outperformance:   {outperformance:+.2f}%")

    print(f"\nWin rate:         {results['win_rate']:.1f}%")
    print(f"Max drawdown:     {results['max_drawdown']:.2f}%")

    # Verdict
    print("\n" + "="*70)
    print("💡 KEY INSIGHTS")
    print("="*70 + "\n")

    print("1. EXPANDED WINDOW EFFECT:")
    print(f"   Positions opened: {len(buy_trades)}")
    print(f"   vs. 10 AM only window: 2 positions")

    if len(buy_trades) > 2:
        print(f"   ✓ Caught {len(buy_trades) - 2} additional dump(s) in expanded window")
    elif len(buy_trades) == 2:
        print(f"   → No additional dumps caught (same as 10 AM window)")
    else:
        print(f"   → Fewer dumps caught than 10 AM window")

    print("\n2. PERFORMANCE:")
    if outperformance > 0:
        print(f"   ✅ Beats buy & hold by {outperformance:+.2f}%")
    else:
        print(f"   ❌ Underperforms buy & hold by {abs(outperformance):.2f}%")

    if results['win_rate'] == 100 and len(sell_trades) > 0:
        print(f"   ✅ Perfect win rate: {len(sell_trades)} profitable trade(s)")

    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    main()
