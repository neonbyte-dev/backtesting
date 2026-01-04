"""
Open Interest + Never Sell at Loss Strategy

This is the LIVE TRADING version of our backtested OI strategy.

Strategy Rules (from backtesting optimization):
1. Entry:
   - OI drops >= 0.15% over 4 hours
   - Price drops >= 0.3% over 4 hours
   - Price is >= 0.5% BELOW 24h moving average
2. Exit: Profit target +1.0% (NO stop loss, NO time limit)
3. Position: 100% of capital per trade

Performance (backtest):
- Return: +10.61%
- Win Rate: 100% (9 trades)
- Philosophy: Never sell at a loss - hold until profitable

Key Difference vs Backtest:
- Backtest: Processes all historical data at once
- Live: Checks current conditions and fetches OI from Binance API
"""

import requests
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Tuple, List
import pytz


class BinanceOIFetcher:
    """
    Fetches Open Interest data from Binance Futures API

    Binance provides free OI data for futures markets.
    We use BTCUSDT perpetual contract data.
    """

    BASE_URL = "https://fapi.binance.com"

    def __init__(self, lookback_hours: int = 24):
        """
        Args:
            lookback_hours: How many hours of data to fetch (for SMA calculation)
        """
        self.lookback_hours = lookback_hours
        self.session = requests.Session()

        # Cache to avoid hitting API too frequently
        self._oi_cache = []
        self._price_cache = []
        self._last_fetch = None
        self._cache_ttl = 300  # 5 minutes cache

    def _fetch_oi_history(self, hours: int = 24) -> List[dict]:
        """
        Fetch hourly OI data from Binance

        Returns:
            List of {timestamp, oi} dicts sorted by time
        """
        try:
            # Binance OI endpoint: /fapi/v1/openInterestHist
            # Requires symbol, period (5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d)
            end_time = int(datetime.now().timestamp() * 1000)
            start_time = int((datetime.now() - timedelta(hours=hours)).timestamp() * 1000)

            url = f"{self.BASE_URL}/futures/data/openInterestHist"
            params = {
                'symbol': 'BTCUSDT',
                'period': '1h',
                'limit': hours + 1,
                'startTime': start_time,
                'endTime': end_time
            }

            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Parse response: [{"symbol": "BTCUSDT", "sumOpenInterest": "...", "timestamp": ...}, ...]
            oi_data = []
            for item in data:
                oi_data.append({
                    'timestamp': datetime.fromtimestamp(item['timestamp'] / 1000, tz=pytz.UTC),
                    'oi': float(item['sumOpenInterest'])  # OI in BTC
                })

            return sorted(oi_data, key=lambda x: x['timestamp'])

        except Exception as e:
            print(f"Error fetching OI history: {e}")
            return []

    def _fetch_price_history(self, hours: int = 24) -> List[dict]:
        """
        Fetch hourly price (klines) data from Binance

        Returns:
            List of {timestamp, close} dicts sorted by time
        """
        try:
            url = f"{self.BASE_URL}/fapi/v1/klines"
            params = {
                'symbol': 'BTCUSDT',
                'interval': '1h',
                'limit': hours + 1
            }

            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Parse klines: [[open_time, open, high, low, close, ...], ...]
            price_data = []
            for candle in data:
                price_data.append({
                    'timestamp': datetime.fromtimestamp(candle[0] / 1000, tz=pytz.UTC),
                    'close': float(candle[4])
                })

            return sorted(price_data, key=lambda x: x['timestamp'])

        except Exception as e:
            print(f"Error fetching price history: {e}")
            return []

    def refresh_data(self, force: bool = False) -> bool:
        """
        Refresh OI and price data from Binance

        Args:
            force: If True, bypass cache TTL

        Returns:
            True if data was refreshed successfully
        """
        now = datetime.now(pytz.UTC)

        # Check cache TTL
        if not force and self._last_fetch:
            elapsed = (now - self._last_fetch).total_seconds()
            if elapsed < self._cache_ttl:
                return True

        # Fetch new data
        self._oi_cache = self._fetch_oi_history(self.lookback_hours)
        self._price_cache = self._fetch_price_history(self.lookback_hours)

        if self._oi_cache and self._price_cache:
            self._last_fetch = now
            return True

        return False

    def get_oi_change_pct(self, hours: int = 4) -> Optional[float]:
        """
        Calculate OI percentage change over specified hours

        Args:
            hours: Lookback period in hours

        Returns:
            OI change as percentage (e.g., -0.15 means dropped 0.15%)
        """
        if len(self._oi_cache) < hours + 1:
            return None

        current_oi = self._oi_cache[-1]['oi']
        past_oi = self._oi_cache[-(hours + 1)]['oi']

        if past_oi == 0:
            return None

        return ((current_oi - past_oi) / past_oi) * 100

    def get_price_change_pct(self, hours: int = 4) -> Optional[float]:
        """
        Calculate price percentage change over specified hours

        Returns:
            Price change as percentage
        """
        if len(self._price_cache) < hours + 1:
            return None

        current_price = self._price_cache[-1]['close']
        past_price = self._price_cache[-(hours + 1)]['close']

        if past_price == 0:
            return None

        return ((current_price - past_price) / past_price) * 100

    def get_sma(self, hours: int = 24) -> Optional[float]:
        """
        Calculate Simple Moving Average of price

        Args:
            hours: SMA period in hours

        Returns:
            SMA value
        """
        if len(self._price_cache) < hours:
            return None

        prices = [p['close'] for p in self._price_cache[-hours:]]
        return np.mean(prices)

    def get_current_price(self) -> Optional[float]:
        """Get the most recent price from cache"""
        if not self._price_cache:
            return None
        return self._price_cache[-1]['close']

    def get_distance_from_sma_pct(self, sma_hours: int = 24) -> Optional[float]:
        """
        Calculate how far current price is from SMA as percentage

        Returns:
            Negative = below SMA, Positive = above SMA
            e.g., -0.5 means price is 0.5% below SMA
        """
        current_price = self.get_current_price()
        sma = self.get_sma(sma_hours)

        if current_price is None or sma is None or sma == 0:
            return None

        return ((current_price - sma) / sma) * 100


