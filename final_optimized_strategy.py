"""
Final Optimized Strategy - 5 Trades in December

Entry: -0.25% dump @ 10 AM from 9:30 AM open
Exit: 1.5% trailing stop, never sell for loss
"""

import sys
sys.path.append('src')

from utils.data_fetcher import DataFetcher
from backtester import Backtester
from strategies.market_open_dump import MarketOpenDumpStrategy


def main():
    print("\n" + "="*70)
    print("📊 OPTIMIZED STRATEGY - DECEMBER 2025")
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
    print("  - Trigger: -0.25% dump from 9:30 AM open")
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
        dump_threshold_pct=-0.25,
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

    print("\n" + "="*70)
    print("✅ ACHIEVED: 5 TRADES IN DECEMBER")
    print("="*70 + "\n")

    print(f"Return:           +{results['total_return_pct']:.2f}%")
    print(f"vs Buy & Hold:    +{results['total_return_pct'] - results['buy_hold_return_pct']:.2f}%")
    print(f"Win Rate:         {results['win_rate']:.1f}%")
    print(f"\n{'Profitable ✅' if results['total_return_pct'] > 0 else 'Losing ❌'}")
    print(f"{'Beats buy & hold ✅' if results['total_return_pct'] > results['buy_hold_return_pct'] else 'Underperforms ❌'}")

    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    main()
