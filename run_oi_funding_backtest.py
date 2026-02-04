"""
Backtest OI + Funding Combined Strategies

This script compares:
1. OI-only strategies (baseline)
2. OI + Funding combined strategies (enhanced)
3. Buy & Hold

The goal is to see if adding funding rates improves the strategy.
"""

import sys
sys.path.append('src')

import pandas as pd
import numpy as np
from src.strategies.oi_funding_strategy import OIFundingCombinedStrategy, SentimentScoreStrategy
from src.strategies.open_interest_strategy import OpenInterestStrategy, OpenInterestRegimeStrategy
from src.backtester import Backtester
import io


def load_combined_data():
    """Load the combined OI + Funding data"""
    df = pd.read_csv('data/btc_oi_funding_combined.csv', parse_dates=['timestamp'])
    df = df.set_index('timestamp')
    df = df.sort_index()

    print(f"Loaded {len(df)} records from {df.index.min()} to {df.index.max()}")

    return df


def run_strategy_backtest(df, strategy, verbose=True):
    """Run a single strategy backtest"""

    # Preview signals
    signals_df = strategy.generate_signals(df)
    buy_count = (signals_df['signal'] == 'BUY').sum()
    sell_count = (signals_df['signal'] == 'SELL').sum()

    if verbose:
        print(f"\nSignals: {buy_count} buys, {sell_count} sells")

    if buy_count == 0:
        return None

    # Suppress output for cleaner comparison
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()

    try:
        backtester = Backtester(initial_capital=10000, fee_percent=0.1)
        results = backtester.run(df, strategy)
    finally:
        sys.stdout = old_stdout

    return results


def compare_all_strategies():
    """Compare OI-only vs OI+Funding strategies"""

    print("=" * 70)
    print("COMPARING OI-ONLY vs OI+FUNDING STRATEGIES")
    print("=" * 70)

    df = load_combined_data()

    # Calculate buy & hold return
    bh_return = (df['close'].iloc[-1] / df['close'].iloc[0] - 1) * 100

    results_list = []

    # =========================================
    # 1. OI-ONLY STRATEGIES (baseline)
    # =========================================
    print("\n--- OI-Only Strategies (Baseline) ---")

    # OI Contrarian
    oi_contrarian = OpenInterestStrategy(
        oi_lookback=4,
        oi_drop_threshold=-0.3,
        require_price_drop=True
    )
    result = run_strategy_backtest(df, oi_contrarian)
    if result:
        results_list.append({
            'strategy': 'OI Contrarian',
            'category': 'OI Only',
            'return_pct': result['total_return_pct'],
            'trades': result['total_trades'],
            'win_rate': result['win_rate'],
            'max_drawdown': result['max_drawdown']
        })

    # OI Regime (both)
    oi_regime = OpenInterestRegimeStrategy(
        lookback=4,
        entry_regime='both',
        exit_on_regime_change=True
    )
    result = run_strategy_backtest(df, oi_regime)
    if result:
        results_list.append({
            'strategy': 'OI Regime (both)',
            'category': 'OI Only',
            'return_pct': result['total_return_pct'],
            'trades': result['total_trades'],
            'win_rate': result['win_rate'],
            'max_drawdown': result['max_drawdown']
        })

    # =========================================
    # 2. OI + FUNDING STRATEGIES (enhanced)
    # =========================================
    print("\n--- OI + Funding Strategies (Enhanced) ---")

    # Combined - Any funding
    combined_any = OIFundingCombinedStrategy(
        oi_lookback=4,
        oi_drop_threshold=-0.2,
        funding_filter='any',
        max_hold_hours=24
    )
    result = run_strategy_backtest(df, combined_any)
    if result:
        results_list.append({
            'strategy': 'OI+Funding (any)',
            'category': 'Combined',
            'return_pct': result['total_return_pct'],
            'trades': result['total_trades'],
            'win_rate': result['win_rate'],
            'max_drawdown': result['max_drawdown']
        })

    # Combined - High funding only (short capitulation)
    combined_high = OIFundingCombinedStrategy(
        oi_lookback=4,
        oi_drop_threshold=-0.2,
        funding_filter='high',
        funding_percentile_high=70,
        max_hold_hours=24
    )
    result = run_strategy_backtest(df, combined_high)
    if result:
        results_list.append({
            'strategy': 'OI+Funding (high)',
            'category': 'Combined',
            'return_pct': result['total_return_pct'],
            'trades': result['total_trades'],
            'win_rate': result['win_rate'],
            'max_drawdown': result['max_drawdown']
        })

    # Combined - Low funding only (long capitulation)
    combined_low = OIFundingCombinedStrategy(
        oi_lookback=4,
        oi_drop_threshold=-0.2,
        funding_filter='low',
        funding_percentile_low=30,
        max_hold_hours=24
    )
    result = run_strategy_backtest(df, combined_low)
    if result:
        results_list.append({
            'strategy': 'OI+Funding (low)',
            'category': 'Combined',
            'return_pct': result['total_return_pct'],
            'trades': result['total_trades'],
            'win_rate': result['win_rate'],
            'max_drawdown': result['max_drawdown']
        })

    # Combined - Require price drop
    combined_price = OIFundingCombinedStrategy(
        oi_lookback=4,
        oi_drop_threshold=-0.2,
        funding_filter='any',
        require_price_drop=True,
        price_drop_threshold=-0.3,
        max_hold_hours=24
    )
    result = run_strategy_backtest(df, combined_price)
    if result:
        results_list.append({
            'strategy': 'OI+Funding+PriceDrop',
            'category': 'Combined',
            'return_pct': result['total_return_pct'],
            'trades': result['total_trades'],
            'win_rate': result['win_rate'],
            'max_drawdown': result['max_drawdown']
        })

    # Sentiment Score strategy
    sentiment = SentimentScoreStrategy(
        sentiment_threshold_buy=0.7,
        sentiment_threshold_sell=0.4,
        hold_hours=8
    )
    result = run_strategy_backtest(df, sentiment)
    if result:
        results_list.append({
            'strategy': 'Sentiment Score',
            'category': 'Combined',
            'return_pct': result['total_return_pct'],
            'trades': result['total_trades'],
            'win_rate': result['win_rate'],
            'max_drawdown': result['max_drawdown']
        })

    # =========================================
    # 3. BUY & HOLD (benchmark)
    # =========================================
    results_list.append({
        'strategy': 'Buy & Hold',
        'category': 'Benchmark',
        'return_pct': bh_return,
        'trades': 1,
        'win_rate': 100 if bh_return > 0 else 0,
        'max_drawdown': 'N/A'
    })

    # =========================================
    # RESULTS
    # =========================================
    results_df = pd.DataFrame(results_list)

    print("\n" + "=" * 70)
    print("FINAL RESULTS COMPARISON")
    print("=" * 70)

    # Sort by return
    results_df = results_df.sort_values('return_pct', ascending=False)
    print(results_df.to_string(index=False))

    # Summary statistics
    print("\n" + "=" * 70)
    print("SUMMARY BY CATEGORY")
    print("=" * 70)

    oi_only = results_df[results_df['category'] == 'OI Only']['return_pct'].mean()
    combined = results_df[results_df['category'] == 'Combined']['return_pct'].mean()

    print(f"\nAverage Return:")
    print(f"   OI-Only strategies:     {oi_only:+.2f}%")
    print(f"   Combined strategies:    {combined:+.2f}%")
    print(f"   Buy & Hold:             {bh_return:+.2f}%")

    if combined > oi_only:
        improvement = combined - oi_only
        print(f"\n   Adding funding IMPROVED returns by {improvement:+.2f}%")
    else:
        diff = oi_only - combined
        print(f"\n   Adding funding DECREASED returns by {diff:.2f}%")

    # Best strategy
    best = results_df.iloc[0]
    print(f"\n   BEST STRATEGY: {best['strategy']}")
    print(f"   Return: {best['return_pct']:+.2f}%")
    print(f"   Win Rate: {best['win_rate']:.1f}%")
    print(f"   Trades: {best['trades']}")

    # Save results
    results_df.to_csv('results/oi_funding_comparison.csv', index=False)
    print("\nSaved results to results/oi_funding_comparison.csv")

    return results_df


