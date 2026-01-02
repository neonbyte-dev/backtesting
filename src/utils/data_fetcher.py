"""
Data Fetcher - Downloads historical price data from Binance

This module fetches OHLCV (Open, High, Low, Close, Volume) candle data
which is the foundation of all backtesting.
"""

import ccxt
import pandas as pd
from datetime import datetime, timedelta
import time


class DataFetcher:
    """Fetches historical cryptocurrency data from Binance"""

    def __init__(self):
        # Create Binance exchange connection (no API key needed for public data)
        self.exchange = ccxt.binance({
            'enableRateLimit': True,  # Respect Binance rate limits
        })

    def fetch_ohlcv(self, symbol='BTC/USDT', timeframe='1h', days_back=30):
        """
        Fetch historical OHLCV data

        Args:
            symbol: Trading pair (e.g., 'BTC/USDT', 'ETH/USDT')
            timeframe: Candle size - '1m', '5m', '15m', '1h', '4h', '1d'
            days_back: How many days of history to fetch

        Returns:
            pandas DataFrame with columns: timestamp, open, high, low, close, volume
        """
        print(f"📥 Fetching {days_back} days of {timeframe} data for {symbol}...")

        # Calculate start time (Binance wants milliseconds since epoch)
        since = self.exchange.parse8601(
            (datetime.now() - timedelta(days=days_back)).isoformat()
        )

        all_candles = []

        # Binance limits to 1000 candles per request, so we might need multiple requests
        while True:
            try:
                candles = self.exchange.fetch_ohlcv(
                    symbol=symbol,
                    timeframe=timeframe,
                    since=since,
                    limit=1000
                )

                if not candles:
                    break

                all_candles.extend(candles)

                # If we got less than 1000, we're done
                if len(candles) < 1000:
                    break

                # Update 'since' to fetch next batch
                since = candles[-1][0] + 1

                # Small delay to respect rate limits
                time.sleep(0.1)

            except Exception as e:
                print(f"❌ Error fetching data: {e}")
                break

        # Convert to DataFrame
        df = pd.DataFrame(
            all_candles,
            columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
        )

        # Convert timestamp to readable datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

        # Set timestamp as index (makes time-based analysis easier)
        df.set_index('timestamp', inplace=True)

        print(f"✅ Fetched {len(df)} candles from {df.index[0]} to {df.index[-1]}")

        return df

    def save_to_csv(self, df, filename):
        """Save DataFrame to CSV for later use"""
        filepath = f"data/{filename}"
        df.to_csv(filepath)
        print(f"💾 Saved to {filepath}")

    def load_from_csv(self, filename):
        """Load previously saved data"""
        filepath = f"data/{filename}"
        df = pd.read_csv(filepath, index_col='timestamp', parse_dates=True)
        print(f"📂 Loaded {len(df)} candles from {filepath}")
        return df


# Quick test if run directly
if __name__ == "__main__":
    fetcher = DataFetcher()

    # Fetch 7 days of hourly BTC data
    df = fetcher.fetch_ohlcv('BTC/USDT', '1h', days_back=7)

    print("\nFirst 5 rows:")
    print(df.head())

    print("\nLast 5 rows:")
    print(df.tail())

    # Save it
    fetcher.save_to_csv(df, 'BTC_USDT_1h_7d.csv')
