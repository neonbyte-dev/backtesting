"""
Test "Never Sell At Loss" Strategies
"""

import sys
sys.path.append('src')

import pandas as pd
import numpy as np
from src.strategies.never_sell_loss_strategy import (
    NeverSellLossStrategy,
    NeverSellLossWithTrailing,
    BreakevenOrBetter
)
from src.strategies.aggressive_oi_strategy import AggressiveOIStrategy
from src.backtester import Backtester
import io


def load_data():
    df = pd.read_csv('data/btc_oi_funding_combined.csv', parse_dates=['timestamp'])
    df = df.set_index('timestamp')
    return df


def run_backtest(df, strategy, verbose=True):
    """Run backtest with optional output"""
    signals = strategy.generate_signals(df)
    buys = (signals['signal'] == 'BUY').sum()
    sells = (signals['signal'] == 'SELL').sum()

    if verbose:
        print(f"\n{strategy.name}:")
        print(f"  Signals: {buys} buys, {sells} sells")

    if buys == 0:
        if verbose:
            print("  No trades!")
        return None

    if not verbose:
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()

    try:
        backtester = Backtester(initial_capital=10000, fee_percent=0.1)
        results = backtester.run(df, strategy)
    finally:
        if not verbose:
            sys.stdout = old_stdout

    return results


def compare_strategies():
    print("=" * 80)
    print("NEVER SELL AT LOSS vs TRADITIONAL STOP LOSS")
    print("=" * 80)

    df = load_data()
    print(f"Data: {len(df)} records from {df.index.min().date()} to {df.index.max().date()}")

    bh_return = (df['close'].iloc[-1] / df['close'].iloc[0] - 1) * 100
    print(f"Buy & Hold: {bh_return:.2f}%\n")

    results = []

    # ============================================
    # BASELINE: With Stop Loss
    # ============================================
    print("-" * 40)
    print("WITH STOP LOSS (baseline)")
    print("-" * 40)

    baseline = AggressiveOIStrategy(
        oi_drop_threshold=-0.2,
        price_drop_threshold=-0.3,
        profit_target=1.5,
        stop_loss=-0.8,
        max_hold_hours=48
    )
    result = run_backtest(df, baseline)
    if result:
        results.append({
            'Strategy': 'With Stop Loss (baseline)',
            'Return %': result['total_return_pct'],
            'Trades': result['total_trades'],
            'Win Rate %': result['win_rate'],
            'Max DD %': result['max_drawdown']
        })

    # ============================================
    # NEVER SELL AT LOSS VARIANTS
    # ============================================
    print("\n" + "-" * 40)
    print("NEVER SELL AT LOSS")
    print("-" * 40)

    # Different profit targets
    for target in [1.0, 1.5, 2.0, 2.5, 3.0]:
        strategy = NeverSellLossStrategy(
            oi_drop_threshold=-0.2,
            price_drop_threshold=-0.3,
            profit_target=target
        )
        result = run_backtest(df, strategy)
        if result:
            results.append({
                'Strategy': f'Never Loss {target}% target',
                'Return %': result['total_return_pct'],
                'Trades': result['total_trades'],
                'Win Rate %': result['win_rate'],
                'Max DD %': result['max_drawdown']
            })

    # With trailing
    print("\n" + "-" * 40)
    print("NEVER LOSS + TRAILING STOP")
    print("-" * 40)

    for trail in [0.3, 0.5, 0.8, 1.0]:
        strategy = NeverSellLossWithTrailing(
            oi_drop_threshold=-0.2,
            price_drop_threshold=-0.3,
            min_profit_to_trail=0.5,
            trailing_stop=trail
        )
        result = run_backtest(df, strategy)
        if result:
            results.append({
                'Strategy': f'Never Loss + Trail {trail}%',
                'Return %': result['total_return_pct'],
                'Trades': result['total_trades'],
                'Win Rate %': result['win_rate'],
                'Max DD %': result['max_drawdown']
            })

    # Breakeven or better
    print("\n" + "-" * 40)
    print("BREAKEVEN OR BETTER")
    print("-" * 40)

    for hours in [24, 48, 72]:
        strategy = BreakevenOrBetter(
            oi_drop_threshold=-0.2,
            price_drop_threshold=-0.3,
            profit_target=1.5,
            breakeven_after_hours=hours
        )
        result = run_backtest(df, strategy)
        if result:
            results.append({
                'Strategy': f'Breakeven after {hours}h',
                'Return %': result['total_return_pct'],
                'Trades': result['total_trades'],
                'Win Rate %': result['win_rate'],
                'Max DD %': result['max_drawdown']
            })

    # Add buy & hold
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
    print("FINAL COMPARISON")
    print("=" * 80)
    print(results_df.to_string(index=False))

    # Find best never-loss strategy
    never_loss = results_df[results_df['Strategy'].str.contains('Never Loss|Breakeven')]
    if len(never_loss) > 0:
        best_nl = never_loss.iloc[0]
        baseline_row = results_df[results_df['Strategy'].str.contains('baseline')]

        if len(baseline_row) > 0:
            baseline_return = baseline_row.iloc[0]['Return %']
            improvement = best_nl['Return %'] - baseline_return

            print(f"\n{'='*80}")
            print("COMPARISON: Never Sell Loss vs Stop Loss")
            print(f"{'='*80}")
            print(f"Best 'Never Sell Loss': {best_nl['Strategy']}")
            print(f"  Return: {best_nl['Return %']:.2f}%")
            print(f"  Win Rate: {best_nl['Win Rate %']:.1f}%")
            print(f"\nBaseline (with stop loss): {baseline_return:.2f}%")
            print(f"\nDifference: {improvement:+.2f}%")

            if improvement > 0:
                print("\n*** NEVER SELL LOSS WINS! ***")
            else:
                print("\n*** STOP LOSS VERSION WINS ***")

    # Save
    results_df.to_csv('results/never_loss_comparison.csv', index=False)
    print("\nSaved to results/never_loss_comparison.csv")

    return results_df


def detailed_trade_analysis():
    """Show detailed trades for the best never-loss strategy"""
    print("\n" + "=" * 80)
    print("DETAILED TRADE ANALYSIS: NEVER SELL AT LOSS")
    print("=" * 80)

    df = load_data()

    # Run best never-loss strategy with full output
    strategy = NeverSellLossStrategy(
        oi_drop_threshold=-0.2,
        price_drop_threshold=-0.3,
        profit_target=1.5
    )

    print(strategy.describe())

    backtester = Backtester(initial_capital=10000, fee_percent=0.1)
    results = backtester.run(df, strategy)

    # Analyze trades
    if results['trades']:
        print("\n--- TRADE QUALITY ANALYSIS ---")

        wins = [t for t in results['trades'] if t['type'] == 'SELL' and t.get('pnl', 0) > 0]
        losses = [t for t in results['trades'] if t['type'] == 'SELL' and t.get('pnl', 0) <= 0]

        print(f"Wins: {len(wins)}")
        print(f"Losses: {len(losses)}")
        print(f"Win Rate: {len(wins)/(len(wins)+len(losses))*100:.1f}%" if (len(wins)+len(losses)) > 0 else "N/A")

        if wins:
            avg_win = np.mean([t.get('pnl_percent', 0) for t in wins])
            print(f"Average Win: +{avg_win:.2f}%")

        if losses:
            avg_loss = np.mean([t.get('pnl_percent', 0) for t in losses])
            print(f"Average Loss: {avg_loss:.2f}%")


if __name__ == "__main__":
    compare_strategies()
    detailed_trade_analysis()
