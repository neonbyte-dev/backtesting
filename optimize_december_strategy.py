"""
Test optimized strategies for December 2025
Comparing:
1. Base strategy (no filters)
2. + No buying above $90k
3. + Trailing stop 1% (never sell at loss)
4. All optimizations combined
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
print(f"December data: {len(data)} candles\n")

# Test configurations
configs = [
    {
        'name': '1. BASE (3PM buy → 9:30AM sell)',
        'entry_mode': 'end_of_dump',
        'exit_mode': 'next_day_premarket',
        'dump_end_hour': 15,
        'max_entry_price': None,
        'trailing_stop_pct': None
    },
    {
        'name': '2. NO BUYING ABOVE $90K',
        'entry_mode': 'end_of_dump',
        'exit_mode': 'next_day_premarket',
        'dump_end_hour': 15,
        'max_entry_price': 90000,
        'trailing_stop_pct': None
    },
    {
        'name': '3. TRAILING STOP 1% (never sell at loss)',
        'entry_mode': 'end_of_dump',
        'exit_mode': 'trailing_stop_no_loss',
        'dump_end_hour': 15,
        'max_entry_price': None,
        'trailing_stop_pct': 1.0
    },
    {
        'name': '4. ALL OPTIMIZATIONS (no buy >90k + trailing 1%)',
        'entry_mode': 'end_of_dump',
        'exit_mode': 'trailing_stop_no_loss',
        'dump_end_hour': 15,
        'max_entry_price': 90000,
        'trailing_stop_pct': 1.0
    },
]

results_summary = []

for config in configs:
    print("="*70)
    print(f"Testing: {config['name']}")
    print("="*70)

    # Create strategy with config
    strategy_params = {
        'entry_mode': config['entry_mode'],
        'exit_mode': config['exit_mode'],
        'dump_end_hour': config['dump_end_hour'],
        'timezone': 'America/New_York'
    }

    # Add optional params
    if config['max_entry_price']:
        strategy_params['max_entry_price'] = config['max_entry_price']
    if config['trailing_stop_pct']:
        strategy_params['trailing_stop_pct'] = config['trailing_stop_pct']

    strategy = MarketOpenDumpStrategy(**strategy_params)

    # Run backtest
    backtester = Backtester(
        initial_capital=10000,
        fee_percent=0.1,
        display_timezone='America/New_York'
    )

    results = backtester.run(data, strategy)

    # Store summary
    results_summary.append({
        'Strategy': config['name'],
        'Return %': results['total_return_pct'],
        'Final Value': results['final_value'],
        'Trades': results['total_trades'],
        'Win Rate %': results['win_rate'],
        'Max DD %': results['max_drawdown'],
        'Winning': results['winning_trades'],
        'Losing': results['losing_trades']
    })

    print("\n")

# Print comparison table
print("\n" + "="*100)
print("OPTIMIZATION COMPARISON - DECEMBER 2025")
print("="*100)
print(f"{'Strategy':<50} {'Return %':>10} {'Trades':>8} {'Win %':>8} {'Max DD %':>10}")
print("-"*100)

for r in results_summary:
    print(f"{r['Strategy']:<50} {r['Return %']:>9.2f}% {r['Trades']:>8} {r['Win Rate %']:>7.1f}% {r['Max DD %']:>9.2f}%")

print("-"*100)

# Find best strategy
best = max(results_summary, key=lambda x: x['Return %'])
print(f"\n🏆 BEST PERFORMER: {best['Strategy']}")
print(f"   Return: {best['Return %']:+.2f}%")
print(f"   Final Value: ${best['Final Value']:,.2f}")
print(f"   Trades: {best['Trades']} ({best['Winning']}W / {best['Losing']}L)")
print(f"   Win Rate: {best['Win Rate %']:.1f}%")
print(f"   Max Drawdown: {best['Max DD %']:.2f}%")
print()
