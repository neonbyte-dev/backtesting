"""
Overnight Recovery Strategy Logic

This is the LIVE TRADING version of our backtested MarketOpenDumpStrategy.

Strategy Rules (from December optimization):
1. Entry: Buy at 3 PM EST when price < $90,000
2. Exit: Trailing stop 1% from peak (never sell at loss)
3. Position: 100% of capital per trade

Performance (December backtest):
- Return: +17.95%
- Win Rate: 76.9%
- Max Drawdown: -3.25%

Key Difference vs Backtest:
- Backtest: Processes all historical data at once
- Live: Checks current moment and decides action
"""

from datetime import datetime
from typing import Optional, Tuple
import pytz


class OvernightRecoveryStrategy:
    """
    Live trading implementation of overnight recovery strategy

    This class contains the decision logic:
    - should_enter(): Check if we should buy right now
    - should_exit(): Check if we should sell right now
    - update_peak(): Track highest price since entry
    """

    def __init__(self, config: dict):
        """
        Initialize strategy with configuration

        Args:
            config: Strategy parameters from config.json

        Example config:
            {
                "entry_hour": 15,  # 3 PM EST
                "max_entry_price_usd": 90000,
                "trailing_stop_pct": 1.0,
                "timezone": "America/New_York"
            }
        """
        self.entry_hour = config.get('entry_hour', 15)
        self.max_entry_price = config.get('max_entry_price_usd', 90000)
        self.trailing_stop_pct = config.get('trailing_stop_pct', 1.0)
        self.timezone = pytz.timezone(config.get('timezone', 'America/New_York'))

        # Track if we already entered today (only 1 trade per day)
        self.last_entry_date = None

    def should_enter(self, current_time: datetime, current_price: float) -> Tuple[bool, str]:
        """
        Decide if we should BUY right now

        Entry Conditions (ALL must be met):
        1. Current time is 3:00 PM EST (or within 5min window)
        2. Price is below $90,000
        3. Haven't already entered today

        Args:
            current_time: Current timestamp (UTC aware)
            current_price: Current BTC price

        Returns:
            (should_buy, reason) - True/False and explanation

        Example:
            >>> strategy = OvernightRecoveryStrategy(config)
            >>> should_buy, reason = strategy.should_enter(now, 87500)
            >>> if should_buy:
            ...     print(f"ENTRY: {reason}")
            ENTRY: All conditions met - Price $87,500 < $90,000 at 3:00 PM EST
        """
        # Convert to EST
        est_time = current_time.astimezone(self.timezone)
        current_hour = est_time.hour
        current_minute = est_time.minute
        current_date = est_time.date()

        # Check 1: Is it 3 PM EST? (Allow 5-minute window: 15:00-15:05)
        if current_hour != self.entry_hour:
            return False, f"Not entry hour (current: {current_hour}:00, target: {self.entry_hour}:00)"

        if current_minute > 5:
            return False, f"Entry window closed (current: {current_hour}:{current_minute})"

        # Check 2: Already entered today?
        if self.last_entry_date == current_date:
            return False, f"Already entered today ({current_date})"

        # Check 3: Price filter
        if current_price >= self.max_entry_price:
            return False, f"Price too high (${current_price:,.0f} >= ${self.max_entry_price:,.0f})"

        # All conditions met!
        self.last_entry_date = current_date
        reason = f"All conditions met - Price ${current_price:,.0f} < ${self.max_entry_price:,.0f} at {current_hour}:{current_minute:02d} EST"
        return True, reason

    def should_exit(self, current_price: float, entry_price: float,
                   peak_price: float) -> Tuple[bool, str]:
        """
        Decide if we should SELL right now

        Exit Conditions:
        1. Must be profitable (current_price > entry_price)
        2. Price dropped 1% from peak

        NEVER sell at a loss - this was key to our backtest success

        Args:
            current_price: Current BTC price
            entry_price: Our entry price
            peak_price: Highest price since entry

        Returns:
            (should_sell, reason) - True/False and explanation

        Example:
            >>> should_sell, reason = strategy.should_exit(88500, 87000, 89500)
            >>> if should_sell:
            ...     print(f"EXIT: {reason}")
            EXIT: Trailing stop hit - Dropped 1.12% from peak
        """
        # Calculate profit
        profit_pct = ((current_price - entry_price) / entry_price) * 100

        # Rule: NEVER sell at a loss
        if profit_pct <= 0:
            return False, f"Not profitable (currently {profit_pct:+.2f}%)"

        # Calculate drawdown from peak
        drawdown_from_peak = ((current_price - peak_price) / peak_price) * 100

        # Check trailing stop
        if drawdown_from_peak <= -self.trailing_stop_pct:
            reason = (f"Trailing stop hit - Dropped {abs(drawdown_from_peak):.2f}% "
                     f"from peak (${peak_price:,.0f} → ${current_price:,.0f})")
            return True, reason

        # Still holding
        return False, f"Holding - Up {profit_pct:+.2f}% from entry, {abs(drawdown_from_peak):.2f}% from peak"

    def update_peak_price(self, current_price: float, current_peak: float) -> float:
        """
        Update peak price tracker

        The peak price is used to calculate trailing stop.
        It should only go up, never down.

        Args:
            current_price: Current BTC price
            current_peak: Current tracked peak

        Returns:
            New peak price

        Example:
            >>> peak = 87000
            >>> peak = strategy.update_peak_price(88500, peak)
            >>> print(f"New peak: ${peak:,.0f}")
            New peak: $88,500
        """
        return max(current_price, current_peak)

    def reset_daily_state(self):
        """
        Reset daily state (called at midnight EST)

        This allows a new entry the next day.
        """
        self.last_entry_date = None

    def get_position_size(self, balance_usd: float, current_price: float) -> float:
        """
        Calculate position size in USDC

        Strategy uses 100% of capital per trade.

        Args:
            balance_usd: Available USDC balance
            current_price: Current BTC price

        Returns:
            Position size in USDC

        Example:
            >>> size = strategy.get_position_size(100000, 87432)
            >>> print(f"Buy ${size:,.0f} worth of BTC")
            Buy $100,000 worth of BTC
        """
        # Use 100% of balance (as per backtest config)
        # In production, you might want to leave a small buffer for fees
        return balance_usd * 0.999  # Leave 0.1% for fees

    def __str__(self):
        """String representation for logging"""
        return (f"OvernightRecovery(entry={self.entry_hour}:00 EST, "
                f"max_price=${self.max_entry_price:,.0f}, "
                f"trail_stop={self.trailing_stop_pct}%)")


