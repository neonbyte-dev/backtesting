#!/usr/bin/env python3
"""
BH Insights V2 Multi-Asset Backtest

Improved signal extraction and multi-asset backtesting.
"""

import sys
sys.path.insert(0, 'src')

import os
import pandas as pd
from datetime import timedelta

from utils.data_fetcher import DataFetcher
from strategies.bh_insights_v2 import BHInsightsStrategyV2, SingleAssetStrategy
from backtester_with_shorts import BacktesterWithShorts


def run_asset_backtest(strategy, asset, initial_capital=10000, verbose=True):
    """Run backtest for a single asset"""

    asset_signals = strategy.get_signals_for_asset(asset)

    if asset_signals.empty:
        if verbose:
            print(f"  No signals for {asset}")
        return None

    # Get date range
    signal_start = asset_signals['timestamp'].min()
    signal_end = asset_signals['timestamp'].max()
    days_needed = (signal_end - signal_start).days + 30

    if verbose:
        print(f"\n{'='*60}")
        print(f"{asset}: {len(asset_signals)} signals ({signal_start.date()} to {signal_end.date()})")
        print(f"{'='*60}")

        # Show signal breakdown
        by_action = asset_signals['action'].value_counts()
        print(f"  LONG: {by_action.get('LONG', 0)}, SHORT: {by_action.get('SHORT', 0)}, EXIT: {by_action.get('EXIT', 0)}")

    # Fetch price data
    fetcher = DataFetcher()

    # Map asset to trading symbol
    if asset in ['GOLD', 'SILVER']:
        # Commodities - use Binance PAXG for gold proxy, or skip
        if verbose:
            print(f"  Skipping {asset} - commodities not available on Binance")
        return None

    symbol = f"{asset}/USDT"

    try:
        data = fetcher.fetch_ohlcv(symbol, '1h', days_back=days_needed)
    except Exception as e:
        if verbose:
            print(f"  Error fetching {symbol}: {e}")
        return None

    # Filter to signal period
    data = data[data.index >= (signal_start - pd.Timedelta(days=1))]

    if len(data) == 0:
        if verbose:
            print(f"  No price data for signal period")
        return None

    # Create wrapper strategy
    single_strategy = SingleAssetStrategy(asset, strategy)

    # Run backtest
    backtester = BacktesterWithShorts(
        initial_capital=initial_capital,
        fee_percent=0.1,
        display_timezone='America/New_York'
    )

    results = backtester.run(data, single_strategy, silent=True)

    if verbose:
        alpha = results['total_return_pct'] - results['buy_hold_return_pct']
        print(f"\n  Strategy: {results['total_return_pct']:+.2f}%  |  Buy&Hold: {results['buy_hold_return_pct']:+.2f}%  |  Alpha: {alpha:+.2f}%")
        print(f"  Trades: {results['total_trades']} (L:{results['long_trades']}/S:{results['short_trades']})  |  Win Rate: {results['win_rate']:.1f}%  |  MaxDD: {results['max_drawdown']:.2f}%")

    return results


def main():
    print("\n" + "="*70)
    print("BH INSIGHTS V2 - MULTI-ASSET BACKTEST")
    print("="*70)

    # Initialize strategy
    strategy = BHInsightsStrategyV2(
        messages_path='data/bh_insights_messages.csv',
        hold_hours=72  # Auto-close after 72 hours if no exit
    )

    # Get signal summary
    print("\n=== SIGNAL SUMMARY ===\n")
    summary = strategy.get_signal_summary()
    print(summary)

    # Find assets with enough signals (at least 3)
    assets_to_test = []
    for asset in strategy.ALL_ASSETS:
        signals = strategy.get_signals_for_asset(asset)
        if len(signals) >= 3:
            assets_to_test.append((asset, len(signals)))

    print(f"\n=== ASSETS WITH ≥3 SIGNALS ===")
    for asset, count in sorted(assets_to_test, key=lambda x: -x[1]):
        print(f"  {asset}: {count} signals")

    # Run backtests
    print("\n" + "="*70)
    print("RUNNING BACKTESTS")
    print("="*70)

    all_results = {}

    for asset, _ in sorted(assets_to_test, key=lambda x: -x[1]):
        try:
            results = run_asset_backtest(strategy, asset, initial_capital=10000, verbose=True)
            if results:
                all_results[asset] = results
        except Exception as e:
            print(f"  Error with {asset}: {e}")

    # === FINAL COMPARISON ===
    if all_results:
        print("\n" + "="*80)
        print("FINAL COMPARISON - SORTED BY ALPHA")
        print("="*80)

        print(f"\n{'Asset':<12} {'Return%':>10} {'BuyHold%':>10} {'Alpha%':>10} {'Trades':>8} {'Win%':>8} {'MaxDD%':>10}")
        print("-" * 80)

        comparison_data = []
        for asset, results in sorted(all_results.items(),
                                      key=lambda x: x[1]['total_return_pct'] - x[1]['buy_hold_return_pct'],
                                      reverse=True):
            alpha = results['total_return_pct'] - results['buy_hold_return_pct']
            print(f"{asset:<12} {results['total_return_pct']:>+10.2f} {results['buy_hold_return_pct']:>+10.2f} "
                  f"{alpha:>+10.2f} {results['total_trades']:>8} "
                  f"{results['win_rate']:>8.1f} {results['max_drawdown']:>10.2f}")

            comparison_data.append({
                'Asset': asset,
                'Strategy_Return_Pct': round(results['total_return_pct'], 2),
                'BuyHold_Return_Pct': round(results['buy_hold_return_pct'], 2),
                'Alpha_Pct': round(alpha, 2),
                'Total_Trades': results['total_trades'],
                'Long_Trades': results['long_trades'],
                'Short_Trades': results['short_trades'],
                'Win_Rate_Pct': round(results['win_rate'], 1),
                'Max_Drawdown_Pct': round(results['max_drawdown'], 2),
                'Final_Value': round(results['final_value'], 2),
            })

        # Aggregate stats
        print("\n" + "="*80)
        print("AGGREGATE STATISTICS")
        print("="*80)

        alphas = [r['total_return_pct'] - r['buy_hold_return_pct'] for r in all_results.values()]
        positive_alpha = sum(1 for a in alphas if a > 0)

        print(f"\nAssets tested: {len(all_results)}")
        print(f"Positive alpha: {positive_alpha}/{len(all_results)} ({positive_alpha/len(all_results)*100:.0f}%)")
        print(f"Average alpha: {sum(alphas)/len(alphas):+.2f}%")
        print(f"Best: {max(alphas):+.2f}%")
        print(f"Worst: {min(alphas):+.2f}%")

        # Save
        os.makedirs('results', exist_ok=True)
        df = pd.DataFrame(comparison_data)
        df = df.sort_values('Alpha_Pct', ascending=False)
        df.to_csv('results/bh_insights_v2_backtest.csv', index=False)
        print(f"\nResults saved to results/bh_insights_v2_backtest.csv")

    return all_results


if __name__ == "__main__":
    main()