class OIStrategy:
    """
    Live trading implementation of OI + Never Sell Loss strategy

    Entry Conditions (ALL must be met):
    1. OI dropped >= 0.15% over 4 hours (liquidation signal)
    2. Price dropped >= 0.3% over 4 hours (oversold signal)
    3. Price is >= 0.5% BELOW 24h SMA (not buying at highs)

    Exit Conditions:
    1. Price reaches +1.0% profit target
    2. NO stop loss (never sell at loss)
    3. NO time limit (hold until profitable)
    """

    def __init__(self, config: dict):
        """
        Initialize strategy with configuration

        Args:
            config: Strategy parameters from config.json

        Example config:
            {
                "oi_drop_threshold": -0.15,      # OI must drop this much (%)
                "price_drop_threshold": -0.3,    # Price must drop this much (%)
                "sma_distance_threshold": -0.5,  # Price must be this far below SMA (%)
                "profit_target_pct": 1.0,        # Exit when this profitable (%)
                "oi_lookback_hours": 4,          # OI lookback period
                "sma_hours": 24,                 # SMA period
                "min_hours_between_trades": 8    # Cooldown between trades
            }
        """
        self.oi_drop_threshold = config.get('oi_drop_threshold', -0.15)
        self.price_drop_threshold = config.get('price_drop_threshold', -0.3)
        self.sma_distance_threshold = config.get('sma_distance_threshold', -0.5)
        self.profit_target_pct = config.get('profit_target_pct', 1.0)
        self.oi_lookback_hours = config.get('oi_lookback_hours', 4)
        self.sma_hours = config.get('sma_hours', 24)
        self.min_hours_between_trades = config.get('min_hours_between_trades', 8)

        # Initialize OI data fetcher
        self.oi_fetcher = BinanceOIFetcher(lookback_hours=max(self.sma_hours, 48))

        # Track last trade time for cooldown
        self.last_trade_time = None

    def should_enter(self, current_time: datetime, current_price: float) -> Tuple[bool, str]:
        """
        Decide if we should BUY right now

        Entry Conditions (ALL must be met):
        1. OI dropped >= 0.15% over 4 hours
        2. Price dropped >= 0.3% over 4 hours
        3. Price is >= 0.5% below 24h SMA
        4. Cooldown period has passed since last trade

        Args:
            current_time: Current timestamp (UTC aware)
            current_price: Current BTC price (from HyperLiquid)

        Returns:
            (should_buy, reason) - True/False and explanation
        """
        # Refresh OI data from Binance
        if not self.oi_fetcher.refresh_data():
            return False, "Failed to fetch OI data from Binance"

        # Check cooldown
        if self.last_trade_time:
            hours_since_trade = (current_time - self.last_trade_time).total_seconds() / 3600
            if hours_since_trade < self.min_hours_between_trades:
                return False, f"Cooldown active ({hours_since_trade:.1f}h < {self.min_hours_between_trades}h)"

        # Check OI change
        oi_change = self.oi_fetcher.get_oi_change_pct(self.oi_lookback_hours)
        if oi_change is None:
            return False, "Could not calculate OI change"

        if oi_change > self.oi_drop_threshold:
            return False, f"OI not dropping enough ({oi_change:+.2f}% > {self.oi_drop_threshold}%)"

        # Check price change (using Binance data for consistency with OI)
        price_change = self.oi_fetcher.get_price_change_pct(self.oi_lookback_hours)
        if price_change is None:
            return False, "Could not calculate price change"

        if price_change > self.price_drop_threshold:
            return False, f"Price not dropping enough ({price_change:+.2f}% > {self.price_drop_threshold}%)"

        # Check SMA distance
        sma_distance = self.oi_fetcher.get_distance_from_sma_pct(self.sma_hours)
        if sma_distance is None:
            return False, "Could not calculate SMA distance"

        if sma_distance > self.sma_distance_threshold:
            return False, f"Price not far enough below SMA ({sma_distance:+.2f}% > {self.sma_distance_threshold}%)"

        # All conditions met!
        self.last_trade_time = current_time
        sma = self.oi_fetcher.get_sma(self.sma_hours)

        reason = (f"All conditions met - "
                  f"OI: {oi_change:+.2f}% (threshold: {self.oi_drop_threshold}%), "
                  f"Price: {price_change:+.2f}%, "
                  f"Below SMA: {sma_distance:+.2f}% (SMA: ${sma:,.0f})")
        return True, reason

    def should_exit(self, current_price: float, entry_price: float,
                    peak_price: float) -> Tuple[bool, str]:
        """
        Decide if we should SELL right now

        Exit Conditions:
        1. Must be profitable by at least profit_target_pct

        NEVER sell at a loss - this is the core philosophy

        Args:
            current_price: Current BTC price
            entry_price: Our entry price
            peak_price: Highest price since entry (not used here, kept for interface)

        Returns:
            (should_sell, reason) - True/False and explanation
        """
        # Calculate profit
        profit_pct = ((current_price - entry_price) / entry_price) * 100

        # Rule: NEVER sell at a loss
        if profit_pct <= 0:
            return False, f"Not profitable (currently {profit_pct:+.2f}%) - holding until profit"

        # Check if we hit profit target
        if profit_pct >= self.profit_target_pct:
            reason = (f"Profit target hit! +{profit_pct:.2f}% >= {self.profit_target_pct}% "
                      f"(Entry: ${entry_price:,.0f} -> Exit: ${current_price:,.0f})")
            return True, reason

        # Profitable but not at target yet
        return False, f"Holding - Up {profit_pct:+.2f}% (target: +{self.profit_target_pct}%)"

    def update_peak_price(self, current_price: float, current_peak: float) -> float:
        """
        Update peak price tracker (kept for interface compatibility)

        Note: This strategy doesn't use trailing stop, but we track peak
        for monitoring purposes.
        """
        return max(current_price, current_peak)

    def reset_daily_state(self):
        """Reset daily state - nothing to reset for this strategy"""
        pass

    def get_position_size(self, balance_usd: float, current_price: float) -> float:
        """
        Calculate position size in USDC

        Strategy uses 100% of capital per trade.
        """
        return balance_usd * 0.999  # Leave 0.1% for fees

    def get_diagnostics(self) -> dict:
        """
        Get current strategy diagnostics for debugging

        Returns:
            Dict with current OI, price, and SMA metrics
        """
        self.oi_fetcher.refresh_data()

        return {
            'oi_change_4h': self.oi_fetcher.get_oi_change_pct(self.oi_lookback_hours),
            'price_change_4h': self.oi_fetcher.get_price_change_pct(self.oi_lookback_hours),
            'sma_24h': self.oi_fetcher.get_sma(self.sma_hours),
            'sma_distance_pct': self.oi_fetcher.get_distance_from_sma_pct(self.sma_hours),
            'current_price_binance': self.oi_fetcher.get_current_price(),
            'last_fetch': self.oi_fetcher._last_fetch,
            'oi_cache_size': len(self.oi_fetcher._oi_cache),
            'thresholds': {
                'oi_drop': self.oi_drop_threshold,
                'price_drop': self.price_drop_threshold,
                'sma_distance': self.sma_distance_threshold,
                'profit_target': self.profit_target_pct
            }
        }

    def __str__(self):
        """String representation for logging"""
        return (f"OIStrategy(OI<={self.oi_drop_threshold}%, "
                f"Price<={self.price_drop_threshold}%, "
                f"SMA<={self.sma_distance_threshold}%, "
                f"Target={self.profit_target_pct}%)")


