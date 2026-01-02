"""
Optimize for Trade Frequency - December Only

Goal: Find strategy with at least 5 trades in December while staying profitable
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
        'results': results
    }


def main():
    print("\n" + "="*70)
    print("🎯 OPTIMIZING FOR TRADE FREQUENCY - DECEMBER 2025")
    print("="*70 + "\n")

    # Fetch December data
    print("Fetching December Bitcoin data...\n")
    fetcher = DataFetcher()
    data = fetcher.fetch_ohlcv('BTC/USDT', '15m', days_back=33)  # Dec 1 - Jan 2

    # Filter to December only
    dec_data = data[(data.index >= '2025-12-01') & (data.index < '2026-01-01')]

    print(f"December period: {dec_data.index[0]} to {dec_data.index[-1]}")
    print(f"Total candles: {len(dec_data)}\n")

    print("="*70)
    print("GOAL: At least 5 trades + profitable")
    print("="*70 + "\n")

    variations = []

    # Test lower thresholds for more trades
    print("GROUP 1: Lower Dump Thresholds\n")

    for threshold in [-0.5, -0.75, -1.0, -1.25, -1.5]:
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

    # Test different trailing stops with -1% threshold
    print("GROUP 2: Different Trailing Stops (-1% dump)\n")

    for trail in [1.0, 1.5, 2.0]:
        variations.append({
            'name': f'Dump -1% @ 10AM → {trail}% trail',
            'config': {
                'entry_mode': 'on_dump',
                'exit_mode': 'trailing_stop_no_loss',
                'dump_threshold_pct': -1.0,
                'trailing_stop_pct': trail,
                'market_open_hour': 10,
            }
        })

    # Test wider entry windows with -1% threshold
    print("GROUP 3: Wider Entry Windows\n")

    variations.append({
        'name': 'Dump -1% @ 9:30-11:30 AM → 1.5% trail',
        'config': {
            'entry_mode': 'on_dump',
            'exit_mode': 'trailing_stop_no_loss',
            'dump_threshold_pct': -1.0,
            'trailing_stop_pct': 1.5,
            'market_open_hour': 9,
            'entry_window_end': 11,
        }
    })

    variations.append({
        'name': 'Dump -0.75% @ 9:30-11:30 AM → 1.5% trail',
        'config': {
            'entry_mode': 'on_dump',
            'exit_mode': 'trailing_stop_no_loss',
            'dump_threshold_pct': -0.75,
            'trailing_stop_pct': 1.5,
            'market_open_hour': 9,
            'entry_window_end': 11,
        }
    })

    print(f"Total variations: {len(variations)}\n")
    print("="*70 + "\n")

    # Run tests
    results = []

    for i, var in enumerate(variations, 1):
        print(f"\n{'─'*70}")
        print(f"TEST {i}/{len(variations)}: {var['name']}")
        print(f"{'─'*70}")

        result = test_strategy(dec_data, var['config'], var['name'])
        results.append(result)

    # Summary
    print("\n" + "="*70)
    print("📊 ALL RESULTS")
    print("="*70 + "\n")

    df = pd.DataFrame([
        {
            'Strategy': r['name'],
            'Trades': r['trades'],
            'Return %': r['return_pct'],
            'vs B&H': r['vs_buy_hold'],
            'Win %': r['win_rate'],
            'Max DD %': r['max_dd'],
        }
        for r in results
    ])

    # Sort by number of trades first, then return
    df = df.sort_values(['Trades', 'Return %'], ascending=[False, False])
    print(df.to_string(index=False))

    # Filter for strategies with 5+ trades
    print("\n" + "="*70)
    print("🎯 STRATEGIES WITH 5+ TRADES")
    print("="*70 + "\n")

    viable = df[df['Trades'] >= 5]

    if len(viable) == 0:
        print("❌ No strategies achieved 5+ trades in December")
        print("\nBest by trade count:")
        best_by_trades = df.iloc[0]
        print(f"  {best_by_trades['Strategy']}")
        print(f"  Trades: {best_by_trades['Trades']}")
        print(f"  Return: {best_by_trades['Return %']:+.2f}%")
    else:
        print(viable.to_string(index=False))

        # Best with 5+ trades
        print("\n" + "="*70)
        print("🏆 BEST STRATEGY WITH 5+ TRADES")
        print("="*70 + "\n")

        # Sort by return among those with 5+ trades
        best_idx = viable['Return %'].idxmax()
        best = results[best_idx]

        print(f"Strategy: {best['name']}")
        print(f"\nPerformance:")
        print(f"  Return:        {best['return_pct']:+.2f}%")
        print(f"  vs Buy & Hold: {best['vs_buy_hold']:+.2f}%")
        print(f"  Final Value:   ${best['final_value']:,.2f}")
        print(f"\nTrade Stats:")
        print(f"  Total Trades:  {best['trades']}")
        print(f"  Win Rate:      {best['win_rate']:.1f}%")
        print(f"  Max Drawdown:  {best['max_dd']:.2f}%")

        # Configuration
        print(f"\nCONFIGURATION:")
        print(f"  Dump threshold: {best['config']['dump_threshold_pct']}%")
        print(f"  Trailing stop:  {best['config'].get('trailing_stop_pct', 1.5)}%")
        if 'entry_window_end' in best['config'] and best['config']['entry_window_end']:
            print(f"  Entry window:   {best['config']['market_open_hour']}:30-{best['config']['entry_window_end']}:30 AM")
        else:
            print(f"  Entry hour:     {best['config']['market_open_hour']} AM")

        # Viability check
        print("\n" + "="*70)
        print("✅ VIABILITY CHECK")
        print("="*70 + "\n")

        if best['return_pct'] > 0:
            print(f"✅ PROFITABLE: +{best['return_pct']:.2f}%")
        else:
            print(f"❌ LOSING: {best['return_pct']:.2f}%")

        if best['vs_buy_hold'] > 0:
            print(f"✅ BEATS buy & hold by {best['vs_buy_hold']:.2f}%")
        else:
            print(f"❌ Underperforms buy & hold by {abs(best['vs_buy_hold']):.2f}%")

        if best['trades'] >= 5:
            print(f"✅ {best['trades']} trades - meets requirement")

        if best['win_rate'] >= 50:
            print(f"✅ Win rate {best['win_rate']:.0f}% - good")
        else:
            print(f"⚠️  Win rate {best['win_rate']:.0f}% - needs improvement")

    # Save
    df.to_csv('results/frequency_optimization.csv', index=False)
    print(f"\n💾 Saved to: results/frequency_optimization.csv\n")


if __name__ == "__main__":
    main()
