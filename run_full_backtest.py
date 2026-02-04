#!/usr/bin/env python3
"""
BH Insights Full Backtest - Including Commodities

Tests all assets including GOLD (via PAXG) and SILVER (via XAG futures).
"""

import sys
sys.path.insert(0, 'src')

import os
import pandas as pd
from datetime import timedelta

from utils.data_fetcher import DataFetcher
from utils.commodity_fetcher import CommodityFetcher
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

        by_action = asset_signals['action'].value_counts()
        print(f"  LONG: {by_action.get('LONG', 0)}, SHORT: {by_action.get('SHORT', 0)}, EXIT: {by_action.get('EXIT', 0)}")

    # Fetch price data - use appropriate fetcher
    if asset in ['GOLD', 'SILVER']:
        fetcher = CommodityFetcher()
        try:
            data = fetcher.fetch_ohlcv(asset, '1h', days_back=days_needed)
        except Exception as e:
            if verbose:
                print(f"  Error fetching {asset}: {e}")
            return None
    else:
        fetcher = DataFetcher()
        symbol = f"{asset}/USDT"
        try:
            data = fetcher.fetch_ohlcv(symbol, '1h', days_back=days_needed)
        except Exception as e:
            if verbose:
                print(f"  Error fetching {symbol}: {e}")
            return None

    if data.empty or len(data) == 0:
        if verbose:
            print(f"  No price data available")
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
        print(f"  Trades: {results['total_trades']} (L:{results['long_trades']}/S:{results['short_trades']})  |  Win Rate: {results['win_rate']:.1f}%")

    return results


def main():
    print("\n" + "="*70)
    print("BH INSIGHTS FULL BACKTEST - INCLUDING COMMODITIES")
    print("="*70)

    # Initialize strategy
    # No hold timeout - positions only close on Brandon's explicit exit signals
    strategy = BHInsightsStrategyV2(
        messages_path='data/bh_insights_messages.csv',
        hold_hours=None  # No timeout - exit only on explicit signals
    )

    # Get signal summary
    print("\n=== SIGNAL SUMMARY ===\n")
    summary = strategy.get_signal_summary()
    print(summary)

    # Assets to test (including commodities)
    assets_to_test = []
    for asset in strategy.ALL_ASSETS:
        signals = strategy.get_signals_for_asset(asset)
        if len(signals) >= 3:
            assets_to_test.append((asset, len(signals)))

    print(f"\n=== ASSETS TO TEST ===")
    for asset, count in sorted(assets_to_test, key=lambda x: -x[1]):
        commodity_tag = " [COMMODITY]" if asset in ['GOLD', 'SILVER'] else ""
        print(f"  {asset}: {count} signals{commodity_tag}")

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

        print(f"\n{'Asset':<12} {'Type':<8} {'Return%':>10} {'BuyHold%':>10} {'Alpha%':>10} {'Trades':>8} {'Win%':>8}")
        print("-" * 80)

        comparison_data = []
        for asset, results in sorted(all_results.items(),
                                      key=lambda x: x[1]['total_return_pct'] - x[1]['buy_hold_return_pct'],
                                      reverse=True):
            alpha = results['total_return_pct'] - results['buy_hold_return_pct']
            asset_type = "COMMODITY" if asset in ['GOLD', 'SILVER'] else "CRYPTO"

            print(f"{asset:<12} {asset_type:<8} {results['total_return_pct']:>+10.2f} {results['buy_hold_return_pct']:>+10.2f} "
                  f"{alpha:>+10.2f} {results['total_trades']:>8} {results['win_rate']:>8.1f}")

            comparison_data.append({
                'Asset': asset,
                'Type': asset_type,
                'Strategy_Return_Pct': round(results['total_return_pct'], 2),
                'BuyHold_Return_Pct': round(results['buy_hold_return_pct'], 2),
                'Alpha_Pct': round(alpha, 2),
                'Total_Trades': results['total_trades'],
                'Long_Trades': results['long_trades'],
                'Short_Trades': results['short_trades'],
                'Win_Rate_Pct': round(results['win_rate'], 1),
                'Max_Drawdown_Pct': round(results['max_drawdown'], 2),
            })

        # Separate crypto vs commodity stats
        print("\n" + "="*80)
        print("BREAKDOWN BY ASSET TYPE")
        print("="*80)

        crypto_results = {k: v for k, v in all_results.items() if k not in ['GOLD', 'SILVER']}
        commodity_results = {k: v for k, v in all_results.items() if k in ['GOLD', 'SILVER']}

        if crypto_results:
            crypto_alphas = [r['total_return_pct'] - r['buy_hold_return_pct'] for r in crypto_results.values()]
            print(f"\nCRYPTO ({len(crypto_results)} assets):")
            print(f"  Positive alpha: {sum(1 for a in crypto_alphas if a > 0)}/{len(crypto_alphas)}")
            print(f"  Average alpha: {sum(crypto_alphas)/len(crypto_alphas):+.2f}%")

        if commodity_results:
            commodity_alphas = [r['total_return_pct'] - r['buy_hold_return_pct'] for r in commodity_results.values()]
            print(f"\nCOMMODITIES ({len(commodity_results)} assets):")
            print(f"  Positive alpha: {sum(1 for a in commodity_alphas if a > 0)}/{len(commodity_alphas)}")
            print(f"  Average alpha: {sum(commodity_alphas)/len(commodity_alphas):+.2f}%")

        # Save
        os.makedirs('results', exist_ok=True)
        df = pd.DataFrame(comparison_data)
        df = df.sort_values('Alpha_Pct', ascending=False)
        df.to_csv('results/bh_insights_full_backtest.csv', index=False)
        print(f"\nResults saved to results/bh_insights_full_backtest.csv")

    return all_results


if __name__ == "__main__":
    main()