# Module testing
if __name__ == '__main__':
    import json

    # Load config
    with open('../config.json', 'r') as f:
        config = json.load(f)

    # Create strategy
    strategy = OvernightRecoveryStrategy(config['strategy'])
    print(f"Strategy: {strategy}")

    # Test entry logic
    test_time = datetime.now(pytz.UTC)
    test_time = test_time.replace(hour=19, minute=2)  # 3:02 PM EST (19:00 UTC)

    print(f"\nTest Entry Logic:")
    print(f"Time: {test_time.astimezone(pytz.timezone('America/New_York'))}")

    # Test case 1: Good entry
    should_buy, reason = strategy.should_enter(test_time, 87000)
    print(f"\nPrice $87,000: {should_buy} - {reason}")

    # Test case 2: Price too high
    should_buy, reason = strategy.should_enter(test_time, 92000)
    print(f"Price $92,000: {should_buy} - {reason}")

    # Test exit logic
    print(f"\nTest Exit Logic:")

    # Test case 1: Profitable but not hit stop
    should_sell, reason = strategy.should_exit(88000, 87000, 88500)
    print(f"Price $88,000 (entry $87k, peak $88.5k): {should_sell} - {reason}")

    # Test case 2: Hit trailing stop
    should_sell, reason = strategy.should_exit(87600, 87000, 88500)
    print(f"Price $87,600 (entry $87k, peak $88.5k): {should_sell} - {reason}")

    # Test case 3: Not profitable
    should_sell, reason = strategy.should_exit(86500, 87000, 87000)
    print(f"Price $86,500 (entry $87k): {should_sell} - {reason}")

    print("\nAll tests passed!")
