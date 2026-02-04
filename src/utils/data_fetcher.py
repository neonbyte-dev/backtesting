"""
Data Fetcher - Downloads historical price data from exchanges

This module fetches OHLCV (Open, High, Low, Close, Volume) candle data
which is the foundation of all backtesting.

Supports:
- Binance (default for most assets)
- Hyperliquid (for HYPE and other HL-native tokens)
"""

import ccxt
import pandas as pd
import requests
from datetime import datetime, timedelta
import time


class DataFetcher:
    """Fetches historical cryptocurrency data from multiple exchanges"""

    # Assets that should use Hyperliquid instead of Binance
    # Includes HL-native tokens and commodities traded on HL
    HYPERLIQUID_ASSETS = ['HYPE', 'PURR', 'JEFF', 'GOLD', 'SILVER']

    def __init__(self):
        # Create Binance exchange connection (no API key needed for public data)
        self.exchange = ccxt.binance({
            'enableRateLimit': True,  # Respect Binance rate limits
        })

        # Hyperliquid API endpoint
        self.hyperliquid_url = 'https://api.hyperliquid.xyz/info'

    def fetch_ohlcv(self, symbol='BTC/USDT', timeframe='1h', days_back=30):
        """
        Fetch historical OHLCV data

        Args:
            symbol: Trading pair (e.g., 'BTC/USDT', 'ETH/USDT', 'HYPE/USDT')
            timeframe: Candle size - '1m', '5m', '15m', '1h', '4h', '1d'
            days_back: How many days of history to fetch

        Returns:
            pandas DataFrame with columns: timestamp, open, high, low, close, volume
        """
        # Extract base asset from symbol (e.g., 'HYPE' from 'HYPE/USDT')
        base_asset = symbol.split('/')[0]

        # Route Hyperliquid-native assets to Hyperliquid API
        if base_asset in self.HYPERLIQUID_ASSETS:
            return self._fetch_from_hyperliquid(base_asset, timeframe, days_back)

        return self._fetch_from_binance(symbol, timeframe, days_back)

    def _fetch_from_hyperliquid(self, coin, timeframe='1h', days_back=30):
        """Fetch data from Hyperliquid API"""

        # Hyperliquid has limited history for fine intervals:
        # - 1h: ~6 months of data
        # - 4h: ~9 months of data
        # - 1d: ~12+ months of data
        # For older data, use coarser intervals
        if days_back > 200 and timeframe in ['1m', '5m', '15m', '1h']:
            print(f"⚠️ {coin}: Using 4h candles (1h not available for {days_back} days back)")
            timeframe = '4h'

        print(f"📥 Fetching {days_back} days of {timeframe} data for {coin} from Hyperliquid...")

        # Map timeframe to Hyperliquid interval format
        interval_map = {
            '1m': '1m', '5m': '5m', '15m': '15m',
            '1h': '1h', '4h': '4h', '1d': '1d'
        }
        interval = interval_map.get(timeframe, '1h')

        start_time = int((datetime.now() - timedelta(days=days_back)).timestamp() * 1000)
        end_time = int(datetime.now().timestamp() * 1000)

        all_candles = []

        # Hyperliquid may limit results, so paginate
        current_start = start_time
        while current_start < end_time:
            payload = {
                'type': 'candleSnapshot',
                'req': {
                    'coin': coin,
                    'interval': interval,
                    'startTime': current_start,
                    'endTime': end_time
                }
            }

            try:
                response = requests.post(
                    self.hyperliquid_url,
                    json=payload,
                    headers={'Content-Type': 'application/json'},
                    timeout=30
                )

                if response.status_code != 200:
                    print(f"❌ Hyperliquid API error: {response.status_code}")
                    break

                data = response.json()
                if not data:
                    break

                all_candles.extend(data)

                # Move start time forward for next batch
                last_ts = data[-1]['t']
                if last_ts <= current_start:
                    break
                current_start = last_ts + 1

                # Small delay
                time.sleep(0.1)

            except Exception as e:
                print(f"❌ Error fetching from Hyperliquid: {e}")
                break

        if not all_candles:
            print(f"❌ No data returned from Hyperliquid for {coin}")
            return pd.DataFrame()

        # Convert Hyperliquid format to standard OHLCV DataFrame
        # Hyperliquid returns: {'t': timestamp, 'o': open, 'h': high, 'l': low, 'c': close, 'v': volume}
        df = pd.DataFrame([
            {
                'timestamp': candle['t'],
                'open': float(candle['o']),
                'high': float(candle['h']),
                'low': float(candle['l']),
                'close': float(candle['c']),
                'volume': float(candle['v'])
            }
            for candle in all_candles
        ])

        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        df = df.sort_index()

        # Remove duplicates
        df = df[~df.index.duplicated(keep='first')]

        print(f"✅ Fetched {len(df)} candles from {df.index[0]} to {df.index[-1]}")
        return df

    def _fetch_from_binance(self, symbol, timeframe='1h', days_back=30):
        """Fetch data from Binance"""
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
