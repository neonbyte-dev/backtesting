"""
Multi-Strategy Position State Manager

This module handles saving and loading position state to disk for MULTIPLE strategies.

Each strategy has its own:
- Position tracking (entry price, size, peak price)
- Capital allocation (fixed USD amount)
- Enabled/disabled status

State is persisted to JSON so the bot can resume after restart.
"""

import json
import os
import shutil
from datetime import datetime
from typing import Optional, Dict, List
from pathlib import Path


class StateManager:
    """
    Manages bot state persistence to disk for multiple strategies

    Each strategy operates independently with its own capital pool.
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
            # Per-strategy positions and config
            'strategies': {},
            # Global stats
            'daily_pnl': 0.0,
            'last_updated': None
        }

    def _get_default_strategy_state(self) -> Dict:
        """Get default state for a new strategy"""
        return {
            'enabled': False,
            'allocated_capital_usd': 0,
            'enabled_since': None,          # When strategy was enabled
            'trade_count': 0,               # Total trades taken
            'total_realized_pnl': 0.0,      # Sum of all realized P&L
            'in_position': False,
            'entry_time': None,
            'entry_price': None,
            'position_size_btc': None,
            'position_size_usd': None,
            'peak_price': None,
            'consecutive_losses': 0,
            'last_trade_result': None,
            'last_trade_time': None,            # When last trade was triggered (persists after exit)
            'last_signal_time': None,           # When entry conditions were last TRUE (backtest-style)
            'last_entry_check_time': None,
            'last_entry_check_result': None,
            'last_entry_check_reason': None,
            'trade_history': []                 # List of completed trades
        }

    def load_state(self) -> Dict:
        """
        Load state from disk

        Returns:
            State dictionary
        """
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    self.state = json.load(f)
                print(f"State loaded from {self.state_file}")
                return self.state
            except json.JSONDecodeError as e:
                print(f"Corrupt state file: {e}")
                if self.backup_file.exists():
                    try:
                        with open(self.backup_file, 'r') as f:
                            self.state = json.load(f)
                        print(f"State recovered from backup")
                        self.save_state()
                        return self.state
                    except:
                        print(f"Backup also corrupt, starting fresh")

        print(f"No state found, starting fresh")
        return self.state

    def save_state(self):
        """Save current state to disk"""
        try:
            self.state['last_updated'] = datetime.utcnow().isoformat()

            if self.state_file.exists():
                shutil.copy(self.state_file, self.backup_file)

            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)

        except Exception as e:
            print(f"ERROR saving state: {e}")
            raise

    def ensure_strategy_exists(self, strategy_name: str):
        """Ensure strategy exists in state"""
        if 'strategies' not in self.state:
            self.state['strategies'] = {}
        if strategy_name not in self.state['strategies']:
            self.state['strategies'][strategy_name] = self._get_default_strategy_state()

    def enable_strategy(self, strategy_name: str, capital_usd: float):
        """
        Enable a strategy with allocated capital

        Args:
            strategy_name: Name of the strategy
            capital_usd: USD amount to allocate
        """
        self.ensure_strategy_exists(strategy_name)
        s = self.state['strategies'][strategy_name]
        s['enabled'] = True
        s['allocated_capital_usd'] = capital_usd
        # Only set enabled_since if not already set (preserve original start date)
        if not s.get('enabled_since'):
            s['enabled_since'] = datetime.utcnow().isoformat()
        self.save_state()
        print(f"Strategy '{strategy_name}' enabled with ${capital_usd:,.0f}")

    def disable_strategy(self, strategy_name: str):
        """
        Disable a strategy

        Args:
            strategy_name: Name of the strategy
        """
        self.ensure_strategy_exists(strategy_name)
        self.state['strategies'][strategy_name]['enabled'] = False
        self.save_state()
        print(f"Strategy '{strategy_name}' disabled")

    def is_strategy_enabled(self, strategy_name: str) -> bool:
        """Check if strategy is enabled"""
        self.ensure_strategy_exists(strategy_name)
        return self.state['strategies'][strategy_name]['enabled']

    def get_strategy_capital(self, strategy_name: str) -> float:
        """Get allocated capital for a strategy"""
        self.ensure_strategy_exists(strategy_name)
        return self.state['strategies'][strategy_name]['allocated_capital_usd']

    def get_enabled_strategies(self) -> List[str]:
        """Get list of enabled strategy names"""
        if 'strategies' not in self.state:
            return []
        return [name for name, s in self.state['strategies'].items() if s.get('enabled', False)]

    def get_total_allocated_capital(self) -> float:
        """Get total capital allocated across all strategies"""
        if 'strategies' not in self.state:
            return 0
        return sum(s.get('allocated_capital_usd', 0) for s in self.state['strategies'].values())

    def enter_position(self, strategy_name: str, entry_time: datetime, entry_price: float,
                       size_btc: float, size_usd: float):
        """
        Record new position entry for a strategy

        Args:
            strategy_name: Which strategy is entering
            entry_time: When we entered
            entry_price: Price we bought at
            size_btc: How much BTC we bought
            size_usd: How much USD we spent
        """
        self.ensure_strategy_exists(strategy_name)
        s = self.state['strategies'][strategy_name]
        s['in_position'] = True
        s['entry_time'] = entry_time.isoformat()
        s['last_trade_time'] = entry_time.isoformat()  # Persists after exit
        s['entry_price'] = entry_price
        s['position_size_btc'] = size_btc
        s['position_size_usd'] = size_usd
        s['peak_price'] = entry_price

        self.save_state()
        print(f"[{strategy_name}] Position entered: {size_btc:.4f} BTC @ ${entry_price:,.2f}")

    def update_peak_price(self, strategy_name: str, new_price: float) -> Optional[float]:
        """
        Update peak price if new high reached

        Args:
            strategy_name: Which strategy's position
            new_price: Current price to check

        Returns:
            Current peak price
        """
        self.ensure_strategy_exists(strategy_name)
        s = self.state['strategies'][strategy_name]

        if not s['in_position']:
            return None

        if new_price > s['peak_price']:
            s['peak_price'] = new_price
            self.save_state()

        return s['peak_price']

    def exit_position(self, strategy_name: str, exit_time: datetime, exit_price: float, profit_pct: float):
        """
        Record position exit for a strategy

        Args:
            strategy_name: Which strategy is exiting
            exit_time: When we exited
            exit_price: Price we sold at
            profit_pct: Profit percentage
        """
        self.ensure_strategy_exists(strategy_name)
        s = self.state['strategies'][strategy_name]

        # Calculate PnL
        pnl_usd = (exit_price - s['entry_price']) * s['position_size_btc']

        # Update daily PnL (global)
        self.state['daily_pnl'] += pnl_usd

        # Update strategy stats
        s['trade_count'] = s.get('trade_count', 0) + 1
        s['total_realized_pnl'] = s.get('total_realized_pnl', 0) + pnl_usd

        # Update consecutive losses
        if profit_pct < 0:
            s['consecutive_losses'] += 1
            s['last_trade_result'] = 'loss'
        else:
            s['consecutive_losses'] = 0
            s['last_trade_result'] = 'win'

        # Record trade in history
        if 'trade_history' not in s:
            s['trade_history'] = []
        s['trade_history'].append({
            'entry_time': s['entry_time'],
            'exit_time': exit_time.isoformat(),
            'entry_price': s['entry_price'],
            'exit_price': exit_price,
            'size': s['position_size_btc'],
            'profit_pct': round(profit_pct, 2),
            'profit_usd': round(pnl_usd, 2),
            'result': 'win' if profit_pct >= 0 else 'loss'
        })

        # Clear position
        s['in_position'] = False
        s['entry_time'] = None
        s['entry_price'] = None
        s['position_size_btc'] = None
        s['position_size_usd'] = None
        s['peak_price'] = None

        self.save_state()
        print(f"[{strategy_name}] Position exited: {profit_pct:+.2f}% (${pnl_usd:+,.2f})")

    def reset_daily_stats(self):
        """Reset daily statistics (call at midnight EST)"""
        self.state['daily_pnl'] = 0.0
        self.save_state()
        print(f"Daily stats reset")

    def record_entry_check(self, strategy_name: str, check_time: datetime, result: bool, reason: str):
        """
        Record the result of an entry check for status display

        Args:
            strategy_name: Which strategy checked entry
            check_time: When the check was performed
            result: True if entry was executed, False if skipped
            reason: Human-readable reason
        """
        self.ensure_strategy_exists(strategy_name)
        s = self.state['strategies'][strategy_name]
        s['last_entry_check_time'] = check_time.isoformat()
        s['last_entry_check_result'] = result
        s['last_entry_check_reason'] = reason

        # Track when conditions were last TRUE (backtest-style signal)
        if result:
            s['last_signal_time'] = check_time.isoformat()

        self.save_state()

    def get_last_entry_check(self, strategy_name: str = None) -> Optional[Dict]:
        """
        Get the last entry check result for status display

        Args:
            strategy_name: If provided, get for specific strategy.
                          If None, returns first found (legacy support).
        """
        if strategy_name:
            self.ensure_strategy_exists(strategy_name)
            s = self.state['strategies'][strategy_name]
            if not s.get('last_entry_check_time'):
                return None
            return {
                'time': s['last_entry_check_time'],
                'result': s['last_entry_check_result'],
                'reason': s['last_entry_check_reason']
            }

        # Legacy: return first strategy's check
        for name, s in self.state.get('strategies', {}).items():
            if s.get('last_entry_check_time'):
                return {
                    'time': s['last_entry_check_time'],
                    'result': s['last_entry_check_result'],
                    'reason': s['last_entry_check_reason']
                }
        return None

    def get_position_details(self, strategy_name: str = None) -> Optional[Dict]:
        """
        Get current position details

        Args:
            strategy_name: If provided, get for specific strategy.
                          If None, returns first position found (legacy support).
        """
        if strategy_name:
            self.ensure_strategy_exists(strategy_name)
            s = self.state['strategies'][strategy_name]
            if not s['in_position']:
                return None
            return {
                'strategy': strategy_name,
                'in_position': True,
                'entry_time': s['entry_time'],
                'entry_price': s['entry_price'],
                'size_btc': s['position_size_btc'],
                'size_usd': s['position_size_usd'],
                'peak_price': s['peak_price']
            }

        # Legacy: return first position found
        for name, s in self.state.get('strategies', {}).items():
            if s.get('in_position'):
                return {
                    'strategy': name,
                    'in_position': True,
                    'entry_time': s['entry_time'],
                    'entry_price': s['entry_price'],
                    'size_btc': s['position_size_btc'],
                    'size_usd': s['position_size_usd'],
                    'peak_price': s['peak_price']
                }
        return None

    def get_all_positions(self) -> List[Dict]:
        """Get all open positions across all strategies"""
        positions = []
        for name, s in self.state.get('strategies', {}).items():
            if s.get('in_position'):
                positions.append({
                    'strategy': name,
                    'entry_time': s['entry_time'],
                    'entry_price': s['entry_price'],
                    'size_btc': s['position_size_btc'],
                    'size_usd': s['position_size_usd'],
                    'peak_price': s['peak_price']
                })
        return positions

    def get_strategy_state(self, strategy_name: str) -> Dict:
        """Get full state for a specific strategy"""
        self.ensure_strategy_exists(strategy_name)
        return self.state['strategies'][strategy_name].copy()

    def get_trade_history(self, strategy_name: str = None, limit: int = 20) -> List[Dict]:
        """
        Get trade history, newest first

        Args:
            strategy_name: If provided, get for specific strategy only.
                          If None, get all trades across all strategies.
            limit: Max number of trades to return

        Returns:
            List of trade dicts with strategy name included
        """
        trades = []
        if strategy_name:
            self.ensure_strategy_exists(strategy_name)
            history = self.state['strategies'][strategy_name].get('trade_history', [])
            for t in history:
                trade = t.copy()
                trade['strategy'] = strategy_name
                trades.append(trade)
        else:
            for name, s in self.state.get('strategies', {}).items():
                for t in s.get('trade_history', []):
                    trade = t.copy()
                    trade['strategy'] = name
                    trades.append(trade)

        # Sort by exit time, newest first
        trades.sort(key=lambda t: t.get('exit_time', ''), reverse=True)
        return trades[:limit]

    def get_all_strategies_summary(self) -> List[Dict]:
        """Get summary of all strategies"""
        summaries = []
        for name, s in self.state.get('strategies', {}).items():
            summaries.append({
                'name': name,
                'enabled': s.get('enabled', False),
                'allocated_capital_usd': s.get('allocated_capital_usd', 0),
                'in_position': s.get('in_position', False),
                'entry_price': s.get('entry_price'),
                'position_size_btc': s.get('position_size_btc')
            })
        return summaries

    def get_risk_metrics(self, strategy_name: str = None) -> Dict:
        """
        Get risk metrics for circuit breakers

        Args:
            strategy_name: If provided, get for specific strategy
        """
        result = {
            'daily_pnl': self.state.get('daily_pnl', 0)
        }

        if strategy_name:
            self.ensure_strategy_exists(strategy_name)
            s = self.state['strategies'][strategy_name]
            result['consecutive_losses'] = s.get('consecutive_losses', 0)
            result['last_trade_result'] = s.get('last_trade_result')
        else:
            # Sum across all strategies
            total_losses = sum(
                s.get('consecutive_losses', 0)
                for s in self.state.get('strategies', {}).values()
            )
            result['consecutive_losses'] = total_losses

        return result

    def is_in_position(self, strategy_name: str = None) -> bool:
        """
        Check if currently in a position

        Args:
            strategy_name: If provided, check specific strategy.
                          If None, check if ANY strategy is in position.
        """
        if strategy_name:
            self.ensure_strategy_exists(strategy_name)
            return self.state['strategies'][strategy_name]['in_position']

        # Check any strategy
        for s in self.state.get('strategies', {}).values():
            if s.get('in_position'):
                return True
        return False

    def __str__(self):
        """String representation for logging"""
        positions = self.get_all_positions()
        if positions:
            pos_strs = [f"{p['strategy']}: {p['size_btc']:.4f} BTC @ ${p['entry_price']:,.0f}"
                        for p in positions]
            return f"State({len(positions)} positions: {', '.join(pos_strs)})"
        else:
            enabled = self.get_enabled_strategies()
            if enabled:
                return f"State(NO_POSITIONS, {len(enabled)} strategies enabled)"
            return "State(NO_POSITIONS, no strategies enabled)"


# Module testing
if __name__ == '__main__':
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        print("Testing Multi-Strategy StateManager...")

        manager = StateManager(tmpdir)
        print(f"Initial state: {manager}")

        # Enable strategies with capital
        manager.enable_strategy('overnight', 50000)
        manager.enable_strategy('oi', 50000)
        print(f"After enabling: {manager}")
        print(f"Total allocated: ${manager.get_total_allocated_capital():,.0f}")

        # Enter position for OI strategy
        now = datetime.utcnow()
        manager.enter_position('oi', now, 90000, 0.5, 45000)
        print(f"After OI entry: {manager}")

        # Enter position for overnight strategy
        manager.enter_position('overnight', now, 90500, 0.5, 45250)
        print(f"After overnight entry: {manager}")

        # Check positions
        all_pos = manager.get_all_positions()
        print(f"All positions: {all_pos}")

        # Exit OI position
        manager.exit_position('oi', datetime.utcnow(), 91000, 1.11)
        print(f"After OI exit: {manager}")

        # Disable overnight
        manager.disable_strategy('overnight')
        print(f"After disabling overnight: {manager}")

        print("\nAll tests passed!")
