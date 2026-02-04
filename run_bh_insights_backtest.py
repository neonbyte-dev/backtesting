#!/usr/bin/env python3
"""
BH Insights Strategy Backtest Runner

This script:
1. Fetches historical price data for the signal period
2. Runs the BH Insights strategy against it
3. Reports backtesting results

LEARNING MOMENT: Signal-Based vs Indicator-Based Backtesting
=============================================================
Traditional backtesting runs indicators on every candle.
Signal-based backtesting maps external signals to candles.

The key challenge: Brandon's signals have timestamps, but we only
have candle close prices. We assume entry/exit at the candle close
that contains the signal timestamp.
"""

import sys
sys.path.insert(0, 'src')

from utils.data_fetcher import DataFetcher
from strategies.bh_insights_strategy import BHInsightsStrategy, BHInsightsMultiCoinStrategy
from backtester_with_shorts import BacktesterWithShorts
import pandas as pd


def run_backtest(coin='BTC', initial_capital=10000, hold_hours=48):
    """Run backtest for a single coin"""
    print(f"\n{'='*70}")
    print(f"BH INSIGHTS STRATEGY BACKTEST - {coin}")
    print(f"{'='*70}\n")

    # Initialize strategy
    strategy = BHInsightsStrategy(
        coin=coin,
        messages_path='data/bh_insights_messages.csv',
        signal_confidence='high',
        hold_hours=hold_hours,
        include_shorts=True
    )

    # Show signal summary
    print(strategy.get_signal_summary())

    if strategy.parsed_signals.empty:
        print(f"No signals found for {coin}, skipping...")
        return None

    # Get signal date range
    signal_start = strategy.parsed_signals['timestamp'].min()
    signal_end = strategy.parsed_signals['timestamp'].max()
    days_needed = (signal_end - signal_start).days + 30  # Add buffer

    print(f"\nSignal period: {signal_start.date()} to {signal_end.date()}")
    print(f"Fetching {days_needed} days of price data...\n")

    # Fetch price data
    fetcher = DataFetcher()
    symbol = f"{coin}/USDT"

    try:
        data = fetcher.fetch_ohlcv(symbol, '1h', days_back=days_needed)
    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")
        return None

    # Filter data to signal period (with buffer)
    data = data[data.index >= (signal_start - pd.Timedelta(days=1))]

    if len(data) == 0:
        print(f"No price data in signal period for {coin}")
        return None

    print(f"Price data: {data.index[0]} to {data.index[-1]}")
    print(f"Total candles: {len(data)}\n")

    # Run backtest
    backtester = BacktesterWithShorts(
        initial_capital=initial_capital,
        fee_percent=0.1,
        display_timezone='America/New_York'
    )

    results = backtester.run(data, strategy, silent=False)

    return results


def run_multi_coin_comparison():
    """Compare results across multiple coins"""
    coins = ['BTC', 'ETH', 'SOL']
    all_results = {}

    for coin in coins:
        results = run_backtest(coin, initial_capital=10000, hold_hours=48)
        if results:
            all_results[coin] = results

    # Summary comparison
    print(f"\n{'='*70}")
    print("MULTI-COIN COMPARISON")
    print(f"{'='*70}\n")

    print(f"{'Coin':<8} {'Return %':>12} {'Buy&Hold %':>12} {'Trades':>10} {'Win Rate':>10}")
    print("-" * 60)

    for coin, results in all_results.items():
        print(f"{coin:<8} {results['total_return_pct']:>12.2f} {results['buy_hold_return_pct']:>12.2f} "
              f"{results['total_trades']:>10} {results['win_rate']:>10.1f}%")

    # Save results
    summary_data = []
    for coin, results in all_results.items():
        summary_data.append({
            'Coin': coin,
            'Initial Capital': results['initial_capital'],
            'Final Value': results['final_value'],
            'Total Return %': results['total_return_pct'],
            'Buy & Hold %': results['buy_hold_return_pct'],
            'Total Trades': results['total_trades'],
            'Long Trades': results['long_trades'],
            'Short Trades': results['short_trades'],
            'Win Rate %': results['win_rate'],
            'Max Drawdown %': results['max_drawdown'],
            'Avg Win': results['avg_win'],
            'Avg Loss': results['avg_loss']
        })

    if summary_data:
        df = pd.DataFrame(summary_data)
        df.to_csv('results/bh_insights_backtest.csv', index=False)
        print(f"\nResults saved to results/bh_insights_backtest.csv")

    return all_results


if __name__ == "__main__":
    import os
    os.makedirs('results', exist_ok=True)

    # Run BTC only for quick test
    print("Running BTC backtest first...\n")
    results = run_backtest('BTC', initial_capital=10000, hold_hours=48)

    if results:
        # Show trade details
        print("\n" + "="*70)
        print("TRADE DETAILS")
        print("="*70 + "\n")

        for trade in results['trades'][:20]:  # First 20 trades
            trade_type = trade['type']
            timestamp = trade['timestamp']
            price = trade['price']

            if 'pnl' in trade:
                pnl = trade['pnl']
                pnl_pct = trade['pnl_percent']
                print(f"{trade_type:<12} | {timestamp} | ${price:,.2f} | P&L: ${pnl:,.2f} ({pnl_pct:+.2f}%)")
            else:
                print(f"{trade_type:<12} | {timestamp} | ${price:,.2f}")

    # Uncomment to run multi-coin comparison
    # run_multi_coin_comparison()
