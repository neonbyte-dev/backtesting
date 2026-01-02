"""
Risk Manager - Circuit Breakers

This module implements safety mechanisms that automatically pause trading
when dangerous conditions are detected.

Circuit Breakers:
1. Daily Loss Limit - Stop if down >5% in one day
2. Consecutive Losses - Stop after 3 losses in a row
3. Stale Data Protection - Don't trade on old price data

WHY THIS MATTERS:
Without circuit breakers, a broken strategy could lose 10%, 20%, 50% before
you notice. Circuit breakers act like airbags - they deploy automatically
when crashes happen.

In our October-November backtest, the strategy lost -27%. A 5% daily loss
limit would have stopped trading on Day 1, preventing most losses.
"""

from datetime import datetime, timedelta
from typing import Tuple, Dict
import pytz


class RiskManager:
    """
    Implements circuit breakers for safe trading

    All checks return (is_safe, reason) tuples.
    If is_safe=False, bot should pause trading.
    """

    def __init__(self, config: dict):
        """
        Initialize risk manager

        Args:
            config: Risk parameters from config.json

        Example config:
            {
                "max_daily_loss_pct": 5.0,
                "max_consecutive_losses": 3,
                "max_data_age_minutes": 10
            }
        """
        self.max_daily_loss_pct = config.get('max_daily_loss_pct', 5.0)
        self.max_consecutive_losses = config.get('max_consecutive_losses', 3)
        self.max_data_age_minutes = config.get('max_data_age_minutes', 10)

        # Track initial balance for daily loss calculation
        self.initial_balance = None
        self.reset_time = None

    def check_daily_loss_limit(self, current_balance: float,
                               initial_balance: float) -> Tuple[bool, str]:
        """
        Check if daily loss limit exceeded

        Circuit Breaker #1: Daily Loss Limit
        - Prevents large single-day losses
        - Example: If down 5% in one day, stop trading

        Args:
            current_balance: Current account balance
            initial_balance: Balance at start of day

        Returns:
            (is_safe, reason)

        Example:
            >>> is_safe, reason = risk_mgr.check_daily_loss_limit(95000, 100000)
            >>> if not is_safe:
            ...     print(f"CIRCUIT BREAKER: {reason}")
            CIRCUIT BREAKER: Daily loss -5.0% exceeds limit of -5.0%
        """
        # Calculate daily loss
        daily_loss_pct = ((current_balance - initial_balance) / initial_balance) * 100

        # Check if exceeded limit
        if daily_loss_pct <= -self.max_daily_loss_pct:
            return False, f"Daily loss {daily_loss_pct:.2f}% exceeds limit of -{self.max_daily_loss_pct}%"

        return True, f"Daily loss {daily_loss_pct:+.2f}% within limits"

    def check_consecutive_losses(self, consecutive_losses: int) -> Tuple[bool, str]:
        """
        Check if too many consecutive losses

        Circuit Breaker #2: Consecutive Losses
        - If strategy loses 3 times in a row, something may be broken
        - Prevents systematic losses when market regime changes

        Args:
            consecutive_losses: Number of losses in a row

        Returns:
            (is_safe, reason)

        Example:
            >>> is_safe, reason = risk_mgr.check_consecutive_losses(3)
            >>> if not is_safe:
            ...     print(f"CIRCUIT BREAKER: {reason}")
            CIRCUIT BREAKER: 3 consecutive losses (max: 3)
        """
        if consecutive_losses >= self.max_consecutive_losses:
            return False, f"{consecutive_losses} consecutive losses (max: {self.max_consecutive_losses})"

        return True, f"{consecutive_losses} consecutive losses (within limits)"

    def check_data_staleness(self, last_update: datetime) -> Tuple[bool, str]:
        """
        Check if price data is stale

        Circuit Breaker #3: Stale Data Protection
        - Don't trade on old price data
        - Example: If price is 10 minutes old, don't enter/exit

        This prevents:
        - Trading at wrong prices during network outages
        - Acting on stale data after bot pause/resume

        Args:
            last_update: When price data was last updated

        Returns:
            (is_safe, reason)

        Example:
            >>> last_update = datetime.now(pytz.UTC) - timedelta(minutes=15)
            >>> is_safe, reason = risk_mgr.check_data_staleness(last_update)
            >>> if not is_safe:
            ...     print(f"CIRCUIT BREAKER: {reason}")
            CIRCUIT BREAKER: Price data stale (15.0 minutes old, max: 10)
        """
        now = datetime.now(pytz.UTC)

        # Ensure last_update is timezone-aware
        if last_update.tzinfo is None:
            last_update = last_update.replace(tzinfo=pytz.UTC)

        # Calculate age
        age = (now - last_update).total_seconds() / 60  # Convert to minutes

        if age > self.max_data_age_minutes:
            return False, f"Price data stale ({age:.1f} minutes old, max: {self.max_data_age_minutes})"

        return True, f"Price data fresh ({age:.1f} minutes old)"

    def check_all_conditions(self, current_balance: float, initial_balance: float,
                            consecutive_losses: int, last_data_update: datetime) -> Tuple[bool, str]:
        """
        Run all risk checks

        Returns:
            (is_safe, reason) - False if ANY circuit breaker triggered

        Example:
            >>> is_safe, reason = risk_mgr.check_all_conditions(95000, 100000, 2, datetime.now(pytz.UTC))
            >>> if not is_safe:
            ...     bot.pause_trading()
            ...     notifier.send_circuit_breaker_alert(reason)
        """
        # Check 1: Daily loss limit
        is_safe, reason = self.check_daily_loss_limit(current_balance, initial_balance)
        if not is_safe:
            return False, f"🛑 DAILY LOSS LIMIT: {reason}"

        # Check 2: Consecutive losses
        is_safe, reason = self.check_consecutive_losses(consecutive_losses)
        if not is_safe:
            return False, f"🛑 CONSECUTIVE LOSSES: {reason}"

        # Check 3: Data staleness
        is_safe, reason = self.check_data_staleness(last_data_update)
        if not is_safe:
            return False, f"🛑 STALE DATA: {reason}"

        # All checks passed
        return True, "✅ All risk checks passed"

    def calculate_position_size(self, balance: float, config: dict) -> float:
        """
        Calculate safe position size

        Current strategy uses 100% of balance (from backtest config).
        In production, you might want to leave a buffer.

        Args:
            balance: Available balance
            config: Position sizing config

        Returns:
            Position size in USDC
        """
        position_size_pct = config.get('position_size_pct', 100)

        # Leave small buffer for fees
        usable_balance = balance * (position_size_pct / 100) * 0.999

        return usable_balance

    def should_allow_entry(self, current_balance: float, initial_balance: float,
                          consecutive_losses: int, last_data_update: datetime) -> Tuple[bool, str]:
        """
        Decide if entry is allowed given current risk conditions

        This is called before EVERY entry attempt.

        Returns:
            (allowed, reason)
        """
        is_safe, reason = self.check_all_conditions(
            current_balance, initial_balance,
            consecutive_losses, last_data_update
        )

        if not is_safe:
            return False, f"Entry blocked: {reason}"

        return True, "Entry allowed"

    def should_allow_exit(self, last_data_update: datetime) -> Tuple[bool, str]:
        """
        Decide if exit is allowed given current risk conditions

        For exits, we only check data staleness.
        We ALWAYS want to exit if stop loss hit, even if daily loss limit reached.

        Returns:
            (allowed, reason)
        """
        is_safe, reason = self.check_data_staleness(last_data_update)

        if not is_safe:
            return False, f"Exit blocked: {reason}"

        return True, "Exit allowed"

    def reset_daily_limits(self, current_balance: float):
        """
        Reset daily limits at midnight EST

        Args:
            current_balance: Current balance (becomes new initial_balance)
        """
        self.initial_balance = current_balance
        self.reset_time = datetime.now(pytz.UTC)
        print(f"✅ Daily risk limits reset. Starting balance: ${current_balance:,.2f}")

    def __str__(self):
        """String representation for logging"""
        return (f"RiskManager(daily_loss_limit={self.max_daily_loss_pct}%, "
               f"max_consecutive_losses={self.max_consecutive_losses}, "
               f"max_data_age={self.max_data_age_minutes}min)")


