"""
Main Backtest Runner - This is what you run to test trading ideas

Usage:
    python run_backtest.py

This script:
1. Fetches historical data
2. Runs your strategy on that data
3. Shows you the results with charts
"""

import sys
sys.path.append('src')

from utils.data_fetcher import DataFetcher
from backtester import Backtester
from strategies.moving_average_cross import MovingAverageCrossStrategy
from utils.visualizer import PerformanceVisualizer


def main():
    """Run a backtest"""

    print("\n" + "="*60)
    print("🔬 CRYPTOCURRENCY BACKTESTING LAB")
    print("="*60 + "\n")

    # ==========================================
    # STEP 1: Get Historical Data
    # ==========================================
    print("STEP 1: Fetching historical data...")

    fetcher = DataFetcher()

    # Configure what data to test on
    SYMBOL = 'BTC/USDT'      # What to trade
    TIMEFRAME = '1h'         # Candle size (1m, 5m, 15m, 1h, 4h, 1d)
    DAYS_BACK = 90           # How far back to test

    # Get the data
    data = fetcher.fetch_ohlcv(SYMBOL, TIMEFRAME, days_back=DAYS_BACK)

    # ==========================================
    # STEP 2: Choose Strategy
    # ==========================================
    print("\nSTEP 2: Initializing strategy...")

    # This is where you plug in different strategies to test
    strategy = MovingAverageCrossStrategy(
        fast_period=20,   # Try different values!
        slow_period=50    # Experiment with parameters
    )

    # ==========================================
    # STEP 3: Run Backtest
    # ==========================================
    print("\nSTEP 3: Running backtest simulation...")

    backtester = Backtester(
        initial_capital=10000,   # Start with $10,000
        fee_percent=0.1          # 0.1% fee per trade (Binance standard)
    )

    results = backtester.run(data, strategy)

    # ==========================================
    # STEP 4: Visualize Results
    # ==========================================
    print("\nSTEP 4: Generating performance charts...")

    visualizer = PerformanceVisualizer()

    # Show detailed trade log
    visualizer.print_trade_log(results)

    # Create charts
    chart_filename = f"results/{SYMBOL.replace('/', '_')}_{TIMEFRAME}_{DAYS_BACK}d.png"
    visualizer.plot_results(results, data, save_path=chart_filename)

    print("\n✅ Backtest complete!\n")


if __name__ == "__main__":
    main()
