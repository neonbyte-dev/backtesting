#!/usr/bin/env python3
"""
BH Insights Multi-Asset Backtest Runner

Tests the BH Insights signal strategy across multiple assets
and compares performance.
"""

import sys
sys.path.insert(0, 'src')

import os
import pandas as pd
from datetime import timedelta

from utils.data_fetcher import DataFetcher
from strategies.bh_insights_multi_asset import BHInsightsMultiAssetStrategy, SingleAssetBHStrategy
from backtester_with_shorts import BacktesterWithShorts


def run_single_asset_backtest(strategy, asset, initial_capital=10000):
    """Run backtest for a single asset"""
    print(f"\n{'='*60}")
    print(f"BACKTESTING {asset}")
    print(f"{'='*60}")

    # Get signals for this asset
    asset_signals = strategy.get_signals_for_asset(asset)

    if asset_signals.empty:
        print(f"No signals found for {asset}")
        return None

    high_conf = asset_signals[asset_signals['confidence'] == 'high']
    print(f"Total signals: {len(asset_signals)} (high confidence: {len(high_conf)})")

    # Get signal date range
    signal_start = asset_signals['timestamp'].min()
    signal_end = asset_signals['timestamp'].max()
    days_needed = (signal_end - signal_start).days + 30

    print(f"Signal period: {signal_start.date()} to {signal_end.date()}")

    # Fetch price data
    fetcher = DataFetcher()
    symbol = f"{asset}/USDT"

    try:
        data = fetcher.fetch_ohlcv(symbol, '1h', days_back=days_needed)
    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")
        return None

    # Filter to signal period
    data = data[data.index >= (signal_start - pd.Timedelta(days=1))]

    if len(data) == 0:
        print(f"No price data in signal period")
        return None

    # Create single-asset strategy wrapper
    single_strategy = SingleAssetBHStrategy(asset, strategy)

    # Run backtest
    backtester = BacktesterWithShorts(
        initial_capital=initial_capital,
        fee_percent=0.1,
        display_timezone='America/New_York'
    )

    results = backtester.run(data, single_strategy, silent=True)

    # Print summary
    print(f"\nRESULTS:")
    print(f"  Strategy Return: {results['total_return_pct']:+.2f}%")
    print(f"  Buy & Hold:      {results['buy_hold_return_pct']:+.2f}%")
    print(f"  Alpha:           {results['total_return_pct'] - results['buy_hold_return_pct']:+.2f}%")
    print(f"  Trades:          {results['total_trades']} (L:{results['long_trades']}/S:{results['short_trades']})")
    print(f"  Win Rate:        {results['win_rate']:.1f}%")
    print(f"  Max Drawdown:    {results['max_drawdown']:.2f}%")

    return results


