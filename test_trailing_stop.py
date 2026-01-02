"""
Test Market Open Dump Strategy with Trailing Stop (No Loss)

This tests the modified exit criteria:
- NEVER sell for a loss (hold until profitable)
- Once profitable: use 1.5% trailing stop

We'll test this with different entry strategies to find the best combination.
"""

import sys
sys.path.append('src')

import pandas as pd
from utils.data_fetcher import DataFetcher
from backtester import Backtester
from strategies.market_open_dump import MarketOpenDumpStrategy


def run_variation(data, strategy_config, initial_capital=10000):
    """Run a single strategy variation"""
    strategy = MarketOpenDumpStrategy(**strategy_config)

    backtester = Backtester(
        initial_capital=initial_capital,
        fee_percent=0.1
    )

    results = backtester.run(data, strategy)

    return {
        'config': strategy_config,
        'results': results
    }


def main():
    print("\n" + "="*70)
    print("🧪 TRAILING STOP STRATEGY TEST (Never Sell for Loss)")
    print("="*70 + "\n")

    # Fetch data
    print("Fetching Bitcoin data...\n")
    fetcher = DataFetcher()

    SYMBOL = 'BTC/USDT'
    TIMEFRAME = '15m'
    DAYS_BACK = 60

    data = fetcher.fetch_ohlcv(SYMBOL, TIMEFRAME, days_back=DAYS_BACK)

    print(f"\n✓ Fetched {len(data)} candles\n")

    # Define variations to test
    print("="*70)
    print("TESTING TRAILING STOP WITH DIFFERENT ENTRY STRATEGIES")
    print("="*70 + "\n")

    variations = []

    # Test with different dump thresholds
    variations.append({
        'name': 'Wait for -0.5% dump → Trailing stop 1.5%',
        'entry_mode': 'on_dump',
        'exit_mode': 'trailing_stop_no_loss',
        'dump_threshold_pct': -0.5,
        'trailing_stop_pct': 1.5,
    })

    variations.append({
        'name': 'Wait for -1% dump → Trailing stop 1.5%',
        'entry_mode': 'on_dump',
        'exit_mode': 'trailing_stop_no_loss',
        'dump_threshold_pct': -1.0,
        'trailing_stop_pct': 1.5,
    })

    variations.append({
        'name': 'Wait for -1.5% dump → Trailing stop 1.5%',
        'entry_mode': 'on_dump',
        'exit_mode': 'trailing_stop_no_loss',
        'dump_threshold_pct': -1.5,
        'trailing_stop_pct': 1.5,
    })

    variations.append({
        'name': 'Wait for -2% dump → Trailing stop 1.5%',
        'entry_mode': 'on_dump',
        'exit_mode': 'trailing_stop_no_loss',
        'dump_threshold_pct': -2.0,
        'trailing_stop_pct': 1.5,
    })

    # Test different trailing stop percentages
    variations.append({
        'name': 'Wait for -1% dump → Trailing stop 1%',
        'entry_mode': 'on_dump',
        'exit_mode': 'trailing_stop_no_loss',
        'dump_threshold_pct': -1.0,
        'trailing_stop_pct': 1.0,
    })

    variations.append({
        'name': 'Wait for -1% dump → Trailing stop 2%',
        'entry_mode': 'on_dump',
        'exit_mode': 'trailing_stop_no_loss',
        'dump_threshold_pct': -1.0,
        'trailing_stop_pct': 2.0,
    })

    # Test immediate entry with trailing stop
    variations.append({
        'name': 'Immediate @ 10 AM → Trailing stop 1.5%',
        'entry_mode': 'immediate',
        'exit_mode': 'trailing_stop_no_loss',
        'trailing_stop_pct': 1.5,
    })

    print(f"✓ Testing {len(variations)} variations\n")

    # Run all tests
    all_results = []

    for i, var_config in enumerate(variations, 1):
        print(f"\n{'─'*70}")
        print(f"VARIATION {i}/{len(variations)}: {var_config['name']}")
        print(f"{'─'*70}")

        strategy_params = {k: v for k, v in var_config.items() if k != 'name'}
        result = run_variation(data, strategy_params)
        result['name'] = var_config['name']
        all_results.append(result)

    # Compare results
    print("\n" + "="*70)
    print("📊 COMPARISON OF ALL TRAILING STOP VARIATIONS")
    print("="*70 + "\n")

    comparison_df = pd.DataFrame([
        {
            'Strategy': r['name'],
            'Return %': r['results']['total_return_pct'],
            'Trades': r['results']['total_trades'],
            'Win Rate %': r['results']['win_rate'],
            'Max DD %': r['results']['max_drawdown'],
            'Final Value $': r['results']['final_value'],
        }
        for r in all_results
    ])

    comparison_df = comparison_df.sort_values('Return %', ascending=False)
    print(comparison_df.to_string(index=False))

    # Best strategy
    print("\n" + "="*70)
    print("🏆 BEST TRAILING STOP STRATEGY")
    print("="*70 + "\n")

    best = all_results[comparison_df.index[0]]

    print(f"Strategy: {best['name']}")
    print(f"")
    print(f"Return: {best['results']['total_return_pct']:+.2f}%")
    print(f"Final Value: ${best['results']['final_value']:,.2f}")
    print(f"Trades: {best['results']['total_trades']}")
    print(f"Win Rate: {best['results']['win_rate']:.1f}%")
    print(f"Max Drawdown: {best['results']['max_drawdown']:.2f}%")

    buy_hold = best['results']['buy_hold_return_pct']
    outperformance = best['results']['total_return_pct'] - buy_hold

    print(f"\nBuy & Hold: {buy_hold:+.2f}%")
    print(f"Outperformance: {outperformance:+.2f}%")

    if outperformance > 0:
        print(f"\n✅ BEATS buy & hold by {outperformance:.2f}%")
    else:
        print(f"\n❌ UNDERPERFORMS buy & hold by {abs(outperformance):.2f}%")

    # Save results
    comparison_df.to_csv('results/trailing_stop_comparison.csv', index=False)
    print(f"\n💾 Saved to: results/trailing_stop_comparison.csv")

    # Analysis
    print("\n" + "="*70)
    print("💡 KEY INSIGHTS")
    print("="*70 + "\n")

    print("1. NEVER SELLING FOR A LOSS:")
    unsold_positions = best['results']['total_trades'] - len([t for t in best['results']['trades'] if t['type'] == 'SELL'])
    print(f"   Trades opened: {best['results']['total_trades']}")
    print(f"   Trades closed: {len([t for t in best['results']['trades'] if t['type'] == 'SELL'])}")
    if unsold_positions > 0:
        print(f"   ⚠️  Positions still open (waiting for profit): {unsold_positions}")
        print(f"   This means we're holding losing positions indefinitely")
    else:
        print(f"   ✓ All positions closed profitably")

    print("\n2. TRAILING STOP EFFECTIVENESS:")
    sell_trades = [t for t in best['results']['trades'] if t['type'] == 'SELL']
    if sell_trades:
        avg_profit = sum(t.get('pnl_percent', 0) for t in sell_trades) / len(sell_trades)
        print(f"   Average profit per closed trade: {avg_profit:+.2f}%")
        print(f"   Win rate: {best['results']['win_rate']:.1f}%")

    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    main()
