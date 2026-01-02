"""
Final Strategy Backtest - Last 30 Days

Entry: -2% dump at 10 AM EST
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
    print("📊 FINAL STRATEGY BACKTEST - LAST 30 DAYS")
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
    print("  - Wait for -2% dump at 10 AM EST")
    print("  - Reference: 9:30 AM open price (US market open)")
    print("  - Compares current price to 9:30 AM open")
    print("\nExit:")
    print("  - 1.5% trailing stop")
    print("  - NEVER sell for loss")
    print("\nPosition size:")
    print("  - $10,000 initial capital")
    print("  - All-in on each trade")
    print("\n" + "="*70 + "\n")

    # Create strategy
    strategy = MarketOpenDumpStrategy(
        entry_mode='on_dump',
        exit_mode='trailing_stop_no_loss',
        dump_threshold_pct=-2.0,
        trailing_stop_pct=1.5,
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

    if sell_trades:
        print("Closed trades:")
        for i, trade in enumerate(sell_trades, 1):
            print(f"\n  Trade {i}:")
            print(f"    Profit: ${trade['pnl']:,.2f} ({trade['pnl_percent']:+.2f}%)")
            print(f"    Exit: {trade['timestamp']}")

        total_profit = sum(t['pnl'] for t in sell_trades)
        avg_profit = total_profit / len(sell_trades)
        print(f"\n  Total profit from closed trades: ${total_profit:,.2f}")
        print(f"  Average profit per trade: ${avg_profit:,.2f}")

    # Check for open positions
    if len(buy_trades) > len(sell_trades):
        print("\n⚠️  OPEN POSITION:")
        last_buy = buy_trades[-1]
        current_price = data['close'].iloc[-1]
        unrealized_pnl = (current_price - last_buy['price']) / last_buy['price'] * 100

        print(f"  Entry: ${last_buy['price']:,.2f} on {last_buy['timestamp']}")
        print(f"  Current: ${current_price:,.2f}")
        print(f"  Unrealized P&L: {unrealized_pnl:+.2f}%")

        if unrealized_pnl < 0:
            print(f"  Status: Waiting for recovery (will not sell for loss)")
        else:
            print(f"  Status: In profit, trailing stop active")

    # Summary
    print("\n" + "="*70)
    print("🎯 FINAL RESULTS")
    print("="*70 + "\n")

    print(f"Starting capital: ${results['initial_capital']:,.2f}")
    print(f"Ending value:     ${results['final_value']:,.2f}")
    print(f"Total return:     ${results['total_return']:,.2f} ({results['total_return_pct']:+.2f}%)")
    print(f"\nBuy & Hold:       {results['buy_hold_return_pct']:+.2f}%")
    print(f"Outperformance:   {results['total_return_pct'] - results['buy_hold_return_pct']:+.2f}%")

    print(f"\nWin rate:         {results['win_rate']:.1f}%")
    print(f"Max drawdown:     {results['max_drawdown']:.2f}%")

    # Verdict
    print("\n" + "="*70)
    print("💡 VERDICT")
    print("="*70 + "\n")

    if results['total_return_pct'] > results['buy_hold_return_pct']:
        outperf = results['total_return_pct'] - results['buy_hold_return_pct']
        print(f"✅ Strategy BEATS buy & hold by {outperf:+.2f}%")
    else:
        underperf = results['buy_hold_return_pct'] - results['total_return_pct']
        print(f"❌ Strategy UNDERPERFORMS buy & hold by {underperf:.2f}%")

    if results['win_rate'] == 100 and len(sell_trades) > 0:
        print(f"✅ Perfect win rate: {len(sell_trades)}/{len(sell_trades)} profitable trades")

    if len(buy_trades) > len(sell_trades):
        print(f"⚠️  Warning: {len(buy_trades) - len(sell_trades)} position(s) still open")

    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    main()
