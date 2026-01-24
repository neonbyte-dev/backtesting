"""
HyperLiquid Exchange Client

This module handles all API interactions with HyperLiquid exchange
using the official hyperliquid-python-sdk.

The SDK handles:
- EIP-712 typed data signing (blockchain authentication)
- Proper request formatting
- Connection management

Error handling:
- Automatic retries with exponential backoff
- Detailed error logging
"""

import time
from typing import Dict, Optional, Tuple
from eth_account import Account

from hyperliquid.info import Info
from hyperliquid.exchange import Exchange
from hyperliquid.utils import constants


class HyperLiquidClient:
    """
    Client for interacting with HyperLiquid API using the official SDK.

    Supports both testnet and mainnet environments.
    All methods include error handling and retry logic.
    """

    def __init__(self, api_key: str, api_secret: str, testnet: bool = True,
                 retry_attempts: int = 3, timeout: int = 30):
        """
        Initialize HyperLiquid client

        Args:
            api_key: Your wallet address (0x...)
            api_secret: Your API wallet private key (0x...)
            testnet: True for testnet, False for mainnet
            retry_attempts: Number of retries on failure
            timeout: Request timeout in seconds
        """
        self.wallet_address = api_key  # Renamed for clarity
        self.private_key = api_secret  # Renamed for clarity
        self.retry_attempts = retry_attempts
        self.timeout = timeout
        self.testnet = testnet

        # Set API URL based on environment
        if testnet:
            self.api_url = constants.TESTNET_API_URL
        else:
            self.api_url = constants.MAINNET_API_URL

        # Initialize SDK clients
        # Info client - for read-only operations (no signing needed)
        self.info = Info(self.api_url, skip_ws=True)

        # Exchange client - for trading (requires signing)
        # Create account from private key for signing
        self.account = Account.from_key(self.private_key)
        self.exchange = Exchange(
            self.account,
            self.api_url,
            account_address=self.wallet_address
        )

    def _retry_operation(self, operation, operation_name: str):
        """
        Retry an operation with exponential backoff

        Special handling for rate limits (429 errors):
        - Wait 30-60 seconds before retrying
        - More attempts for rate limits (they're transient)

        Args:
            operation: Callable to execute
            operation_name: Name for error messages

        Returns:
            Result of the operation

        Raises:
            Exception: If all retry attempts fail
        """
        last_error = None
        max_attempts = self.retry_attempts

        for attempt in range(max_attempts):
            try:
                return operation()
            except Exception as e:
                last_error = e
                error_str = str(e)

                # Check if this is a rate limit error (429)
                is_rate_limit = '429' in error_str or 'rate' in error_str.lower()

                if attempt < max_attempts - 1:
                    if is_rate_limit:
                        # Rate limit: wait longer (30s, 60s, 120s)
                        sleep_time = 30 * (2 ** attempt)
                        print(f"Rate limited, waiting {sleep_time}s before retry...")
                    else:
                        # Normal error: standard backoff (2s, 4s, 8s)
                        sleep_time = 2 * (2 ** attempt)

                    time.sleep(sleep_time)

        raise Exception(f"{operation_name} failed after {max_attempts} attempts: {str(last_error)}")

    def get_btc_price(self) -> float:
        """
        Get current BTC market price

        Returns:
            Current BTC price in USDC

        Example:
            >>> price = client.get_btc_price()
            >>> print(f"BTC: ${price:,.2f}")
            BTC: $87,432.50
        """
        def fetch_price():
            # Get all mid prices
            all_mids = self.info.all_mids()
            if 'BTC' in all_mids:
                return float(all_mids['BTC'])
            else:
                raise Exception(f"BTC price not found in response: {all_mids}")

        try:
            return self._retry_operation(fetch_price, "Get BTC price")
        except Exception as e:
            raise Exception(f"Failed to get BTC price: {str(e)}")

    def get_account_balance(self) -> float:
        """
        Get available USDC balance from perp clearinghouse

        HyperLiquid stores USDC in the perpetual trading clearinghouse,
        not the spot clearinghouse. This queries the perp account.

        Returns:
            Available USDC balance (account value)

        Example:
            >>> balance = client.get_account_balance()
            >>> print(f"Balance: ${balance:,.2f}")
            Balance: $100,000.00
        """
        def fetch_balance():
            # Get user state from perp clearinghouse
            user_state = self.info.user_state(self.wallet_address)

            if 'marginSummary' in user_state:
                margin = user_state['marginSummary']
                account_value = float(margin.get('accountValue', 0))
                return account_value

            # Fallback: try spot clearinghouse
            spot_state = self.info.spot_user_state(self.wallet_address)
            if 'balances' in spot_state:
                for balance in spot_state['balances']:
                    if balance['coin'] == 'USDC':
                        return float(balance['total'])

            return 0.0

        try:
            return self._retry_operation(fetch_balance, "Get account balance")
        except Exception as e:
            raise Exception(f"Failed to get account balance: {str(e)}")

    def place_market_order(self, side: str, size_usd: float) -> Tuple[str, float, float]:
        """
        Place a market order for BTC

        Args:
            side: 'BUY' or 'SELL'
            size_usd: Order size in USDC

        Returns:
            Tuple of (order_id, fill_price, fill_size_btc)

        Example:
            >>> order_id, price, size = client.place_market_order('BUY', 100000)
            >>> print(f"Bought {size:.4f} BTC at ${price:,.2f}")
            Bought 1.1435 BTC at $87,432.50
        """
        def execute_order():
            # Get current price to calculate BTC size
            current_price = self.get_btc_price()
            size_btc = size_usd / current_price

            # Round to appropriate precision (4 decimal places for BTC on HyperLiquid)
            size_btc = round(size_btc, 4)

            # Determine if buy or sell
            is_buy = side.upper() == 'BUY'

            # Place market order using SDK
            # For market orders, we use a limit order with IOC (Immediate or Cancel)
            # at a price that will definitely fill (slippage buffer)
            if is_buy:
                # For buys, use a price above market
                limit_price = current_price * 1.01  # 1% slippage buffer
            else:
                # For sells, use a price below market
                limit_price = current_price * 0.99  # 1% slippage buffer

            # Round price to appropriate precision
            limit_price = round(limit_price, 1)

            # Place the order
            # SDK uses 'name' parameter for the trading pair
            result = self.exchange.order(
                name="BTC",
                is_buy=is_buy,
                sz=size_btc,
                limit_px=limit_price,
                order_type={"limit": {"tif": "Ioc"}},  # Immediate or Cancel
                reduce_only=False
            )

            # Parse the response
            if result.get('status') == 'ok':
                response_data = result.get('response', {})
                if response_data.get('type') == 'order':
                    statuses = response_data.get('data', {}).get('statuses', [])
                    if statuses:
                        status = statuses[0]
                        if 'filled' in status:
                            filled = status['filled']
                            return (
                                str(status.get('oid', 'unknown')),
                                float(filled['avgPx']),
                                float(filled['totalSz'])
                            )
                        elif 'resting' in status:
                            # Order is resting (not filled) - shouldn't happen with IOC
                            raise Exception(f"Order not filled (resting): {status}")
                        elif 'error' in status:
                            raise Exception(f"Order error: {status['error']}")

                raise Exception(f"Unexpected response format: {result}")
            else:
                raise Exception(f"Order failed: {result}")

        try:
            return self._retry_operation(execute_order, f"Place {side} order")
        except Exception as e:
            raise Exception(f"Failed to place {side} order: {str(e)}")

    def get_positions(self) -> Dict:
        """
        Get current open positions

        Returns:
            Dictionary with position details

        Example:
            >>> positions = client.get_positions()
            >>> if positions.get('BTC'):
            ...     print(f"Position: {positions['BTC']['size']} BTC")
        """
        def fetch_positions():
            user_state = self.info.user_state(self.wallet_address)

            positions = {}
            if 'assetPositions' in user_state:
                for pos in user_state['assetPositions']:
                    position_data = pos.get('position', {})
                    size = float(position_data.get('szi', 0))
                    if size != 0:  # Only open positions
                        coin = position_data.get('coin', 'UNKNOWN')
                        positions[coin] = {
                            'size': size,
                            'entry_price': float(position_data.get('entryPx', 0)),
                            'unrealized_pnl': float(position_data.get('unrealizedPnl', 0)),
                            'liquidation_price': float(position_data.get('liquidationPx', 0)) if position_data.get('liquidationPx') else None
                        }

            return positions

        try:
            return self._retry_operation(fetch_positions, "Get positions")
        except Exception as e:
            raise Exception(f"Failed to get positions: {str(e)}")

    def get_order_status(self, order_id: str) -> Dict:
        """
        Check status of a specific order

        Args:
            order_id: The order ID to check

        Returns:
            Order status details
        """
        def fetch_order():
            # Get open orders
            open_orders = self.info.open_orders(self.wallet_address)
            for order in open_orders:
                if str(order.get('oid')) == order_id:
                    return order

            # Check user fills for completed orders
            user_fills = self.info.user_fills(self.wallet_address)
            for fill in user_fills:
                if str(fill.get('oid')) == order_id:
                    return {'status': 'filled', **fill}

            return {'status': 'not_found', 'order_id': order_id}

        try:
            return self._retry_operation(fetch_order, "Get order status")
        except Exception as e:
            raise Exception(f"Failed to get order status: {str(e)}")

    def close_all_positions(self) -> bool:
        """
        Emergency function: Close all open positions at market price

        Use this for emergency exits only.

        Returns:
            True if successful, False otherwise
        """
        try:
            positions = self.get_positions()

            for coin, pos in positions.items():
                size = abs(pos['size'])
                side = 'SELL' if pos['size'] > 0 else 'BUY'

                # Close position
                current_price = self.get_btc_price()
                self.place_market_order(side, size * current_price)
                print(f"Closed {coin} position: {side} {size}")

            return True

        except Exception as e:
            print(f"Failed to close positions: {str(e)}")
            return False


# Module testing (only runs if script executed directly)
if __name__ == '__main__':
    import os
    from dotenv import load_dotenv

    # Load credentials
    load_dotenv()
    wallet_address = os.getenv('HYPERLIQUID_API_KEY')
    private_key = os.getenv('HYPERLIQUID_API_SECRET')

    if not wallet_address or not private_key:
        print("ERROR: Set HYPERLIQUID_API_KEY and HYPERLIQUID_API_SECRET in .env file")
        exit(1)

    # Create client (testnet for safety)
    client = HyperLiquidClient(wallet_address, private_key, testnet=True)

    # Test methods
    print("Testing HyperLiquid Client with SDK...")
    print(f"BTC Price: ${client.get_btc_price():,.2f}")
    print(f"Account Balance: ${client.get_account_balance():,.2f}")
    print(f"Positions: {client.get_positions()}")
    print("All tests passed!")
