"""
Backtest Open Interest Strategies

This script tests the OI-based strategies we developed to see if they
actually generate profitable trades in practice.

Learning moment: Backtesting vs Forward Testing
-----------------------------------------------
Backtesting tells us how a strategy WOULD HAVE performed on historical data.
It does NOT guarantee future performance because:
1. We might be overfitting to the specific time period
2. Market conditions change (regime shifts)
3. We're testing on the SAME data we used to discover the pattern

Ideally you'd want:
- In-sample data: For discovering patterns (what we did)
- Out-of-sample data: For testing (data the strategy hasn't "seen")
- Forward testing: Real trades with real money (ultimate test)

With only 30 days of data, we're limited, but we can still learn
from the exercise.
"""

import sys
sys.path.append('src')

import pandas as pd
import numpy as np
from src.strategies.open_interest_strategy import OpenInterestStrategy, OpenInterestRegimeStrategy
from src.backtester import Backtester
from src.utils.visualizer import PerformanceVisualizer


def load_oi_data():
    """Load our processed OI data with features"""
    df = pd.read_csv('data/btc_oi_with_features.csv', parse_dates=['timestamp'])
    df = df.set_index('timestamp')
    df = df.sort_index()

    # Rename for compatibility with backtester
    # The backtester expects OHLCV columns
    # We already have 'close' from price data

    print(f"Loaded {len(df)} records from {df.index.min()} to {df.index.max()}")

    return df


def run_contrarian_backtest(df, params=None):
    """
    Backtest the contrarian OI strategy

    Default parameters based on our analysis findings.
    """

    if params is None:
        params = {
            'oi_lookback': 4,
            'oi_drop_threshold': -0.3,
            'oi_rise_threshold': 0.3,
            'hold_hours': 4,
            'require_price_drop': True,
            'price_drop_threshold': -0.5
        }

    print("\n" + "=" * 60)
    print("BACKTESTING: Open Interest Contrarian Strategy")
    print("=" * 60)
    print(f"\nParameters:")
    for k, v in params.items():
        print(f"   {k}: {v}")

    # Create strategy
    strategy = OpenInterestStrategy(**params)

    # Preview signals
    signals_df = strategy.generate_signals(df)
    buy_count = (signals_df['signal'] == 'BUY').sum()
    sell_count = (signals_df['signal'] == 'SELL').sum()
    print(f"\nSignals generated: {buy_count} buys, {sell_count} sells")

    if buy_count == 0:
        print("No buy signals generated! Try loosening parameters.")
        return None

    # Run backtest - use correct interface
    backtester = Backtester(initial_capital=10000, fee_percent=0.1)
    results = backtester.run(df, strategy)

    # Create results dict that matches what visualizer expects
    results_dict = {
        'data': backtester.portfolio_values,
        'metrics': results,
        'trades': results['trades']
    }

    return results_dict


def run_regime_backtest(df, entry_regime='liquidation'):
    """
    Backtest the regime-based OI strategy
    """

    print("\n" + "=" * 60)
    print(f"BACKTESTING: Open Interest Regime Strategy ({entry_regime})")
    print("=" * 60)

    # Create strategy
    strategy = OpenInterestRegimeStrategy(
        lookback=4,
        entry_regime=entry_regime,
        exit_on_regime_change=True,
        hold_hours=4
    )

    # Preview signals
    signals_df = strategy.generate_signals(df)
    buy_count = (signals_df['signal'] == 'BUY').sum()
    sell_count = (signals_df['signal'] == 'SELL').sum()
    print(f"\nSignals generated: {buy_count} buys, {sell_count} sells")

    if buy_count == 0:
        print("No buy signals generated!")
        return None

    # Run backtest
    backtester = Backtester(initial_capital=10000, fee_percent=0.1)
    results = backtester.run(df, strategy)

    # Create results dict
    results_dict = {
        'data': backtester.portfolio_values,
        'metrics': results,
        'trades': results['trades']
    }

    return results_dict


