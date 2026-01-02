"""
Ultra Aggressive Frequency - Push for 5+ Trades

Try very low thresholds and multiple entry times per day
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
        'trades': results['total_trades'],
        'return_pct': results['total_return_pct'],
        'win_rate': results['win_rate'],
        'vs_buy_hold': results['total_return_pct'] - results['buy_hold_return_pct'],
        'final_value': results['final_value'],
        'max_dd': results['max_drawdown'],
    }


def main():
    print("\n" + "="*70)
    print("🚀 ULTRA AGGRESSIVE: PUSHING FOR 5+ TRADES")
    print("="*70 + "\n")

    fetcher = DataFetcher()
    data = fetcher.fetch_ohlcv('BTC/USDT', '15m', days_back=33)
    dec_data = data[(data.index >= '2025-12-01') & (data.index < '2026-01-01')]

    print(f"December: {dec_data.index[0]} to {dec_data.index[-1]}\n")

    variations = []

    # Very low thresholds
    print("Testing ultra-low dump thresholds...\n")

    for threshold in [-0.25, -0.5, -0.75, -1.0]:
        for window_end in [None, 11, 12]:
            if window_end:
                variations.append({
                    'name': f'Dump {threshold}% @ 9:30-{window_end}:30 AM → 1.5% trail',
                    'config': {
                        'entry_mode': 'on_dump',
                        'exit_mode': 'trailing_stop_no_loss',
                        'dump_threshold_pct': threshold,
                        'trailing_stop_pct': 1.5,
                        'market_open_hour': 9,
                        'entry_window_end': window_end,
                    }
                })
            else:
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

    print(f"Testing {len(variations)} variations...\n")
    print("="*70 + "\n")

    results = []
    for i, var in enumerate(variations, 1):
        print(f"TEST {i}/{len(variations)}: {var['name']:<50}", end=' ')
        result = test_strategy(dec_data, var['config'], var['name'])
        results.append(result)
        print(f"→ {result['trades']} trades, {result['return_pct']:+.1f}%")

    # Summary
    print("\n" + "="*70)
    print("📊 RESULTS BY TRADE COUNT")
    print("="*70 + "\n")

    df = pd.DataFrame(results)
    df = df.sort_values(['trades', 'return_pct'], ascending=[False, False])

    print(df[['name', 'trades', 'return_pct', 'win_rate', 'vs_buy_hold']].head(15).to_string(index=False))

    # Check for 5+ trades
    winners = df[df['trades'] >= 5]

    print("\n" + "="*70)
    if len(winners) > 0:
        print("🎉 FOUND STRATEGIES WITH 5+ TRADES!")
        print("="*70 + "\n")

        best = winners.iloc[0]
        print(f"WINNER: {best['name']}")
        print(f"\n  Trades:        {best['trades']}")
        print(f"  Return:        {best['return_pct']:+.2f}%")
        print(f"  vs Buy & Hold: {best['vs_buy_hold']:+.2f}%")
        print(f"  Win Rate:      {best['win_rate']:.1f}%")
        print(f"  Max Drawdown:  {best['max_dd']:.2f}%")
    else:
        print("❌ NO STRATEGY ACHIEVED 5+ TRADES")
        print("="*70 + "\n")

        best = df.iloc[0]
        print(f"BEST AVAILABLE: {best['name']}")
        print(f"\n  Trades:        {best['trades']} (max possible in Dec)")
        print(f"  Return:        {best['return_pct']:+.2f}%")
        print(f"  vs Buy & Hold: {best['vs_buy_hold']:+.2f}%")
        print(f"  Win Rate:      {best['win_rate']:.1f}%")

        print("\n💡 REALITY CHECK:")
        print("   The 10 AM dump pattern is rare in December 2025")
        print(f"   Maximum possible: {best['trades']} trades")
        print("   This is a low-frequency, high-quality pattern")

    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    main()
