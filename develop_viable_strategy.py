"""
Develop Viable 10 AM Dump Strategy - Last 30-40 Days

Goal: Find a profitable strategy for trading BTC dumps around 10 AM EST
Test multiple variations and identify the best performer
"""

import sys
sys.path.append('src')

import pandas as pd
from utils.data_fetcher import DataFetcher
from backtester import Backtester
from strategies.market_open_dump import MarketOpenDumpStrategy


def test_strategy(data, config, name):
    """Test a single strategy configuration"""
    strategy = MarketOpenDumpStrategy(**config)
    backtester = Backtester(initial_capital=10000, fee_percent=0.1)
    results = backtester.run(data, strategy)

    return {
        'name': name,
        'config': config,
        'return_pct': results['total_return_pct'],
        'trades': results['total_trades'],
        'win_rate': results['win_rate'],
        'max_dd': results['max_drawdown'],
        'final_value': results['final_value'],
        'vs_buy_hold': results['total_return_pct'] - results['buy_hold_return_pct'],
        'buy_hold': results['buy_hold_return_pct'],
        'results': results
    }


def main():
    print("\n" + "="*70)
    print("🔬 DEVELOPING VIABLE 10 AM DUMP STRATEGY")
    print("="*70 + "\n")

    # Fetch data (35 days for good coverage)
    print("Fetching 35 days of Bitcoin data...\n")
    fetcher = DataFetcher()
    data = fetcher.fetch_ohlcv('BTC/USDT', '15m', days_back=35)

    print(f"Data: {data.index[0]} to {data.index[-1]}")
    print(f"Candles: {len(data)}\n")

    # Test configurations
    print("="*70)
    print("TESTING STRATEGY VARIATIONS")
    print("="*70 + "\n")

    variations = []

    # Group 1: Different dump thresholds
    print("GROUP 1: Dump Threshold Variations\n")

    for threshold in [-1.0, -1.5, -2.0, -2.5]:
        variations.append({
            'name': f'Dump {threshold}% @ 10AM → 1.5% trail',
            'config': {
                'entry_mode': 'on_dump',
                'exit_mode': 'trailing_stop_no_loss',
                'dump_threshold_pct': threshold,
                'trailing_stop_pct': 1.5,
                'market_open_hour': 10,
            }
        })

    # Group 2: Different trailing stops (with -1.5% dump)
    print("GROUP 2: Trailing Stop Variations\n")

    for trail in [1.0, 1.5, 2.0, 2.5]:
        variations.append({
            'name': f'Dump -1.5% @ 10AM → {trail}% trail',
            'config': {
                'entry_mode': 'on_dump',
                'exit_mode': 'trailing_stop_no_loss',
                'dump_threshold_pct': -1.5,
                'trailing_stop_pct': trail,
                'market_open_hour': 10,
            }
        })

    # Group 3: Different entry windows (with -1.5% dump, 1.5% trail)
    print("GROUP 3: Entry Window Variations\n")

    variations.append({
        'name': 'Dump -1.5% @ 9:30-10:30 AM → 1.5% trail',
        'config': {
            'entry_mode': 'on_dump',
            'exit_mode': 'trailing_stop_no_loss',
            'dump_threshold_pct': -1.5,
            'trailing_stop_pct': 1.5,
            'market_open_hour': 9,
            'entry_window_end': 10,
        }
    })

    variations.append({
        'name': 'Dump -1.5% @ 10-11 AM → 1.5% trail',
        'config': {
            'entry_mode': 'on_dump',
            'exit_mode': 'trailing_stop_no_loss',
            'dump_threshold_pct': -1.5,
            'trailing_stop_pct': 1.5,
            'market_open_hour': 10,
            'entry_window_end': 11,
        }
    })

    # Group 4: EOD exits (for comparison)
    print("GROUP 4: End-of-Day Exit (for comparison)\n")

    for threshold in [-1.5, -2.0]:
        variations.append({
            'name': f'Dump {threshold}% @ 10AM → EOD exit',
            'config': {
                'entry_mode': 'on_dump',
                'exit_mode': 'eod',
                'dump_threshold_pct': threshold,
                'market_open_hour': 10,
            }
        })

    print(f"Total variations to test: {len(variations)}\n")
    print("="*70 + "\n")

    # Run all tests
    results = []

    for i, var in enumerate(variations, 1):
        print(f"\n{'─'*70}")
        print(f"TEST {i}/{len(variations)}: {var['name']}")
        print(f"{'─'*70}")

        result = test_strategy(data, var['config'], var['name'])
        results.append(result)

    # Summary comparison
    print("\n" + "="*70)
    print("📊 RESULTS SUMMARY")
    print("="*70 + "\n")

    df = pd.DataFrame([
        {
            'Strategy': r['name'],
            'Return %': r['return_pct'],
            'vs B&H': r['vs_buy_hold'],
            'Trades': r['trades'],
            'Win %': r['win_rate'],
            'Max DD %': r['max_dd'],
        }
        for r in results
    ])

    # Sort by return
    df = df.sort_values('Return %', ascending=False)
    print(df.to_string(index=False))

    # Best strategy
    print("\n" + "="*70)
    print("🏆 BEST STRATEGY")
    print("="*70 + "\n")

    best = results[df.index[0]]

    print(f"Strategy: {best['name']}")
    print(f"\nPerformance:")
    print(f"  Return:          {best['return_pct']:+.2f}%")
    print(f"  vs Buy & Hold:   {best['vs_buy_hold']:+.2f}%")
    print(f"  Final Value:     ${best['final_value']:,.2f}")
    print(f"\nTrade Stats:")
    print(f"  Total Trades:    {best['trades']}")
    print(f"  Win Rate:        {best['win_rate']:.1f}%")
    print(f"  Max Drawdown:    {best['max_dd']:.2f}%")

    # Check if viable
    print("\n" + "="*70)
    print("✅ VIABILITY CHECK")
    print("="*70 + "\n")

    viable = True

    if best['return_pct'] <= 0:
        print("❌ Strategy is LOSING money")
        viable = False
    else:
        print(f"✅ Strategy is PROFITABLE: +{best['return_pct']:.2f}%")

    if best['vs_buy_hold'] <= 0:
        print("❌ Strategy UNDERPERFORMS buy & hold")
        viable = False
    else:
        print(f"✅ Strategy BEATS buy & hold by {best['vs_buy_hold']:.2f}%")

    if best['trades'] < 2:
        print(f"⚠️  Only {best['trades']} trade(s) - limited data")
    else:
        print(f"✅ {best['trades']} trades - reasonable sample")

    if best['win_rate'] == 0 and best['trades'] > 0:
        print("⚠️  No winning trades yet (may have open positions)")
    elif best['win_rate'] >= 50:
        print(f"✅ Win rate {best['win_rate']:.0f}% - good consistency")

    # Final verdict
    print("\n" + "="*70)
    if viable and best['return_pct'] > 0 and best['vs_buy_hold'] > 0:
        print("🎉 VIABLE STRATEGY FOUND!")
    else:
        print("⚠️  STRATEGY NEEDS REFINEMENT")
    print("="*70 + "\n")

    # Configuration
    print("WINNING CONFIGURATION:")
    print(f"  Entry: {best['config']['entry_mode']}")
    print(f"  Dump threshold: {best['config']['dump_threshold_pct']}% from 9:30 AM open")
    print(f"  Exit: {best['config']['exit_mode']}")
    if best['config']['exit_mode'] == 'trailing_stop_no_loss':
        print(f"  Trailing stop: {best['config'].get('trailing_stop_pct', 1.5)}%")
    if 'entry_window_end' in best['config'] and best['config']['entry_window_end']:
        print(f"  Entry window: {best['config']['market_open_hour']}:30-{best['config']['entry_window_end']}:30 AM")
    else:
        print(f"  Entry hour: {best['config']['market_open_hour']} AM")

    # Save results
    df.to_csv('results/strategy_development.csv', index=False)
    print(f"\n💾 Saved results to: results/strategy_development.csv\n")


if __name__ == "__main__":
    main()