def parameter_optimization():
    """
    Find optimal parameters for the combined strategy

    Learning moment: Avoid Overfitting
    -----------------------------------
    Testing many parameters on limited data = overfitting risk.
    We're looking for:
    1. Robust parameters (work across a range)
    2. Logical parameters (make sense theoretically)
    3. Sufficient trades (statistical significance)
    """

    print("\n" + "=" * 70)
    print("PARAMETER OPTIMIZATION FOR COMBINED STRATEGY")
    print("=" * 70)

    df = load_combined_data()
    results_list = []

    # Test parameter combinations
    for oi_lookback in [2, 4, 6, 8]:
        for oi_threshold in [-0.15, -0.2, -0.25, -0.3]:
            for funding_filter in ['any', 'high', 'low']:
                for max_hold in [12, 24, 48]:

                    strategy = OIFundingCombinedStrategy(
                        oi_lookback=oi_lookback,
                        oi_drop_threshold=oi_threshold,
                        funding_filter=funding_filter,
                        max_hold_hours=max_hold
                    )

                    # Quick signal check
                    signals = strategy.generate_signals(df)
                    buy_count = (signals['signal'] == 'BUY').sum()

                    if buy_count < 5:  # Skip if too few trades
                        continue

                    result = run_strategy_backtest(df, strategy, verbose=False)

                    if result and result['total_trades'] >= 5:
                        results_list.append({
                            'oi_lookback': oi_lookback,
                            'oi_threshold': oi_threshold,
                            'funding_filter': funding_filter,
                            'max_hold': max_hold,
                            'trades': result['total_trades'],
                            'return_pct': result['total_return_pct'],
                            'win_rate': result['win_rate'],
                            'max_drawdown': result['max_drawdown']
                        })

    results_df = pd.DataFrame(results_list)

    if len(results_df) > 0:
        print("\nTop 10 by Return:")
        print(results_df.sort_values('return_pct', ascending=False).head(10).to_string())

        print("\nTop 10 by Win Rate (min 10 trades):")
        filtered = results_df[results_df['trades'] >= 10]
        print(filtered.sort_values('win_rate', ascending=False).head(10).to_string())

        # Save
        results_df.to_csv('results/oi_funding_param_optimization.csv', index=False)
        print("\nSaved to results/oi_funding_param_optimization.csv")

    return results_df


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Backtest OI+Funding strategies')
    parser.add_argument('--optimize', action='store_true', help='Run parameter optimization')
    args = parser.parse_args()

    if args.optimize:
        parameter_optimization()
    else:
        compare_all_strategies()
