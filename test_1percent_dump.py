"""
Test -1% Dump Threshold - December

Sweet spot between -0.25% (too sensitive) and -2.5% (too selective)
"""

import sys
sys.path.append('src')

from utils.data_fetcher import DataFetcher
from backtester import Backtester
from strategies.market_open_dump import MarketOpenDumpStrategy


def main():
    print("\n" + "="*70)
    print("📊 TESTING -1% DUMP THRESHOLD - DECEMBER 2025")
    print("="*70 + "\n")

    # Fetch December data
    fetcher = DataFetcher()
    data = fetcher.fetch_ohlcv('BTC/USDT', '15m', days_back=33)
    dec_data = data[(data.index >= '2025-12-01') & (data.index < '2026-01-01')]

    print(f"Period: {dec_data.index[0]} to {dec_data.index[-1]}")
    print(f"Total candles: {len(dec_data)}\n")

    print("="*70)
    print("STRATEGY CONFIGURATION")
    print("="*70)
    print("\nEntry:")
    print("  - Time: 10:00-10:59 AM EST")
    print("  - Reference: 9:30 AM open price")
    print("  - Trigger: -1.0% dump from 9:30 AM open")
    print("\nExit:")
    print("  - 1.5% trailing stop")
    print("  - NEVER sell for loss")
    print("\nPosition size:")
    print("  - $10,000 initial capital\n")
    print("="*70 + "\n")

    # Run strategy
    strategy = MarketOpenDumpStrategy(
        entry_mode='on_dump',
        exit_mode='trailing_stop_no_loss',
        dump_threshold_pct=-1.0,
        trailing_stop_pct=1.5,
        market_open_hour=10,
    )

    backtester = Backtester(initial_capital=10000, fee_percent=0.1)
    results = backtester.run(dec_data, strategy)

    # Trade analysis
    print("\n" + "="*70)
    print("📈 TRADE-BY-TRADE BREAKDOWN")
    print("="*70 + "\n")

    buy_trades = [t for t in results['trades'] if t['type'] == 'BUY']
    sell_trades = [t for t in results['trades'] if t['type'] == 'SELL']

    print(f"Total entries: {len(buy_trades)}")
    print(f"Total exits:   {len(sell_trades)}")
    print(f"Still open:    {len(buy_trades) - len(sell_trades)}\n")

    if len(sell_trades) > 0:
        for i, sell in enumerate(sell_trades, 1):
            buy = buy_trades[i-1]

            print(f"TRADE {i}:")
            print(f"  Entry:  {buy['timestamp']} @ ${buy['price']:,.2f}")
            print(f"  Exit:   {sell['timestamp']} @ ${sell['price']:,.2f}")
            print(f"  Profit: ${sell['pnl']:,.2f} ({sell['pnl_percent']:+.2f}%)")
            print(f"  Result: {'✅ WIN' if sell['pnl'] > 0 else '❌ LOSS'}\n")

    # Open positions
    if len(buy_trades) > len(sell_trades):
        open_trade = buy_trades[-1]
        current_price = dec_data['close'].iloc[-1]
        unrealized = (current_price - open_trade['price']) / open_trade['price'] * 100

        print(f"OPEN POSITION:")
        print(f"  Entry:      {open_trade['timestamp']} @ ${open_trade['price']:,.2f}")
        print(f"  Current:    ${current_price:,.2f}")
        print(f"  Unrealized: {unrealized:+.2f}%")
        print(f"  Status:     {'Waiting for recovery' if unrealized < 0 else 'Trailing stop active'}\n")

    # Summary
    print("="*70)
    print("🎯 FINAL RESULTS")
    print("="*70 + "\n")

    print(f"Starting capital: ${results['initial_capital']:,.2f}")
    print(f"Ending value:     ${results['final_value']:,.2f}")
    print(f"Total return:     ${results['total_return']:,.2f} ({results['total_return_pct']:+.2f}%)")
    print(f"\nBuy & Hold:       {results['buy_hold_return_pct']:+.2f}%")
    print(f"Outperformance:   {results['total_return_pct'] - results['buy_hold_return_pct']:+.2f}%")
    print(f"\nClosed Trades:    {len(sell_trades)}")
    print(f"Win Rate:         {results['win_rate']:.1f}%")
    print(f"Max Drawdown:     {results['max_drawdown']:.2f}%")

    # Comparison
    print("\n" + "="*70)
    print("📊 COMPARISON")
    print("="*70 + "\n")

    print("| Threshold | Trades | Return  | Win Rate | Quality |")
    print("|-----------|--------|---------|----------|---------|")
    print("| -0.25%    | 5      | +7.83%  | 80%      | Low     |")
    print(f"| -1.0%     | {len(sell_trades):<6} | {results['total_return_pct']:+.2f}% | {results['win_rate']:.0f}%      | ?       |")
    print("| -2.5%     | 2      | +11.51% | 100%     | High    |")

    print("\n" + "="*70)

    if len(sell_trades) >= 3:
        print(f"✅ {len(sell_trades)} TRADES - Good frequency")
    else:
        print(f"⚠️  Only {len(sell_trades)} trades - Lower than desired")

    if results['total_return_pct'] > 0:
        print(f"✅ PROFITABLE: +{results['total_return_pct']:.2f}%")
    else:
        print(f"❌ LOSING: {results['total_return_pct']:.2f}%")

    if results['total_return_pct'] > results['buy_hold_return_pct']:
        print(f"✅ BEATS buy & hold by {results['total_return_pct'] - results['buy_hold_return_pct']:.2f}%")

    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    main()
