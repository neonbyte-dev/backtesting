"""
HyperLiquid Exchange Client

This module handles all API interactions with HyperLiquid exchange.
It provides methods to:
- Fetch current BTC price
- Get account balance
- Place market orders
- Check order status
- Monitor positions

Error handling:
- Automatic retries with exponential backoff
- Timeout protection (30 seconds)
- Detailed error logging
"""

import requests
import time
import hmac
import hashlib
import json
from typing import Dict, Optional, Tuple
from datetime import datetime


class HyperLiquidClient:
    """
    Client for interacting with HyperLiquid API

    Supports both testnet and mainnet environments.
    All methods include error handling and retry logic.
    """

    def __init__(self, api_key: str, api_secret: str, testnet: bool = True,
                 retry_attempts: int = 3, timeout: int = 30):
        """
        Initialize HyperLiquid client

        Args:
            api_key: Your HyperLiquid API key
            api_secret: Your HyperLiquid API secret
            testnet: True for testnet, False for mainnet
            retry_attempts: Number of retries on failure
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.retry_attempts = retry_attempts
        self.timeout = timeout

        # Set base URL based on environment
        if testnet:
            self.base_url = "https://api.hyperliquid-testnet.xyz"
        else:
            self.base_url = "https://api.hyperliquid.xyz"

        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json'
        })

    def _generate_signature(self, timestamp: str, method: str, endpoint: str, body: str = "") -> str:
        """
        Generate HMAC signature for authenticated requests

        HyperLiquid uses HMAC-SHA256 for request signing.
        Format: timestamp + method + endpoint + body
        """
        message = f"{timestamp}{method}{endpoint}{body}"
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature

    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None,
                      authenticated: bool = False) -> Dict:
        """
        Make HTTP request to HyperLiquid API with retry logic

        Args:
            method: HTTP method (GET, POST)
            endpoint: API endpoint path
            data: Request payload (for POST)
            authenticated: Whether to sign the request

        Returns:
            API response as dictionary

        Raises:
            Exception: If all retry attempts fail
        """
        url = f"{self.base_url}{endpoint}"

        for attempt in range(self.retry_attempts):
            try:
                # Add authentication if required
                headers = {}
                if authenticated:
                    timestamp = str(int(time.time() * 1000))
                    body = json.dumps(data) if data else ""
                    signature = self._generate_signature(timestamp, method, endpoint, body)

                    headers.update({
                        'HX-ACCESS-KEY': self.api_key,
                        'HX-ACCESS-SIGN': signature,
                        'HX-ACCESS-TIMESTAMP': timestamp
                    })

                # Make request
                if method == 'GET':
                    response = self.session.get(url, headers=headers, timeout=self.timeout)
                elif method == 'POST':
                    response = self.session.post(url, json=data, headers=headers, timeout=self.timeout)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                # Check response
                response.raise_for_status()
                return response.json()

            except requests.exceptions.Timeout:
                if attempt == self.retry_attempts - 1:
                    raise Exception(f"Request timeout after {self.retry_attempts} attempts")
                time.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s, 4s

            except requests.exceptions.RequestException as e:
                if attempt == self.retry_attempts - 1:
                    raise Exception(f"Request failed after {self.retry_attempts} attempts: {str(e)}")
                time.sleep(2 ** attempt)

        raise Exception("Unexpected error in _make_request")

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
        try:
            # HyperLiquid ticker endpoint
            response = self._make_request('GET', '/info/ticker?coin=BTC')

            # Extract last price
            if 'price' in response:
                return float(response['price'])
            else:
                raise Exception(f"Unexpected response format: {response}")

        except Exception as e:
            raise Exception(f"Failed to get BTC price: {str(e)}")

    def get_account_balance(self) -> float:
        """
        Get available USDC balance

        Returns:
            Available USDC balance

        Example:
            >>> balance = client.get_account_balance()
            >>> print(f"Balance: ${balance:,.2f}")
            Balance: $100,000.00
        """
        try:
            response = self._make_request('GET', '/info/spotClearinghouseState',
                                         authenticated=True)

            # Find USDC balance
            if 'balances' in response:
                for balance in response['balances']:
                    if balance['coin'] == 'USDC':
                        return float(balance['total'])

            raise Exception(f"USDC balance not found in response")

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
        try:
            # Get current price to calculate BTC size
            current_price = self.get_btc_price()
            size_btc = size_usd / current_price

            # Prepare order payload
            order_data = {
                'coin': 'BTC',
                'is_buy': side == 'BUY',
                'sz': round(size_btc, 8),  # 8 decimal places for BTC
                'limit_px': None,  # Market order (no limit price)
                'order_type': {'limit': {'tif': 'Ioc'}},  # Immediate or cancel
                'reduce_only': False
            }

            # Place order
            response = self._make_request('POST', '/exchange/order',
                                         data=order_data, authenticated=True)

            # Extract fill information
            if response.get('status') == 'ok':
                fill_info = response['response']['data']['statuses'][0]

                if 'filled' in fill_info:
                    filled = fill_info['filled']
                    return (
                        response['response']['data']['statuses'][0].get('oid', 'unknown'),
                        float(filled['avgPx']),
                        float(filled['totalSz'])
                    )
                else:
                    raise Exception(f"Order not filled: {fill_info}")
            else:
                raise Exception(f"Order failed: {response}")

        except Exception as e:
            raise Exception(f"Failed to place {side} order: {str(e)}")

    def get_positions(self) -> Dict:
        """
        Get current open positions

        Returns:
            Dictionary with position details

        Example:
            >>> positions = client.get_positions()
            >>> if positions['BTC']:
            ...     print(f"Position: {positions['BTC']['size']} BTC")
        """
        try:
            response = self._make_request('GET', '/info/userState', authenticated=True)

            positions = {}
            if 'assetPositions' in response:
                for pos in response['assetPositions']:
                    if float(pos['position']['szi']) != 0:  # Only open positions
                        positions[pos['position']['coin']] = {
                            'size': float(pos['position']['szi']),
                            'entry_price': float(pos['position']['entryPx']),
                            'unrealized_pnl': float(pos['position']['unrealizedPnl'])
                        }

            return positions

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
        try:
            response = self._make_request('GET', f'/info/order/{order_id}',
                                         authenticated=True)
            return response

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
                self.place_market_order(side, size * self.get_btc_price())
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
    api_key = os.getenv('HYPERLIQUID_API_KEY')
    api_secret = os.getenv('HYPERLIQUID_API_SECRET')

    if not api_key or not api_secret:
        print("ERROR: Set HYPERLIQUID_API_KEY and HYPERLIQUID_API_SECRET in .env file")
        exit(1)

    # Create client
    client = HyperLiquidClient(api_key, api_secret, testnet=True)

    # Test methods
    print("Testing HyperLiquid Client...")
    print(f"BTC Price: ${client.get_btc_price():,.2f}")
    print(f"Account Balance: ${client.get_account_balance():,.2f}")
    print(f"Positions: {client.get_positions()}")
    print("All tests passed!")
