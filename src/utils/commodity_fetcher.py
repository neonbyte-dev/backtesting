"""
Commodity Data Fetcher

Fetches price data for commodities using multiple sources:

GOLD:
- Primary: Bybit XAUT/USDT (gold-backed token) - best history
- Fallback: OKX XAU/USDT:USDT perpetual futures
- Fallback: Binance PAXG/USDT spot

SILVER:
- Primary: Bitget XAG/USDT:USDT perpetual futures
- Fallback: Binance XAG/USDT:USDT futures (limited history from Jan 2026)

LEARNING MOMENT: Multiple Data Source Strategy
=============================================
Different exchanges launched commodity perps at different times.
To get the longest possible history, we try multiple sources:
1. Bybit has XAUT going back the furthest for gold
2. Bitget has XAG perps with decent history
3. We use fallbacks when primary fails or has gaps
"""

import ccxt
import pandas as pd
from datetime import datetime, timedelta
import time


class CommodityFetcher:
    """Fetches commodity price data from multiple exchanges"""

    # Data sources with priority order
    GOLD_SOURCES = [
        {'exchange': 'bybit', 'symbol': 'XAUT/USDT:USDT', 'type': 'swap', 'name': 'Bybit XAUT perp'},
        {'exchange': 'okx', 'symbol': 'XAU/USDT:USDT', 'type': 'swap', 'name': 'OKX XAU perp'},
        {'exchange': 'binance', 'symbol': 'PAXG/USDT', 'type': 'spot', 'name': 'Binance PAXG spot'},
    ]

    SILVER_SOURCES = [
        {'exchange': 'bitget', 'symbol': 'XAG/USDT:USDT', 'type': 'swap', 'name': 'Bitget XAG perp'},
        {'exchange': 'binance', 'symbol': 'XAG/USDT:USDT', 'type': 'future', 'name': 'Binance XAG futures'},
    ]

    def __init__(self):
        # Initialize exchanges lazily
        self._exchanges = {}

    def _get_exchange(self, name, exchange_type):
        """Get or create exchange instance"""
        key = f"{name}_{exchange_type}"
        if key not in self._exchanges:
            if name == 'binance':
                self._exchanges[key] = ccxt.binance({
                    'enableRateLimit': True,
                    'options': {'defaultType': exchange_type}
                })
            elif name == 'bybit':
                self._exchanges[key] = ccxt.bybit({
                    'enableRateLimit': True,
                    'options': {'defaultType': exchange_type}
                })
            elif name == 'okx':
                self._exchanges[key] = ccxt.okx({
                    'enableRateLimit': True,
                    'options': {'defaultType': exchange_type}
                })
            elif name == 'bitget':
                self._exchanges[key] = ccxt.bitget({
                    'enableRateLimit': True,
                    'options': {'defaultType': exchange_type}
                })
        return self._exchanges[key]

    def _fetch_from_source(self, source, timeframe, days_back):
        """Fetch data from a specific source"""
        exchange = self._get_exchange(source['exchange'], source['type'])
        symbol = source['symbol']

        since = exchange.parse8601(
            (datetime.now() - timedelta(days=days_back)).isoformat()
        )

        all_candles = []

        while True:
            try:
                candles = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=1000)
                if not candles:
                    break

                all_candles.extend(candles)

                if len(candles) < 1000:
                    break

                since = candles[-1][0] + 1
                time.sleep(0.1)

            except Exception as e:
                return None, str(e)

        if not all_candles:
            return None, "No data returned"

        df = pd.DataFrame(
            all_candles,
            columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
        )

        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)

        return df, None

    def fetch_ohlcv(self, commodity, timeframe='1h', days_back=365):
        """
        Fetch OHLCV data for a commodity, trying multiple sources

        Args:
            commodity: 'GOLD' or 'SILVER'
            timeframe: '1h', '4h', '1d', etc.
            days_back: How many days of history to fetch

        Returns:
            pandas DataFrame with OHLCV data
        """
        commodity = commodity.upper()

        if commodity == 'GOLD':
            sources = self.GOLD_SOURCES
        elif commodity == 'SILVER':
            sources = self.SILVER_SOURCES
        else:
            raise ValueError(f"Unknown commodity: {commodity}. Supported: GOLD, SILVER")

        print(f"📥 Fetching {days_back} days of {timeframe} data for {commodity}...")

        # Try each source in priority order
        for source in sources:
            print(f"  Trying {source['name']}...", end=" ")
            df, error = self._fetch_from_source(source, timeframe, days_back)

            if df is not None and len(df) > 0:
                print(f"✅ {len(df)} candles ({df.index[0].date()} to {df.index[-1].date()})")
                return df
            else:
                print(f"❌ {error}")

        print(f"⚠️ No data found for {commodity} from any source")
        return pd.DataFrame()


if __name__ == "__main__":
    fetcher = CommodityFetcher()

    print("\n" + "="*60)
    print("Testing Commodity Data Fetcher - Multi-Source")
    print("="*60)

    print("\n=== Testing GOLD ===")
    gold = fetcher.fetch_ohlcv('GOLD', '1h', days_back=200)
    if not gold.empty:
        print(f"  Total candles: {len(gold)}")
        print(f"  Date range: {gold.index[0]} to {gold.index[-1]}")
        print(f"  Price range: ${gold['close'].min():.2f} to ${gold['close'].max():.2f}")

    print("\n=== Testing SILVER ===")
    silver = fetcher.fetch_ohlcv('SILVER', '1h', days_back=200)
    if not silver.empty:
        print(f"  Total candles: {len(silver)}")
        print(f"  Date range: {silver.index[0]} to {silver.index[-1]}")
        print(f"  Price range: ${silver['close'].min():.2f} to ${silver['close'].max():.2f}")