# Module testing
if __name__ == '__main__':
    import json

    # Test configuration matching our backtest winner
    test_config = {
        "oi_drop_threshold": -0.15,
        "price_drop_threshold": -0.3,
        "sma_distance_threshold": -0.5,
        "profit_target_pct": 1.0,
        "oi_lookback_hours": 4,
        "sma_hours": 24,
        "min_hours_between_trades": 8
    }

    # Create strategy
    strategy = OIStrategy(test_config)
    print(f"Strategy: {strategy}")

    # Test OI fetcher
    print("\nFetching OI data from Binance...")
    if strategy.oi_fetcher.refresh_data(force=True):
        print("Data fetched successfully!")

        # Get diagnostics
        diag = strategy.get_diagnostics()
        print(f"\nDiagnostics:")
        print(f"  OI Change (4h): {diag['oi_change_4h']:+.2f}%" if diag['oi_change_4h'] else "  OI Change: N/A")
        print(f"  Price Change (4h): {diag['price_change_4h']:+.2f}%" if diag['price_change_4h'] else "  Price Change: N/A")
        print(f"  SMA (24h): ${diag['sma_24h']:,.2f}" if diag['sma_24h'] else "  SMA: N/A")
        print(f"  Distance from SMA: {diag['sma_distance_pct']:+.2f}%" if diag['sma_distance_pct'] else "  SMA Distance: N/A")
        print(f"  Current Price (Binance): ${diag['current_price_binance']:,.2f}" if diag['current_price_binance'] else "  Price: N/A")

        # Test entry logic
        print("\nTesting Entry Logic:")
        test_time = datetime.now(pytz.UTC)
        test_price = diag['current_price_binance'] or 95000

        should_buy, reason = strategy.should_enter(test_time, test_price)
        print(f"  Should Enter: {should_buy}")
        print(f"  Reason: {reason}")

        # Test exit logic
        print("\nTesting Exit Logic:")
        entry_price = test_price * 0.99  # Simulate 1% profit

        should_sell, reason = strategy.should_exit(test_price, entry_price, test_price)
        print(f"  Should Exit: {should_sell}")
        print(f"  Reason: {reason}")

    else:
        print("Failed to fetch OI data")

    print("\nAll tests completed!")