def parameter_sweep():
    """
    Test different parameter combinations to find optimal settings

    Learning moment: Parameter Optimization
    ---------------------------------------
    Testing many parameters on the same data = overfitting risk.
    The "best" parameters might just be lucky on this specific period.

    To mitigate:
    1. Don't pick the absolute best - pick something robust
    2. Look for parameter stability (good across a range, not just one point)
    3. Use out-of-sample testing when possible
    """

    print("\n" + "=" * 60)
    print("PARAMETER SWEEP")
    print("=" * 60)

    df = load_oi_data()

    results_list = []

    # Test different lookback periods and thresholds
    for lookback in [2, 4, 6, 8]:
        for drop_thresh in [-0.2, -0.3, -0.4, -0.5]:
            for require_price_drop in [True, False]:

                params = {
                    'oi_lookback': lookback,
                    'oi_drop_threshold': drop_thresh,
                    'oi_rise_threshold': abs(drop_thresh),
                    'hold_hours': lookback,
                    'require_price_drop': require_price_drop,
                    'price_drop_threshold': -0.5
                }

                strategy = OpenInterestStrategy(**params)
                signals_df = strategy.generate_signals(df)

                buy_count = (signals_df['signal'] == 'BUY').sum()

                if buy_count < 3:  # Skip if too few trades
                    continue

                # Use quiet backtest (capture output)
                import io
                import sys
                old_stdout = sys.stdout
                sys.stdout = io.StringIO()

                try:
                    backtester = Backtester(initial_capital=10000, fee_percent=0.1)
                    results = backtester.run(df, strategy)
                finally:
                    sys.stdout = old_stdout

                results_list.append({
                    'lookback': lookback,
                    'drop_threshold': drop_thresh,
                    'require_price_drop': require_price_drop,
                    'trades': results['total_trades'],
                    'return_pct': results['total_return_pct'],
                    'win_rate': results['win_rate'],
                    'max_drawdown': results['max_drawdown']
                })

    results_df = pd.DataFrame(results_list)

    if len(results_df) > 0:
        print("\nTop 10 parameter combinations by return:")
        print(results_df.sort_values('return_pct', ascending=False).head(10).to_string())

        print("\nTop 10 parameter combinations by win rate:")
        print(results_df.sort_values('win_rate', ascending=False).head(10).to_string())

        # Save results
        results_df.to_csv('results/oi_parameter_sweep.csv', index=False)
        print("\nSaved parameter sweep results to results/oi_parameter_sweep.csv")

    return results_df


def compare_strategies():
    """Compare all OI strategies against buy & hold"""

    print("\n" + "=" * 60)
    print("STRATEGY COMPARISON")
    print("=" * 60)

    df = load_oi_data()

    # Calculate buy & hold return
    bh_return = (df['close'].iloc[-1] / df['close'].iloc[0] - 1) * 100

    results_summary = []

    # 1. Contrarian strategy
    contrarian_results = run_contrarian_backtest(df)
    if contrarian_results:
        metrics = contrarian_results['metrics']
        results_summary.append({
            'strategy': 'OI Contrarian',
            'return_pct': metrics['total_return_pct'],
            'trades': metrics['total_trades'],
            'win_rate': metrics['win_rate'],
            'max_drawdown': metrics['max_drawdown']
        })

    # 2. Regime strategy - liquidation only
    liquidation_results = run_regime_backtest(df, 'liquidation')
    if liquidation_results:
        metrics = liquidation_results['metrics']
        results_summary.append({
            'strategy': 'OI Regime (liquidation)',
            'return_pct': metrics['total_return_pct'],
            'trades': metrics['total_trades'],
            'win_rate': metrics['win_rate'],
            'max_drawdown': metrics['max_drawdown']
        })

    # 3. Regime strategy - squeeze only
    squeeze_results = run_regime_backtest(df, 'squeeze')
    if squeeze_results:
        metrics = squeeze_results['metrics']
        results_summary.append({
            'strategy': 'OI Regime (squeeze)',
            'return_pct': metrics['total_return_pct'],
            'trades': metrics['total_trades'],
            'win_rate': metrics['win_rate'],
            'max_drawdown': metrics['max_drawdown']
        })

    # 4. Regime strategy - both
    both_results = run_regime_backtest(df, 'both')
    if both_results:
        metrics = both_results['metrics']
        results_summary.append({
            'strategy': 'OI Regime (both)',
            'return_pct': metrics['total_return_pct'],
            'trades': metrics['total_trades'],
            'win_rate': metrics['win_rate'],
            'max_drawdown': metrics['max_drawdown']
        })

    # Add buy & hold
    results_summary.append({
        'strategy': 'Buy & Hold',
        'return_pct': bh_return,
        'trades': 1,
        'win_rate': 100 if bh_return > 0 else 0,
        'max_drawdown': 'N/A'
    })

    # Print comparison
    print("\n" + "=" * 60)
    print("FINAL COMPARISON")
    print("=" * 60)

    summary_df = pd.DataFrame(results_summary)
    print(summary_df.to_string(index=False))

    # Save comparison
    summary_df.to_csv('results/oi_strategy_comparison.csv', index=False)
    print("\nSaved comparison to results/oi_strategy_comparison.csv")

    return summary_df


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Backtest OI strategies')
    parser.add_argument('--sweep', action='store_true', help='Run parameter sweep')
    parser.add_argument('--compare', action='store_true', help='Compare all strategies')
    args = parser.parse_args()

    if args.sweep:
        parameter_sweep()
    elif args.compare:
        compare_strategies()
    else:
        # Default: run main comparison
        compare_strategies()