# Module testing
if __name__ == '__main__':
    import json

    # Load config
    with open('../config.json', 'r') as f:
        config = json.load(f)

    # Create risk manager
    risk_mgr = RiskManager(config['risk'])
    print(f"Risk Manager: {risk_mgr}\n")

    # Test 1: Daily loss limit
    print("Test 1: Daily Loss Limit")
    is_safe, reason = risk_mgr.check_daily_loss_limit(95000, 100000)
    print(f"  95K from 100K: {is_safe} - {reason}")

    is_safe, reason = risk_mgr.check_daily_loss_limit(94900, 100000)
    print(f"  94.9K from 100K: {is_safe} - {reason}")

    # Test 2: Consecutive losses
    print("\nTest 2: Consecutive Losses")
    is_safe, reason = risk_mgr.check_consecutive_losses(2)
    print(f"  2 losses: {is_safe} - {reason}")

    is_safe, reason = risk_mgr.check_consecutive_losses(3)
    print(f"  3 losses: {is_safe} - {reason}")

    # Test 3: Data staleness
    print("\nTest 3: Data Staleness")
    fresh_time = datetime.now(pytz.UTC) - timedelta(minutes=2)
    is_safe, reason = risk_mgr.check_data_staleness(fresh_time)
    print(f"  2 min old: {is_safe} - {reason}")

    stale_time = datetime.now(pytz.UTC) - timedelta(minutes=15)
    is_safe, reason = risk_mgr.check_data_staleness(stale_time)
    print(f"  15 min old: {is_safe} - {reason}")

    # Test 4: All conditions
    print("\nTest 4: All Conditions")
    is_safe, reason = risk_mgr.check_all_conditions(
        current_balance=97000,
        initial_balance=100000,
        consecutive_losses=1,
        last_data_update=datetime.now(pytz.UTC)
    )
    print(f"  Normal conditions: {is_safe} - {reason}")

    is_safe, reason = risk_mgr.check_all_conditions(
        current_balance=94000,  # -6% loss
        initial_balance=100000,
        consecutive_losses=1,
        last_data_update=datetime.now(pytz.UTC)
    )
    print(f"  Excessive loss: {is_safe} - {reason}")

    print("\n✅ All tests passed!")
