"""
Explore Open Interest Data Availability

Learning moment: Open Interest vs Volume
- Volume = how many contracts traded in a period
- Open Interest = total outstanding contracts at a point in time
- OI increasing + price rising = new money entering (bullish conviction)
- OI decreasing + price rising = short squeeze (shorts covering)
- OI increasing + price falling = new shorts entering (bearish conviction)
- OI decreasing + price falling = long liquidations

This script explores what OI data is available from different sources.
"""

import ccxt
import requests
import pandas as pd
from datetime import datetime, timedelta
import time

def explore_binance_oi():
    """
    Explore Binance Open Interest endpoints

    Binance has two main endpoints:
    1. /fapi/v1/openInterest - Current OI (single point)
    2. /futures/data/openInterestHist - Historical OI (limited history)
    """
    print("=" * 60)
    print("EXPLORING BINANCE OPEN INTEREST DATA")
    print("=" * 60)

    # Method 1: Using CCXT for current OI
    print("\n1. Current Open Interest via CCXT:")
    try:
        exchange = ccxt.binanceusdm()  # USD-M Futures (perpetuals)

        # Fetch current open interest
        oi = exchange.fetch_open_interest('BTC/USDT:USDT')
        print(f"   Current BTC Open Interest: {oi['openInterestAmount']:,.2f} BTC")
        print(f"   Value: ${oi['openInterestValue']:,.0f}")
        print(f"   Timestamp: {oi['datetime']}")
    except Exception as e:
        print(f"   Error: {e}")

    # Method 2: Historical OI via Binance API directly
    print("\n2. Historical Open Interest via Binance API:")
    try:
        # Binance futures data endpoint
        url = "https://fapi.binance.com/futures/data/openInterestHist"

        # Try different periods
        for period in ['5m', '15m', '30m', '1h', '4h', '1d']:
            params = {
                'symbol': 'BTCUSDT',
                'period': period,
                'limit': 500  # Max is 500
            }
            response = requests.get(url, params=params)
            data = response.json()

            if isinstance(data, list) and len(data) > 0:
                df = pd.DataFrame(data)
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                oldest = df['timestamp'].min()
                newest = df['timestamp'].max()
                days_available = (newest - oldest).days
                print(f"   {period}: {len(data)} records, {days_available} days ({oldest.date()} to {newest.date()})")
            else:
                print(f"   {period}: Error or no data - {data}")

            time.sleep(0.2)  # Rate limit

    except Exception as e:
        print(f"   Error: {e}")

    # Method 3: Check what the longest period available is
    print("\n3. Fetching maximum 1h historical data:")
    try:
        url = "https://fapi.binance.com/futures/data/openInterestHist"
        params = {
            'symbol': 'BTCUSDT',
            'period': '1h',
            'limit': 500
        }
        response = requests.get(url, params=params)
        data = response.json()

        if isinstance(data, list) and len(data) > 0:
            df = pd.DataFrame(data)
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df['sumOpenInterest'] = df['sumOpenInterest'].astype(float)
            df['sumOpenInterestValue'] = df['sumOpenInterestValue'].astype(float)

            print(f"\n   Data sample (first 5 rows):")
            print(df[['timestamp', 'sumOpenInterest', 'sumOpenInterestValue']].head().to_string())

            print(f"\n   Data sample (last 5 rows):")
            print(df[['timestamp', 'sumOpenInterest', 'sumOpenInterestValue']].tail().to_string())

            print(f"\n   Total range: {df['timestamp'].min()} to {df['timestamp'].max()}")
            print(f"   Days available: {(df['timestamp'].max() - df['timestamp'].min()).days}")

            return df
    except Exception as e:
        print(f"   Error: {e}")

    return None

def explore_coinglass_free():
    """
    Check CoinGlass public data (no API key)
    CoinGlass has great OI data but most requires subscription
    """
    print("\n" + "=" * 60)
    print("EXPLORING COINGLASS (FREE DATA)")
    print("=" * 60)

    # CoinGlass has some public endpoints
    try:
        # This is their public aggregated OI endpoint
        url = "https://open-api.coinglass.com/public/v2/open_interest"
        params = {'symbol': 'BTC'}

        headers = {'accept': 'application/json'}
        response = requests.get(url, params=params, headers=headers)

        if response.status_code == 200:
            data = response.json()
            print(f"   Response: {data}")
        else:
            print(f"   Status {response.status_code}: API requires authentication for most data")
    except Exception as e:
        print(f"   Error: {e}")

def fetch_extended_oi_history():
    """
    Attempt to fetch more historical OI by paginating

    Learning moment: API Pagination
    Many APIs limit how much data you can get per request.
    To get more history, you need to make multiple requests
    with different time ranges (pagination).
    """
    print("\n" + "=" * 60)
    print("ATTEMPTING EXTENDED HISTORICAL OI FETCH")
    print("=" * 60)

    url = "https://fapi.binance.com/futures/data/openInterestHist"
    all_data = []

    # Try to go back in time by specifying endTime
    end_time = int(datetime.now().timestamp() * 1000)

    for i in range(10):  # Try 10 batches
        params = {
            'symbol': 'BTCUSDT',
            'period': '1h',
            'limit': 500,
            'endTime': end_time
        }

        response = requests.get(url, params=params)
        data = response.json()

        if not isinstance(data, list) or len(data) == 0:
            print(f"   Batch {i+1}: No more data available")
            break

        all_data.extend(data)

        # Move end_time to before the oldest record we got
        oldest_ts = min(d['timestamp'] for d in data)
        end_time = oldest_ts - 1

        oldest_date = datetime.fromtimestamp(oldest_ts / 1000)
        print(f"   Batch {i+1}: Got {len(data)} records back to {oldest_date}")

        time.sleep(0.3)  # Rate limit

    if all_data:
        # Remove duplicates and sort
        df = pd.DataFrame(all_data)
        df = df.drop_duplicates(subset='timestamp')
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df = df.sort_values('timestamp')

        print(f"\n   Total records: {len(df)}")
        print(f"   Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        print(f"   Days of data: {(df['timestamp'].max() - df['timestamp'].min()).days}")

        return df

    return None


if __name__ == "__main__":
    # Explore all sources
    binance_df = explore_binance_oi()
    explore_coinglass_free()
    extended_df = fetch_extended_oi_history()

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print("""
Key findings:
1. Binance free API provides ~20-30 days of hourly OI history
2. CoinGlass requires paid API for historical data
3. For 1 year of data, we'd need:
   - A paid data source (CoinGlass, Glassnode)
   - Or cached historical data (Kaggle datasets)
   - Or start collecting data now for future analysis

Recommendation:
- Use the 20-30 days we can get for initial analysis
- This is enough to test if OI has predictive value
- If promising, consider paid data for longer backtest
""")

    # Save what we got
    if extended_df is not None:
        extended_df.to_csv('data/btc_open_interest_hourly.csv', index=False)
        print("\nSaved available OI data to data/btc_open_interest_hourly.csv")
