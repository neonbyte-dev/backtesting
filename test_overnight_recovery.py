"""
Test Overnight Recovery Strategy - Buy at 3 PM, Sell at 9:30 AM Next Day

THE HYPOTHESIS:
BTC dumps from 9:30 AM → 3 PM EST (during US market hours)
Then recovers overnight before the next dump cycle

STRATEGY:
- Entry: 3:00 PM EST (end of dump, lowest point)
- Exit: 9:30 AM EST next day (before next dump starts)
- Goal: Capture overnight recovery

This script will run the backtest and show you intraday visualizations
to confirm the timing is working correctly.
"""

import sys
sys.path.append('src')

from utils.data_fetcher import DataFetcher
from backtester import Backtester
from strategies.market_open_dump import MarketOpenDumpStrategy
from utils.visualizer import PerformanceVisualizer


def main():
    """Run overnight recovery strategy backtest"""

    print("\n" + "="*60)
    print("🌙 OVERNIGHT RECOVERY STRATEGY TEST")
    print("="*60 + "\n")

    # ==========================================
    # STEP 1: Get Historical Data
    # ==========================================
    print("STEP 1: Fetching historical data...")

    fetcher = DataFetcher()

    # Configure data
    SYMBOL = 'BTC/USDT'
    TIMEFRAME = '5m'         # 5-minute candles for precise timing
    DAYS_BACK = 90           # 3 months of data

    data = fetcher.fetch_ohlcv(SYMBOL, TIMEFRAME, days_back=DAYS_BACK)

    # ==========================================
    # STEP 2: Configure Overnight Strategy
    # ==========================================
    print("\nSTEP 2: Initializing overnight recovery strategy...")

    strategy = MarketOpenDumpStrategy(
        entry_mode='end_of_dump',         # Buy at end of dump
        exit_mode='next_day_premarket',   # Sell next day before dump
        dump_end_hour=15,                 # 3 PM EST (end of dump)
        timezone='America/New_York'
    )

    # ==========================================
    # STEP 3: Run Backtest
    # ==========================================
    print("\nSTEP 3: Running backtest simulation...")

    backtester = Backtester(
        initial_capital=10000,
        fee_percent=0.1,
        display_timezone='America/New_York'  # Show times in EST for clarity
    )

    results = backtester.run(data, strategy)

    # ==========================================
    # STEP 4: Visualize Results
    # ==========================================
    print("\nSTEP 4: Generating visualizations...")

    visualizer = PerformanceVisualizer()

    # Show trade log
    visualizer.print_trade_log(results)

    # Create standard performance charts
    print("\n📊 Creating standard performance charts...")
    visualizer.plot_results(results, data, save_path='results/overnight_recovery_performance.png')

    # Create intraday analysis (NEW!)
    print("\n📊 Creating intraday pattern analysis...")
    visualizer.plot_intraday_analysis(results, data, save_path='results/overnight_recovery_intraday.png')

    print("\n✅ Backtest complete!")
    print("\nCharts saved:")
    print("  1. results/overnight_recovery_performance.png")
    print("  2. results/overnight_recovery_intraday.png")
    print("\nThe intraday chart will show you:")
    print("  - Are entries happening at 3 PM?")
    print("  - Are exits happening at 9:30 AM next day?")
    print("  - Which entry hours are most profitable?")
    print("  - How long are we holding (should be ~18.5 hours)?")
    print()


if __name__ == "__main__":
    main()
