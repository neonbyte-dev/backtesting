"""
Fine-tune December strategy - test variations around the winning formula
Testing different combinations of:
- Price thresholds ($85K, $88K, $90K, $92K, $95K)
- Trailing stops (0.5%, 0.75%, 1.0%, 1.5%, 2.0%)
"""

import sys
sys.path.append('src')

import pandas as pd
from utils.data_fetcher import DataFetcher
from backtester import Backtester
from strategies.market_open_dump import MarketOpenDumpStrategy

# Fetch and filter to December
print("Fetching data...")
fetcher = DataFetcher()
data = fetcher.fetch_ohlcv('BTC/USDT', '5m', days_back=90)
data = data.loc['2025-12-01':'2025-12-31']

# Test matrix
price_thresholds = [85000, 88000, 90000, 92000, 95000, None]  # None = no filter
trailing_stops = [0.5, 0.75, 1.0, 1.5, 2.0]

print(f"Testing {len(price_thresholds)} price thresholds × {len(trailing_stops)} trailing stops")
print(f"= {len(price_thresholds) * len(trailing_stops)} total combinations\n")

results_summary = []

for max_price in price_thresholds:
    for trail_pct in trailing_stops:
        price_label = f"${max_price/1000:.0f}K" if max_price else "No filter"

        # Run backtest (suppressing output)
        strategy = MarketOpenDumpStrategy(
            entry_mode='end_of_dump',
            exit_mode='trailing_stop_no_loss',
            dump_end_hour=15,
            max_entry_price=max_price,
            trailing_stop_pct=trail_pct,
            timezone='America/New_York'
        )

        backtester = Backtester(
            initial_capital=10000,
            fee_percent=0.1,
            display_timezone='America/New_York'
        )

        # Redirect stdout to suppress trade logs
        import io
        import sys
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()

        results = backtester.run(data, strategy)

        sys.stdout = old_stdout

        # Store results
        results_summary.append({
            'max_price': price_label,
            'trailing_pct': trail_pct,
            'return_pct': results['total_return_pct'],
            'final_value': results['final_value'],
            'trades': results['total_trades'],
            'win_rate': results['win_rate'],
            'max_dd': results['max_drawdown'],
            'winning': results['winning_trades'],
            'losing': results['losing_trades']
        })

# Sort by return
results_summary.sort(key=lambda x: x['return_pct'], reverse=True)

# Print top 10
print("="*100)
print("TOP 10 BEST PERFORMING COMBINATIONS")
print("="*100)
print(f"{'Price Filter':<15} {'Trail %':<10} {'Return %':>10} {'Trades':>8} {'Win %':>8} {'Max DD %':>10}")
print("-"*100)

for i, r in enumerate(results_summary[:10], 1):
    print(f"{r['max_price']:<15} {r['trailing_pct']:<10.2f} {r['return_pct']:>9.2f}% "
          f"{r['trades']:>8} {r['win_rate']:>7.1f}% {r['max_dd']:>9.2f}%")

print("-"*100)

# Best performer
best = results_summary[0]
print(f"\n🏆 BEST COMBINATION:")
print(f"   Max Entry Price: {best['max_price']}")
print(f"   Trailing Stop: {best['trailing_pct']}%")
print(f"   Return: {best['return_pct']:+.2f}%")
print(f"   Final Value: ${best['final_value']:,.2f}")
print(f"   Trades: {best['trades']} ({best['winning']}W / {best['losing']}L)")
print(f"   Win Rate: {best['win_rate']:.1f}%")
print(f"   Max Drawdown: {best['max_dd']:.2f}%")

# Compare to current champion
current_champion = {'max_price': '$90K', 'trailing_pct': 1.0, 'return_pct': 17.95}

print(f"\n📊 COMPARISON TO CURRENT CHAMPION:")
print(f"   Current: {current_champion['max_price']}, {current_champion['trailing_pct']}% trail → +{current_champion['return_pct']:.2f}%")
print(f"   Best:    {best['max_price']}, {best['trailing_pct']}% trail → +{best['return_pct']:.2f}%")

if best['return_pct'] > current_champion['return_pct']:
    improvement = best['return_pct'] - current_champion['return_pct']
    print(f"\n✅ IMPROVEMENT: +{improvement:.2f}% better!")
    print(f"   NEW CHAMPION: {best['max_price']} with {best['trailing_pct']}% trailing stop")
else:
    print(f"\n✅ CURRENT SETTINGS ARE OPTIMAL")
    print(f"   Stick with $90K max entry + 1.0% trailing stop")

print()
