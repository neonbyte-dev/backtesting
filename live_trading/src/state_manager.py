"""
Position State Manager

This module handles saving and loading position state to disk.

WHY THIS MATTERS:
If the bot crashes or restarts, it MUST remember:
- Are we in a position?
- What was our entry price?
- What's the peak price we've seen?

Without this, the bot could:
- Buy more BTC when it already owns BTC
- Forget the entry price and sell at the wrong time
- Lose track of the trailing stop

The state is saved to JSON files:
- state.json: Current state
- state_backup.json: Previous state (in case state.json corrupts)
"""

import json
import os
import shutil
from datetime import datetime
from typing import Optional, Dict
from pathlib import Path


class StateManager:
    """
    Manages bot state persistence to disk

    All state changes are immediately saved to disk.
    On startup, state is loaded from disk.
    """

    def __init__(self, state_dir: str = './state'):
        """
        Initialize state manager

        Args:
            state_dir: Directory to store state files
        """
        self.state_dir = Path(state_dir)
        self.state_file = self.state_dir / 'state.json'
        self.backup_file = self.state_dir / 'state_backup.json'

        # Create directory if doesn't exist
        self.state_dir.mkdir(parents=True, exist_ok=True)

        # Current state (in memory)
        self.state = {
            'in_position': False,
            'entry_time': None,
            'entry_price': None,
            'position_size_btc': None,
            'position_size_usd': None,
            'peak_price': None,
            'last_updated': None,
            'daily_pnl': 0.0,
            'consecutive_losses': 0,
            'last_trade_result': None
        }

    def load_state(self) -> Dict:
        """
        Load state from disk

        If state.json exists, load it.
        If state.json is corrupt, try state_backup.json.
        If both fail, start with empty state.

        Returns:
            State dictionary

        Example:
            >>> manager = StateManager()
            >>> state = manager.load_state()
            >>> if state['in_position']:
            ...     print(f"Resuming position from ${state['entry_price']}")
        """
        # Try loading main state file
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    self.state = json.load(f)
                print(f"✅ State loaded from {self.state_file}")
                return self.state
            except json.JSONDecodeError as e:
                print(f"⚠️  Corrupt state file: {e}")
                # Try backup
                if self.backup_file.exists():
                    try:
                        with open(self.backup_file, 'r') as f:
                            self.state = json.load(f)
                        print(f"✅ State recovered from backup")
                        # Save as main state
                        self.save_state()
                        return self.state
                    except:
                        print(f"⚠️  Backup also corrupt, starting fresh")

        # No valid state found
        print(f"ℹ️  No state found, starting fresh")
        return self.state

    def save_state(self):
        """
        Save current state to disk

        Process:
        1. Backup current state.json to state_backup.json
        2. Write new state to state.json
        3. Update last_updated timestamp

        This is called after every state change.
        """
        try:
            # Update timestamp
            self.state['last_updated'] = datetime.utcnow().isoformat()

            # Backup existing state file
            if self.state_file.exists():
                shutil.copy(self.state_file, self.backup_file)

            # Write new state
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)

        except Exception as e:
            print(f"❌ ERROR saving state: {e}")
            raise

    def enter_position(self, entry_time: datetime, entry_price: float,
                      size_btc: float, size_usd: float):
        """
        Record new position entry

        Args:
            entry_time: When we entered
            entry_price: Price we bought at
            size_btc: How much BTC we bought
            size_usd: How much USD we spent
        """
        self.state['in_position'] = True
        self.state['entry_time'] = entry_time.isoformat()
        self.state['entry_price'] = entry_price
        self.state['position_size_btc'] = size_btc
        self.state['position_size_usd'] = size_usd
        self.state['peak_price'] = entry_price  # Initialize peak at entry

        self.save_state()
        print(f"✅ Position entered: {size_btc:.4f} BTC @ ${entry_price:,.2f}")

    def update_peak_price(self, new_price: float):
        """
        Update peak price if new high reached

        Args:
            new_price: Current price to check

        Returns:
            Current peak price
        """
        if not self.state['in_position']:
            return None

        if new_price > self.state['peak_price']:
            self.state['peak_price'] = new_price
            self.save_state()

        return self.state['peak_price']

    def exit_position(self, exit_time: datetime, exit_price: float, profit_pct: float):
        """
        Record position exit

        Args:
            exit_time: When we exited
            exit_price: Price we sold at
            profit_pct: Profit percentage
        """
        # Calculate PnL
        pnl_usd = (exit_price - self.state['entry_price']) * self.state['position_size_btc']

        # Update daily PnL
        self.state['daily_pnl'] += pnl_usd

        # Update consecutive losses
        if profit_pct < 0:
            self.state['consecutive_losses'] += 1
            self.state['last_trade_result'] = 'loss'
        else:
            self.state['consecutive_losses'] = 0
            self.state['last_trade_result'] = 'win'

        # Clear position
        self.state['in_position'] = False
        self.state['entry_time'] = None
        self.state['entry_price'] = None
        self.state['position_size_btc'] = None
        self.state['position_size_usd'] = None
        self.state['peak_price'] = None

        self.save_state()
        print(f"✅ Position exited: {profit_pct:+.2f}% (${pnl_usd:+,.2f})")

    def reset_daily_stats(self):
        """
        Reset daily statistics (call at midnight EST)
        """
        self.state['daily_pnl'] = 0.0
        self.save_state()
        print(f"✅ Daily stats reset")

    def get_position_details(self) -> Optional[Dict]:
        """
        Get current position details

        Returns:
            Position dict if in position, None otherwise

        Example:
            >>> pos = manager.get_position_details()
            >>> if pos:
            ...     print(f"Position: {pos['size_btc']} BTC @ ${pos['entry_price']}")
        """
        if not self.state['in_position']:
            return None

        return {
            'in_position': True,
            'entry_time': self.state['entry_time'],
            'entry_price': self.state['entry_price'],
            'size_btc': self.state['position_size_btc'],
            'size_usd': self.state['position_size_usd'],
            'peak_price': self.state['peak_price']
        }

    def get_risk_metrics(self) -> Dict:
        """
        Get risk metrics for circuit breakers

        Returns:
            {
                'daily_pnl': float,
                'consecutive_losses': int,
                'last_trade_result': str
            }
        """
        return {
            'daily_pnl': self.state['daily_pnl'],
            'consecutive_losses': self.state['consecutive_losses'],
            'last_trade_result': self.state['last_trade_result']
        }

    def is_in_position(self) -> bool:
        """Check if currently in a position"""
        return self.state['in_position']

    def __str__(self):
        """String representation for logging"""
        if self.state['in_position']:
            return (f"State(IN_POSITION: {self.state['position_size_btc']:.4f} BTC "
                   f"@ ${self.state['entry_price']:,.0f}, peak=${self.state['peak_price']:,.0f})")
        else:
            return "State(NO_POSITION)"


# Module testing
if __name__ == '__main__':
    import tempfile

    # Create temporary state directory for testing
    with tempfile.TemporaryDirectory() as tmpdir:
        print("Testing StateManager...")

        # Create manager
        manager = StateManager(tmpdir)
        print(f"Initial state: {manager}")

        # Test entering position
        now = datetime.utcnow()
        manager.enter_position(now, 87432.50, 1.1435, 100000)
        print(f"After entry: {manager}")

        # Test updating peak
        manager.update_peak_price(88500)
        print(f"After peak update: {manager}")

        # Test persistence (create new manager, should load state)
        manager2 = StateManager(tmpdir)
        manager2.load_state()
        print(f"New manager loaded state: {manager2}")

        assert manager2.state['in_position'] == True
        assert manager2.state['peak_price'] == 88500

        # Test exiting position
        manager2.exit_position(datetime.utcnow(), 89000, 1.8)
        print(f"After exit: {manager2}")

        assert manager2.state['in_position'] == False

        print("\n✅ All tests passed!")