def run_multi_asset_backtest():
    """Run backtests across all assets with sufficient signals"""

    print("\n" + "="*70)
    print("BH INSIGHTS MULTI-ASSET BACKTEST")
    print("="*70)

    # Initialize strategy
    strategy = BHInsightsMultiAssetStrategy(
        messages_path='data/bh_insights_messages.csv',
        hold_hours=720  # 30 days - positions close on EXIT signal, not timeout
    )

    # Show signal summary
    print("\n=== SIGNAL SUMMARY ===\n")
    summary = strategy.get_signal_summary()
    print(summary)

    # Get assets with enough signals
    assets_to_test = []
    for asset in strategy.SUPPORTED_ASSETS:
        signals = strategy.get_signals_for_asset(asset)
        high_conf = signals[signals['confidence'] == 'high'] if not signals.empty else pd.DataFrame()
        if len(high_conf) >= 2:  # At least 2 high-confidence signals
            assets_to_test.append((asset, len(high_conf)))

    print(f"\n=== ASSETS WITH ≥2 HIGH-CONFIDENCE SIGNALS ===")
    for asset, count in sorted(assets_to_test, key=lambda x: -x[1]):
        print(f"  {asset}: {count} signals")

    # Run backtests
    all_results = {}

    for asset, _ in sorted(assets_to_test, key=lambda x: -x[1]):
        try:
            results = run_single_asset_backtest(strategy, asset)
            if results:
                all_results[asset] = results
        except Exception as e:
            print(f"Error backtesting {asset}: {e}")

    # === COMPARISON TABLE ===
    print("\n" + "="*80)
    print("MULTI-ASSET COMPARISON")
    print("="*80)

    print(f"\n{'Asset':<10} {'Return %':>10} {'Buy&Hold %':>12} {'Alpha %':>10} "
          f"{'Trades':>8} {'Win%':>8} {'MaxDD%':>10}")
    print("-" * 80)

    comparison_data = []
    for asset, results in sorted(all_results.items(),
                                  key=lambda x: x[1]['total_return_pct'] - x[1]['buy_hold_return_pct'],
                                  reverse=True):
        alpha = results['total_return_pct'] - results['buy_hold_return_pct']
        print(f"{asset:<10} {results['total_return_pct']:>+10.2f} {results['buy_hold_return_pct']:>+12.2f} "
              f"{alpha:>+10.2f} {results['total_trades']:>8} "
              f"{results['win_rate']:>8.1f} {results['max_drawdown']:>10.2f}")

        comparison_data.append({
            'Asset': asset,
            'Strategy_Return_Pct': results['total_return_pct'],
            'BuyHold_Return_Pct': results['buy_hold_return_pct'],
            'Alpha_Pct': alpha,
            'Total_Trades': results['total_trades'],
            'Long_Trades': results['long_trades'],
            'Short_Trades': results['short_trades'],
            'Win_Rate_Pct': results['win_rate'],
            'Max_Drawdown_Pct': results['max_drawdown'],
            'Final_Value': results['final_value'],
            'Avg_Win': results['avg_win'],
            'Avg_Loss': results['avg_loss']
        })

    # === AGGREGATE STATS ===
    if all_results:
        print("\n" + "="*80)
        print("AGGREGATE STATISTICS")
        print("="*80)

        total_alpha = sum(r['total_return_pct'] - r['buy_hold_return_pct'] for r in all_results.values())
        avg_alpha = total_alpha / len(all_results)
        avg_win_rate = sum(r['win_rate'] for r in all_results.values()) / len(all_results)

        positive_alpha = sum(1 for r in all_results.values()
                            if r['total_return_pct'] > r['buy_hold_return_pct'])

        print(f"\nAssets tested: {len(all_results)}")
        print(f"Assets with positive alpha: {positive_alpha}/{len(all_results)} "
              f"({positive_alpha/len(all_results)*100:.0f}%)")
        print(f"Average alpha: {avg_alpha:+.2f}%")
        print(f"Average win rate: {avg_win_rate:.1f}%")

        # Best and worst
        best = max(all_results.items(), key=lambda x: x[1]['total_return_pct'] - x[1]['buy_hold_return_pct'])
        worst = min(all_results.items(), key=lambda x: x[1]['total_return_pct'] - x[1]['buy_hold_return_pct'])

        print(f"\nBest alpha: {best[0]} ({best[1]['total_return_pct'] - best[1]['buy_hold_return_pct']:+.2f}%)")
        print(f"Worst alpha: {worst[0]} ({worst[1]['total_return_pct'] - worst[1]['buy_hold_return_pct']:+.2f}%)")

    # Save results
    os.makedirs('results', exist_ok=True)

    if comparison_data:
        df = pd.DataFrame(comparison_data)
        df = df.sort_values('Alpha_Pct', ascending=False)
        df.to_csv('results/bh_insights_multi_asset.csv', index=False)
        print(f"\nResults saved to results/bh_insights_multi_asset.csv")

    return all_results


if __name__ == "__main__":
    results = run_multi_asset_backtest()
