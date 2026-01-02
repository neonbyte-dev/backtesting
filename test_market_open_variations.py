"""
Market Open Dump Strategy - Test Multiple Variations

This script tests different combinations of entry/exit rules to find
the best way to trade the "10 AM dump" pattern.

We'll test:
- 3 entry modes (immediate, on_dump, intraday_low)
- 3 exit modes (eod, fixed_hours, profit_target)
- Different thresholds and parameters

Then compare all results to find the winner.
"""

import sys
sys.path.append('src')

import pandas as pd
from utils.data_fetcher import DataFetcher
from backtester import Backtester
from strategies.market_open_dump import MarketOpenDumpStrategy


def run_single_variation(data, strategy_config, initial_capital=10000):
    """
    Run a single strategy variation

    Returns:
        Dictionary with strategy config and results
    """
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
    print("🧪 MARKET OPEN DUMP STRATEGY - VARIATIONS TEST")
    print("="*70 + "\n")

    # ==========================================
    # STEP 1: Fetch Intraday Data
    # ==========================================
    print("STEP 1: Fetching intraday Bitcoin data...")
    print("(We need fine-grained data to capture 10 AM movements)\n")

    fetcher = DataFetcher()

    # Use 5-minute candles to capture intraday patterns
    # Test since early November (when pattern was strongest per tweet)
    SYMBOL = 'BTC/USDT'
    TIMEFRAME = '15m'  # 15-minute candles (good balance of detail vs data limits)
    DAYS_BACK = 60     # ~2 months of data

    data = fetcher.fetch_ohlcv(SYMBOL, TIMEFRAME, days_back=DAYS_BACK)

    print(f"\n✓ Fetched {len(data)} candles from {data.index[0]} to {data.index[-1]}\n")

    # ==========================================
    # STEP 2: Define Strategy Variations to Test
    # ==========================================
    print("STEP 2: Defining strategy variations to test...\n")

    variations = []

    # Group 1: Different entry modes with end-of-day exit
    variations.append({
        'name': 'Immediate @ 10 AM → Exit EOD',
        'entry_mode': 'immediate',
        'exit_mode': 'eod',
    })

    variations.append({
        'name': 'Wait for -0.5% dump → Exit EOD',
        'entry_mode': 'on_dump',
        'exit_mode': 'eod',
        'dump_threshold_pct': -0.5,
    })

    variations.append({
        'name': 'Wait for -1% dump → Exit EOD',
        'entry_mode': 'on_dump',
        'exit_mode': 'eod',
        'dump_threshold_pct': -1.0,
    })

    variations.append({
        'name': 'Wait for -2% dump → Exit EOD',
        'entry_mode': 'on_dump',
        'exit_mode': 'eod',
        'dump_threshold_pct': -2.0,
    })

    # Group 2: Best entry mode with different exit times
    variations.append({
        'name': 'On -1% dump → Exit after 4 hours',
        'entry_mode': 'on_dump',
        'exit_mode': 'fixed_hours',
        'dump_threshold_pct': -1.0,
        'exit_hours': 4,
    })

    variations.append({
        'name': 'On -1% dump → Exit after 6 hours',
        'entry_mode': 'on_dump',
        'exit_mode': 'fixed_hours',
        'dump_threshold_pct': -1.0,
        'exit_hours': 6,
    })

    # Group 3: Profit target exits
    variations.append({
        'name': 'On -1% dump → Exit at +0.5% profit',
        'entry_mode': 'on_dump',
        'exit_mode': 'profit_target',
        'dump_threshold_pct': -1.0,
        'profit_target_pct': 0.5,
    })

    variations.append({
        'name': 'On -1% dump → Exit at +1% profit',
        'entry_mode': 'on_dump',
        'exit_mode': 'profit_target',
        'dump_threshold_pct': -1.0,
        'profit_target_pct': 1.0,
    })

    # Group 4: Hindsight test (shows max potential)
    variations.append({
        'name': 'Buy intraday low (hindsight) → Exit EOD',
        'entry_mode': 'intraday_low',
        'exit_mode': 'eod',
    })

    print(f"✓ Testing {len(variations)} different variations\n")

    # ==========================================
    # STEP 3: Run All Variations
    # ==========================================
    print("="*70)
    print("STEP 3: Running backtests...")
    print("="*70 + "\n")

    all_results = []

    for i, var_config in enumerate(variations, 1):
        print(f"\n{'─'*70}")
        print(f"VARIATION {i}/{len(variations)}: {var_config['name']}")
        print(f"{'─'*70}")

        # Remove 'name' from config before passing to strategy
        strategy_params = {k: v for k, v in var_config.items() if k != 'name'}

        result = run_single_variation(data, strategy_params)
        result['name'] = var_config['name']
        all_results.append(result)

    # ==========================================
    # STEP 4: Compare Results
    # ==========================================
    print("\n" + "="*70)
    print("📊 COMPARISON OF ALL VARIATIONS")
    print("="*70 + "\n")

    # Create comparison table
    comparison_df = pd.DataFrame([
        {
            'Strategy': r['name'],
            'Total Return %': r['results']['total_return_pct'],
            'Total Trades': r['results']['total_trades'],
            'Win Rate %': r['results']['win_rate'],
            'Max Drawdown %': r['results']['max_drawdown'],
            'Final Value $': r['results']['final_value'],
        }
        for r in all_results
    ])

    # Sort by total return (best first)
    comparison_df = comparison_df.sort_values('Total Return %', ascending=False)

    # Print table
    print(comparison_df.to_string(index=False))

    # ==========================================
    # STEP 5: Identify Best Strategy
    # ==========================================
    print("\n" + "="*70)
    print("🏆 BEST PERFORMING STRATEGY")
    print("="*70 + "\n")

    best = all_results[comparison_df.index[0]]

    print(f"Strategy: {best['name']}")
    print(f"")
    print(f"Return: {best['results']['total_return_pct']:+.2f}%")
    print(f"Final Value: ${best['results']['final_value']:,.2f}")
    print(f"Total Trades: {best['results']['total_trades']}")
    print(f"Win Rate: {best['results']['win_rate']:.1f}%")
    print(f"Max Drawdown: {best['results']['max_drawdown']:.2f}%")

    # Compare to buy & hold
    buy_hold_return = best['results']['buy_hold_return_pct']
    outperformance = best['results']['total_return_pct'] - buy_hold_return

    print(f"\nBuy & Hold Return: {buy_hold_return:+.2f}%")
    print(f"Strategy vs Buy & Hold: {outperformance:+.2f}%")

    if outperformance > 0:
        print(f"\n✅ Strategy BEATS buy & hold by {outperformance:.2f}%")
    else:
        print(f"\n❌ Strategy UNDERPERFORMS buy & hold by {abs(outperformance):.2f}%")

    # ==========================================
    # STEP 6: Save Results
    # ==========================================
    print("\n" + "="*70)
    print("💾 Saving results...")
    print("="*70 + "\n")

    # Save comparison table
    comparison_df.to_csv('results/market_open_dump_comparison.csv', index=False)
    print("✓ Saved comparison table to: results/market_open_dump_comparison.csv")

    # Save best strategy details
    best_trades_df = pd.DataFrame(best['results']['trades'])
    if len(best_trades_df) > 0:
        best_trades_df.to_csv('results/market_open_dump_best_trades.csv', index=False)
        print("✓ Saved best strategy trades to: results/market_open_dump_best_trades.csv")

    print("\n✅ Analysis complete!\n")

    # ==========================================
    # STEP 7: Print Insights
    # ==========================================
    print("="*70)
    print("💡 KEY INSIGHTS")
    print("="*70 + "\n")

    print("1. PATTERN VALIDATION:")
    if best['results']['total_trades'] > 0:
        print(f"   ✓ Strategy generated {best['results']['total_trades']} trades")
        print(f"   ✓ Pattern appears {best['results']['total_trades'] / DAYS_BACK * 30:.1f} times per month")
    else:
        print(f"   ✗ No trades triggered - pattern may not exist in this data")

    print("\n2. PROFITABILITY:")
    if best['results']['total_return_pct'] > 0:
        print(f"   ✓ Best strategy returned {best['results']['total_return_pct']:+.2f}%")
    else:
        print(f"   ✗ Best strategy lost {best['results']['total_return_pct']:.2f}%")

    print("\n3. CONSISTENCY:")
    if best['results']['win_rate'] > 50:
        print(f"   ✓ Win rate {best['results']['win_rate']:.1f}% (more wins than losses)")
    else:
        print(f"   ✗ Win rate {best['results']['win_rate']:.1f}% (more losses than wins)")

    print("\n4. COMPARISON TO BUY & HOLD:")
    if outperformance > 5:
        print(f"   ✓ Strategy significantly outperforms ({outperformance:+.2f}%)")
    elif outperformance > 0:
        print(f"   ~ Strategy slightly outperforms ({outperformance:+.2f}%)")
    else:
        print(f"   ✗ Strategy underperforms - just holding BTC is better")

    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    main()
