"""
Final Strategy Comparison

Testing all OI-based strategies to find the best performer.
"""

import sys
sys.path.append('src')

import pandas as pd
import numpy as np
from src.strategies.aggressive_oi_strategy import AggressiveOIStrategy, ScalpingOIStrategy, AdaptiveOIStrategy
from src.strategies.open_interest_strategy import OpenInterestStrategy, OpenInterestRegimeStrategy
from src.backtester import Backtester
import io


def load_data():
    """Load combined data"""
    df = pd.read_csv('data/btc_oi_funding_combined.csv', parse_dates=['timestamp'])
    df = df.set_index('timestamp')
    return df


def run_backtest_quiet(df, strategy):
    """Run backtest without printing"""
    signals = strategy.generate_signals(df)
    buys = (signals['signal'] == 'BUY').sum()

    if buys == 0:
        return None

    old_stdout = sys.stdout
    sys.stdout = io.StringIO()

    try:
        backtester = Backtester(initial_capital=10000, fee_percent=0.1)
        results = backtester.run(df, strategy)
    finally:
        sys.stdout = old_stdout

    return results


def run_all_comparisons():
    """Compare all strategies"""
    print("=" * 80)
    print("COMPREHENSIVE STRATEGY COMPARISON")
    print("=" * 80)

    df = load_data()
    print(f"Data: {len(df)} records from {df.index.min().date()} to {df.index.max().date()}")

    bh_return = (df['close'].iloc[-1] / df['close'].iloc[0] - 1) * 100
    print(f"Buy & Hold return: {bh_return:.2f}%\n")

    results = []

    # ============================================
    # ORIGINAL STRATEGIES
    # ============================================
    print("Testing Original Strategies...")

    strategies = [
        ("OI Contrarian (original)", OpenInterestStrategy(
            oi_lookback=4, oi_drop_threshold=-0.3, require_price_drop=True
        )),
        ("OI Regime Both (original)", OpenInterestRegimeStrategy(
            lookback=4, entry_regime='both', exit_on_regime_change=True
        )),
    ]

    for name, strategy in strategies:
        result = run_backtest_quiet(df, strategy)
        if result:
            results.append({
                'Strategy': name,
                'Return %': result['total_return_pct'],
                'Trades': result['total_trades'],
                'Win Rate %': result['win_rate'],
                'Max DD %': result['max_drawdown']
            })

    # ============================================
    # AGGRESSIVE STRATEGIES
    # ============================================
    print("Testing Aggressive Strategies...")

    aggressive_strategies = [
        # Standard aggressive
        ("Aggressive 2% target", AggressiveOIStrategy(
            oi_drop_threshold=-0.25, price_drop_threshold=-0.5,
            profit_target=2.0, stop_loss=-1.0, max_hold_hours=48
        )),
        ("Aggressive 1.5% target", AggressiveOIStrategy(
            oi_drop_threshold=-0.25, price_drop_threshold=-0.5,
            profit_target=1.5, stop_loss=-0.8, max_hold_hours=36
        )),
        ("Aggressive 3% target", AggressiveOIStrategy(
            oi_drop_threshold=-0.3, price_drop_threshold=-0.5,
            profit_target=3.0, stop_loss=-1.5, max_hold_hours=72
        )),

        # Scalping
        ("Scalping 0.8%", ScalpingOIStrategy(
            oi_drop_threshold=-0.15, price_drop_threshold=-0.3,
            profit_target=0.8, stop_loss=-0.5, max_hold_hours=12
        )),
        ("Scalping 1.0%", ScalpingOIStrategy(
            oi_drop_threshold=-0.15, price_drop_threshold=-0.3,
            profit_target=1.0, stop_loss=-0.6, max_hold_hours=16
        )),

        # Adaptive
        ("Adaptive Vol", AdaptiveOIStrategy(
            oi_drop_threshold=-0.2, price_drop_threshold=-0.4,
            base_profit_target=1.5, base_stop_loss=-0.8
        )),
    ]

    for name, strategy in aggressive_strategies:
        result = run_backtest_quiet(df, strategy)
        if result:
            results.append({
                'Strategy': name,
                'Return %': result['total_return_pct'],
                'Trades': result['total_trades'],
                'Win Rate %': result['win_rate'],
                'Max DD %': result['max_drawdown']
            })

    # ============================================
    # PARAMETER SWEEP FOR BEST CONFIG
    # ============================================
    print("Running parameter sweep...")

    best_return = -999
    best_config = None

    for oi_thresh in [-0.15, -0.2, -0.25, -0.3]:
        for price_thresh in [-0.2, -0.3, -0.5, -0.7]:
            for profit_target in [1.0, 1.5, 2.0, 2.5, 3.0]:
                for stop_loss in [-0.5, -0.8, -1.0, -1.5]:
                    for max_hold in [24, 36, 48]:

                        strategy = AggressiveOIStrategy(
                            oi_drop_threshold=oi_thresh,
                            price_drop_threshold=price_thresh,
                            profit_target=profit_target,
                            stop_loss=stop_loss,
                            max_hold_hours=max_hold
                        )

                        result = run_backtest_quiet(df, strategy)

                        if result and result['total_trades'] >= 5:
                            if result['total_return_pct'] > best_return:
                                best_return = result['total_return_pct']
                                best_config = {
                                    'oi_thresh': oi_thresh,
                                    'price_thresh': price_thresh,
                                    'profit_target': profit_target,
                                    'stop_loss': stop_loss,
                                    'max_hold': max_hold,
                                    'trades': result['total_trades'],
                                    'win_rate': result['win_rate'],
                                    'max_dd': result['max_drawdown']
                                }

    if best_config:
        results.append({
            'Strategy': f"OPTIMIZED (OI:{best_config['oi_thresh']}, PT:{best_config['profit_target']})",
            'Return %': best_return,
            'Trades': best_config['trades'],
            'Win Rate %': best_config['win_rate'],
            'Max DD %': best_config['max_dd']
        })

        print(f"\nBest parameters found:")
        print(f"  OI threshold: {best_config['oi_thresh']}%")
        print(f"  Price threshold: {best_config['price_thresh']}%")
        print(f"  Profit target: {best_config['profit_target']}%")
        print(f"  Stop loss: {best_config['stop_loss']}%")
        print(f"  Max hold: {best_config['max_hold']}h")

    # ============================================
    # ADD BUY & HOLD
    # ============================================
    results.append({
        'Strategy': 'Buy & Hold',
        'Return %': bh_return,
        'Trades': 1,
        'Win Rate %': 100 if bh_return > 0 else 0,
        'Max DD %': 'N/A'
    })

    # ============================================
    # RESULTS
    # ============================================
    results_df = pd.DataFrame(results)
    results_df = results_df.sort_values('Return %', ascending=False)

    print("\n" + "=" * 80)
    print("FINAL RESULTS (sorted by return)")
    print("=" * 80)
    print(results_df.to_string(index=False))

    # Save
    results_df.to_csv('results/final_strategy_comparison.csv', index=False)
    print("\nSaved to results/final_strategy_comparison.csv")

    # ============================================
    # DETAILED LOOK AT TOP STRATEGY
    # ============================================
    if best_config:
        print("\n" + "=" * 80)
        print("DETAILED ANALYSIS OF BEST STRATEGY")
        print("=" * 80)

        best_strategy = AggressiveOIStrategy(
            oi_drop_threshold=best_config['oi_thresh'],
            price_drop_threshold=best_config['price_thresh'],
            profit_target=best_config['profit_target'],
            stop_loss=best_config['stop_loss'],
            max_hold_hours=best_config['max_hold']
        )

        # Run with output
        backtester = Backtester(initial_capital=10000, fee_percent=0.1)
        results = backtester.run(df, best_strategy)

    return results_df


if __name__ == "__main__":
    run_all_comparisons()
