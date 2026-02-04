"""
CME Sunday Open Strategy Backtest Runner

Tests Brandon Hong's CME Sunday Open strategy across multiple assets:
- BTC/USDT (Bitcoin)
- ETH/USDT (Ethereum)
- SOL/USDT (Solana)
- PAXG/USDT (Tokenized Gold - proxy for gold)
- XRP/USDT (XRP)

LEARNING MOMENT: Why These Assets?
===================================
Brandon Hong trades both crypto (BTC shorts) and precious metals (gold/silver longs).

Binance doesn't have spot gold/silver, so we use PAXG (Pax Gold) as a proxy.
PAXG is a token backed 1:1 by physical gold, so it tracks gold prices closely.

For a complete test, you'd want actual gold/silver futures data from CME,
but for this proof of concept, PAXG gives us directional insight.
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from utils.data_fetcher import DataFetcher
from backtester_with_shorts import BacktesterWithShorts
from strategies.cme_sunday_open_strategy import (
    CMESundayOpenStrategy,
    CMESundayOpenLongOnly,
    CMESundayOpenShortOnly
)


def run_single_backtest(symbol, data, strategy, initial_capital=10000):
    """Run a single backtest and return results"""
    backtester = BacktesterWithShorts(
        initial_capital=initial_capital,
        fee_percent=0.1,
        display_timezone='America/New_York'
    )
    results = backtester.run(data, strategy, silent=True)
    return results


def run_multi_asset_backtest(days_back=365, initial_capital=10000):
    """
    Run CME Sunday Open strategy across multiple assets

    Returns DataFrame with results for each asset and strategy combination
    """
    fetcher = DataFetcher()

    # Assets to test
    assets = [
        ('BTC/USDT', 'Bitcoin'),
        ('ETH/USDT', 'Ethereum'),
        ('SOL/USDT', 'Solana'),
        ('XRP/USDT', 'XRP'),
        # ('PAXG/USDT', 'Gold (PAXG)'),  # May have limited liquidity
    ]

    # Strategy configurations to test
    strategy_configs = [
        # Long + Short (full strategy)
        {
            'name': 'CME Both (24h hold)',
            'params': {
                'direction_mode': 'first_candle',
                'trade_direction': 'both',
                'exit_mode': 'fixed_hours',
                'hold_hours': 24
            }
        },
        {
            'name': 'CME Both (48h hold)',
            'params': {
                'direction_mode': 'first_candle',
                'trade_direction': 'both',
                'exit_mode': 'fixed_hours',
                'hold_hours': 48
            }
        },
        {
            'name': 'CME Both (Friday close)',
            'params': {
                'direction_mode': 'first_candle',
                'trade_direction': 'both',
                'exit_mode': 'friday_close',
            }
        },
        # Long only
        {
            'name': 'CME Long Only (24h)',
            'params': {
                'direction_mode': 'first_candle',
                'trade_direction': 'long_only',
                'exit_mode': 'fixed_hours',
                'hold_hours': 24
            }
        },
        # Short only
        {
            'name': 'CME Short Only (24h)',
            'params': {
                'direction_mode': 'first_candle',
                'trade_direction': 'short_only',
                'exit_mode': 'fixed_hours',
                'hold_hours': 24
            }
        },
        # Stop loss / Take profit version
        {
            'name': 'CME Both (2% SL, 4% TP)',
            'params': {
                'direction_mode': 'first_candle',
                'trade_direction': 'both',
                'exit_mode': 'stop_and_target',
                'stop_loss_pct': 2.0,
                'take_profit_pct': 4.0
            }
        },
    ]

    results_list = []

    print("=" * 80)
    print("CME SUNDAY OPEN STRATEGY - MULTI-ASSET BACKTEST")
    print("=" * 80)
    print(f"Period: {days_back} days")
    print(f"Initial Capital: ${initial_capital:,}")
    print("=" * 80)

    for symbol, asset_name in assets:
        print(f"\n{'='*60}")
        print(f"FETCHING: {asset_name} ({symbol})")
        print(f"{'='*60}")

        try:
            # Fetch hourly data
            data = fetcher.fetch_ohlcv(symbol, '1h', days_back=days_back)

            if len(data) < 100:
                print(f"  Skipping {asset_name} - insufficient data")
                continue

            # Calculate buy & hold return for comparison
            buy_hold_return = ((data['close'].iloc[-1] - data['close'].iloc[0]) / data['close'].iloc[0]) * 100

            print(f"  Data range: {data.index[0]} to {data.index[-1]}")
            print(f"  Candles: {len(data)}")
            print(f"  Buy & Hold: {buy_hold_return:+.2f}%")

            # Test each strategy configuration
            for config in strategy_configs:
                strategy = CMESundayOpenStrategy(**config['params'])
                results = run_single_backtest(symbol, data, strategy, initial_capital)

                results_list.append({
                    'Asset': asset_name,
                    'Symbol': symbol,
                    'Strategy': config['name'],
                    'Total Return %': results['total_return_pct'],
                    'Buy & Hold %': buy_hold_return,
                    'Alpha %': results['total_return_pct'] - buy_hold_return,
                    'Total Trades': results['total_trades'],
                    'Long Trades': results['long_trades'],
                    'Short Trades': results['short_trades'],
                    'Win Rate %': results['win_rate'],
                    'Max Drawdown %': results['max_drawdown'],
                    'Final Value': results['final_value']
                })

                print(f"  {config['name']}: {results['total_return_pct']:+.2f}% "
                      f"(Win: {results['win_rate']:.0f}%, Trades: {results['total_trades']})")

        except Exception as e:
            print(f"  Error processing {asset_name}: {e}")
            continue

    # Create results DataFrame
    results_df = pd.DataFrame(results_list)

    return results_df


def print_summary(results_df):
    """Print a formatted summary of results"""
    print("\n" + "=" * 100)
    print("SUMMARY: CME SUNDAY OPEN STRATEGY RESULTS")
    print("=" * 100)

    # Best performers by asset
    print("\n📊 BEST STRATEGY BY ASSET:")
    print("-" * 80)
    for asset in results_df['Asset'].unique():
        asset_results = results_df[results_df['Asset'] == asset]
        best = asset_results.loc[asset_results['Total Return %'].idxmax()]
        print(f"  {asset:12} | Best: {best['Strategy']:25} | Return: {best['Total Return %']:+7.2f}% | "
              f"Win Rate: {best['Win Rate %']:5.1f}%")

    # Overall best strategies
    print("\n📈 TOP 5 OVERALL PERFORMERS:")
    print("-" * 80)
    top5 = results_df.nlargest(5, 'Total Return %')
    for _, row in top5.iterrows():
        print(f"  {row['Asset']:12} | {row['Strategy']:25} | Return: {row['Total Return %']:+7.2f}% | "
              f"Alpha: {row['Alpha %']:+7.2f}%")

    # Worst performers (to see what doesn't work)
    print("\n📉 BOTTOM 5 PERFORMERS:")
    print("-" * 80)
    bottom5 = results_df.nsmallest(5, 'Total Return %')
    for _, row in bottom5.iterrows():
        print(f"  {row['Asset']:12} | {row['Strategy']:25} | Return: {row['Total Return %']:+7.2f}% | "
              f"Alpha: {row['Alpha %']:+7.2f}%")

    # Strategy comparison across all assets
    print("\n📋 STRATEGY COMPARISON (Average across all assets):")
    print("-" * 80)
    strategy_summary = results_df.groupby('Strategy').agg({
        'Total Return %': 'mean',
        'Alpha %': 'mean',
        'Win Rate %': 'mean',
        'Total Trades': 'mean',
        'Max Drawdown %': 'mean'
    }).round(2)
    strategy_summary = strategy_summary.sort_values('Total Return %', ascending=False)
    print(strategy_summary.to_string())

    # Long vs Short analysis
    print("\n🔄 LONG VS SHORT ANALYSIS:")
    print("-" * 80)
    long_only = results_df[results_df['Strategy'].str.contains('Long Only')]
    short_only = results_df[results_df['Strategy'].str.contains('Short Only')]

    if len(long_only) > 0:
        print(f"  Long Only Avg Return:  {long_only['Total Return %'].mean():+.2f}%")
    if len(short_only) > 0:
        print(f"  Short Only Avg Return: {short_only['Total Return %'].mean():+.2f}%")

    return results_df


def save_results(results_df, filename='cme_sunday_results.csv'):
    """Save results to CSV"""
    filepath = f"results/{filename}"
    os.makedirs('results', exist_ok=True)
    results_df.to_csv(filepath, index=False)
    print(f"\n💾 Results saved to {filepath}")


if __name__ == "__main__":
    # Run the backtest
    # Using 365 days to get ~52 Sunday opens
    results_df = run_multi_asset_backtest(days_back=365, initial_capital=10000)

    # Print summary
    print_summary(results_df)

    # Save results
    save_results(results_df)

    print("\n" + "=" * 80)
    print("BACKTEST COMPLETE")
    print("=" * 80)
