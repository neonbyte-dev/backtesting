"""
Solana DEX Client - Jupiter Aggregator

This module handles Solana token swaps via Jupiter aggregator.
Similar interface pattern to HyperLiquidClient for consistency.

Jupiter is the dominant DEX aggregator on Solana, providing:
- Best price routing across all Solana DEXs
- Slippage protection
- Simple REST API (no SDK required)

How it works:
1. Get quote from Jupiter (includes route and expected output)
2. Get serialized transaction from Jupiter
3. Sign transaction with your wallet
4. Submit to Solana RPC
"""

import time
import base64
import requests
from typing import Dict, Optional, Tuple

# Solana libraries for signing and submitting transactions
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.transaction import VersionedTransaction
from solana.rpc.api import Client as SolanaClient
from solana.rpc.commitment import Confirmed
from solana.rpc.types import TokenAccountOpts


class SolanaDEXClient:
    """
    Client for trading Solana tokens via Jupiter aggregator.

    Uses REST APIs directly (no SDK) for transparency.
    All methods include error handling and retry logic.
    """

    # Common token addresses on Solana
    USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
    SOL_MINT = "So11111111111111111111111111111111111111112"  # Wrapped SOL

    # API endpoints
    JUPITER_API = "https://quote-api.jup.ag/v6"
    DEXSCREENER_API = "https://api.dexscreener.com/latest/dex"

    def __init__(self, private_key: str, rpc_url: str = "https://api.mainnet-beta.solana.com",
                 slippage_bps: int = 100, retry_attempts: int = 3, priority_fee_lamports: int = 100000):
        """
        Initialize Solana DEX client

        Args:
            private_key: Base58-encoded Solana private key
            rpc_url: Solana RPC endpoint URL
            slippage_bps: Slippage tolerance in basis points (100 = 1%)
            retry_attempts: Number of retries on failure
            priority_fee_lamports: Priority fee in lamports for faster execution (100000 = 0.0001 SOL)
        """
        self.rpc_url = rpc_url
        self.slippage_bps = slippage_bps
        self.retry_attempts = retry_attempts
        self.priority_fee_lamports = priority_fee_lamports

        # Initialize keypair from private key
        try:
            # Private key can be base58 string or list of bytes
            if isinstance(private_key, str):
                # Try to decode as base58
                self.keypair = Keypair.from_base58_string(private_key)
            else:
                self.keypair = Keypair.from_bytes(bytes(private_key))

            self.wallet_address = str(self.keypair.pubkey())
            print(f"[Solana] Wallet: {self.wallet_address[:8]}...{self.wallet_address[-8:]}")
        except Exception as e:
            raise ValueError(f"Invalid Solana private key: {e}")

        # Initialize Solana RPC client
        self.solana = SolanaClient(rpc_url)

    def _retry_operation(self, operation, operation_name: str):
        """
        Retry an operation with exponential backoff

        Same pattern as HyperLiquid client for consistency.
        """
        last_error = None

        for attempt in range(self.retry_attempts):
            try:
                return operation()
            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                # Rate limit handling
                if '429' in str(e) or 'rate' in error_str:
                    sleep_time = 30 + (30 * attempt)
                    print(f"Rate limited, waiting {sleep_time}s before retry...")
                    time.sleep(sleep_time)
                else:
                    # Normal error: exponential backoff
                    if attempt < self.retry_attempts - 1:
                        sleep_time = 2 * (2 ** attempt)
                        time.sleep(sleep_time)

        raise Exception(f"{operation_name} failed after retries: {str(last_error)}")

    def get_price(self, token_address: str) -> float:
        """
        Get current token price via DexScreener

        DexScreener provides reliable pricing for Solana tokens.

        Args:
            token_address: Solana token mint address

        Returns:
            Current price in USD
        """
        def fetch_price():
            url = f"{self.DEXSCREENER_API}/tokens/{token_address}"
            response = requests.get(url, timeout=10)

            if response.status_code == 429:
                raise Exception("Rate limited (429)")

            response.raise_for_status()
            data = response.json()

            if data.get('pairs') and len(data['pairs']) > 0:
                # Get the pair with highest liquidity
                pairs = sorted(data['pairs'],
                              key=lambda p: float(p.get('liquidity', {}).get('usd', 0) or 0),
                              reverse=True)
                price = float(pairs[0].get('priceUsd', 0) or 0)
                if price > 0:
                    return price

            raise Exception(f"No price found for token {token_address}")

        return self._retry_operation(fetch_price, "Get token price")

    def get_token_info(self, token_address: str) -> Dict:
        """
        Get token info including price, liquidity, FDV

        Args:
            token_address: Solana token mint address

        Returns:
            Dict with price, fdv, liquidity, name, symbol
        """
        def fetch_info():
            url = f"{self.DEXSCREENER_API}/tokens/{token_address}"
            response = requests.get(url, timeout=10)

            if response.status_code == 429:
                raise Exception("Rate limited (429)")

            response.raise_for_status()
            data = response.json()

            if data.get('pairs') and len(data['pairs']) > 0:
                # Get the pair with highest liquidity
                pairs = sorted(data['pairs'],
                              key=lambda p: float(p.get('liquidity', {}).get('usd', 0) or 0),
                              reverse=True)
                pair = pairs[0]

                return {
                    'price': float(pair.get('priceUsd', 0) or 0),
                    'fdv': float(pair.get('fdv', 0) or 0),
                    'liquidity': float(pair.get('liquidity', {}).get('usd', 0) or 0),
                    'name': pair.get('baseToken', {}).get('name', 'Unknown'),
                    'symbol': pair.get('baseToken', {}).get('symbol', 'UNK'),
                    'chain': pair.get('chainId', 'solana'),
                }

            return {'price': 0, 'fdv': 0, 'liquidity': 0, 'name': 'Unknown', 'symbol': 'UNK'}

        return self._retry_operation(fetch_info, "Get token info")

    def get_sol_balance(self) -> float:
        """
        Get SOL balance (needed for transaction fees)

        Returns:
            SOL balance
        """
        def fetch_balance():
            response = self.solana.get_balance(self.keypair.pubkey(), commitment=Confirmed)
            # Convert lamports to SOL (1 SOL = 1e9 lamports)
            return response.value / 1e9

        return self._retry_operation(fetch_balance, "Get SOL balance")

    def get_usdc_balance(self) -> float:
        """
        Get USDC balance

        Returns:
            USDC balance
        """
        def fetch_balance():
            # Get all token accounts for this wallet
            opts = TokenAccountOpts(mint=Pubkey.from_string(self.USDC_MINT))
            response = self.solana.get_token_accounts_by_owner_json_parsed(
                self.keypair.pubkey(),
                opts,
                commitment=Confirmed
            )

            if response.value:
                for account in response.value:
                    # Handle both object and dict access patterns
                    try:
                        # Try object attribute access first
                        data = account.account.data
                        if hasattr(data, 'parsed'):
                            parsed = data.parsed
                        else:
                            parsed = data.get('parsed', {})

                        if isinstance(parsed, dict):
                            info = parsed.get('info', {})
                        else:
                            info = getattr(parsed, 'info', {})
                            if not isinstance(info, dict):
                                info = {}

                        if info.get('mint') == self.USDC_MINT:
                            token_amount = info.get('tokenAmount', {})
                            amount = float(token_amount.get('uiAmount', 0) or 0)
                            return amount
                    except (AttributeError, TypeError):
                        # Fallback: try pure dict access
                        try:
                            acc_data = account.get('account', {}).get('data', {})
                            parsed = acc_data.get('parsed', {})
                            info = parsed.get('info', {})
                            if info.get('mint') == self.USDC_MINT:
                                amount = float(info.get('tokenAmount', {}).get('uiAmount', 0) or 0)
                                return amount
                        except:
                            pass

            return 0.0

        return self._retry_operation(fetch_balance, "Get USDC balance")

    def get_token_balance(self, token_address: str) -> Tuple[float, int]:
        """
        Get balance for a specific token

        Args:
            token_address: Token mint address

        Returns:
            Tuple of (ui_amount, raw_amount)
        """
        def fetch_balance():
            opts = TokenAccountOpts(mint=Pubkey.from_string(token_address))
            response = self.solana.get_token_accounts_by_owner_json_parsed(
                self.keypair.pubkey(),
                opts,
                commitment=Confirmed
            )

            if response.value:
                for account in response.value:
                    try:
                        # Handle both object and dict access patterns
                        data = account.account.data
                        if hasattr(data, 'parsed'):
                            parsed = data.parsed
                        else:
                            parsed = data.get('parsed', {})

                        if isinstance(parsed, dict):
                            info = parsed.get('info', {})
                        else:
                            info = getattr(parsed, 'info', {})
                            if not isinstance(info, dict):
                                info = {}

                        if info.get('mint') == token_address:
                            token_amount = info.get('tokenAmount', {})
                            ui_amount = float(token_amount.get('uiAmount', 0) or 0)
                            raw_amount = int(token_amount.get('amount', 0) or 0)
                            return (ui_amount, raw_amount)
                    except (AttributeError, TypeError):
                        pass

            return (0.0, 0)

        return self._retry_operation(fetch_balance, "Get token balance")

    def _get_jupiter_quote(self, input_mint: str, output_mint: str,
                           amount: int, slippage_bps: int = None) -> Dict:
        """
        Get swap quote from Jupiter

        Args:
            input_mint: Input token address
            output_mint: Output token address
            amount: Amount in smallest unit (lamports for SOL, etc.)
            slippage_bps: Slippage in basis points (uses default if None)

        Returns:
            Jupiter quote response
        """
        if slippage_bps is None:
            slippage_bps = self.slippage_bps

        url = f"{self.JUPITER_API}/quote"
        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": str(amount),
            "slippageBps": slippage_bps,
        }

        response = requests.get(url, params=params, timeout=30)

        if response.status_code == 429:
            raise Exception("Jupiter rate limited (429)")

        response.raise_for_status()
        return response.json()

    def _get_swap_transaction(self, quote: Dict) -> str:
        """
        Get serialized swap transaction from Jupiter

        Args:
            quote: Quote from _get_jupiter_quote()

        Returns:
            Base64-encoded serialized transaction
        """
        url = f"{self.JUPITER_API}/swap"
        payload = {
            "quoteResponse": quote,
            "userPublicKey": self.wallet_address,
            "wrapAndUnwrapSol": True,
            "dynamicComputeUnitLimit": True,
            "prioritizationFeeLamports": self.priority_fee_lamports,  # High priority for fast execution
        }

        response = requests.post(url, json=payload, timeout=30)

        if response.status_code == 429:
            raise Exception("Jupiter rate limited (429)")

        response.raise_for_status()
        return response.json()['swapTransaction']

    def _sign_and_send_transaction(self, serialized_tx: str) -> str:
        """
        Sign and send a serialized transaction

        Args:
            serialized_tx: Base64-encoded serialized transaction

        Returns:
            Transaction signature
        """
        # Decode the transaction
        tx_bytes = base64.b64decode(serialized_tx)
        tx = VersionedTransaction.from_bytes(tx_bytes)

        # Sign the transaction
        tx.sign([self.keypair])

        # Send the transaction
        response = self.solana.send_raw_transaction(
            bytes(tx),
            opts={"skip_preflight": True, "max_retries": 3}
        )

        return str(response.value)

    def buy_token(self, token_address: str, usdc_amount: float,
                  min_liquidity: float = 10000) -> Tuple[str, float, float]:
        """
        Buy a token using USDC via Jupiter

        Args:
            token_address: Token to buy
            usdc_amount: Amount of USDC to spend
            min_liquidity: Minimum liquidity required (skip if below)

        Returns:
            Tuple of (tx_signature, fill_price, tokens_received)
        """
        def execute_buy():
            # Check liquidity first
            token_info = self.get_token_info(token_address)
            if token_info['liquidity'] < min_liquidity:
                raise Exception(f"Insufficient liquidity: ${token_info['liquidity']:,.0f} < ${min_liquidity:,.0f}")

            # Convert USDC amount to smallest unit (6 decimals)
            usdc_amount_raw = int(usdc_amount * 1e6)

            # Get quote
            quote = self._get_jupiter_quote(
                input_mint=self.USDC_MINT,
                output_mint=token_address,
                amount=usdc_amount_raw
            )

            # Check slippage
            expected_output = int(quote['outAmount'])
            min_output = int(quote.get('otherAmountThreshold', expected_output * 0.99))

            if expected_output == 0:
                raise Exception("Quote returned zero output amount")

            # Get and sign transaction
            serialized_tx = self._get_swap_transaction(quote)
            tx_signature = self._sign_and_send_transaction(serialized_tx)

            # Wait for confirmation
            time.sleep(2)

            # Calculate fill price
            # Get token decimals from quote
            out_decimals = int(quote.get('outputDecimals', 9))
            tokens_received = expected_output / (10 ** out_decimals)
            fill_price = usdc_amount / tokens_received if tokens_received > 0 else 0

            print(f"[Solana] BUY: {tokens_received:,.4f} {token_info['symbol']} @ ${fill_price:.8f}")

            return (tx_signature, fill_price, tokens_received)

        return self._retry_operation(execute_buy, "Buy token")

    def sell_token(self, token_address: str, token_amount: float = None,
                   sell_all: bool = False) -> Tuple[str, float, float]:
        """
        Sell a token for USDC via Jupiter

        Args:
            token_address: Token to sell
            token_amount: Amount of tokens to sell (in UI units)
            sell_all: If True, sell entire balance

        Returns:
            Tuple of (tx_signature, fill_price, usdc_received)
        """
        def execute_sell():
            # Get token balance
            ui_balance, raw_balance = self.get_token_balance(token_address)

            if raw_balance == 0:
                raise Exception(f"No balance for token {token_address}")

            # Determine sell amount
            if sell_all:
                amount_raw = raw_balance
                amount_ui = ui_balance
            else:
                # Calculate raw amount from UI amount
                token_info = self.get_token_info(token_address)
                # Estimate decimals from balance ratio
                decimals = round(len(str(raw_balance)) - len(str(int(ui_balance))) if ui_balance > 0 else 9)
                amount_raw = int(token_amount * (10 ** decimals))
                amount_ui = token_amount

                if amount_raw > raw_balance:
                    raise Exception(f"Insufficient balance: {ui_balance} < {token_amount}")

            # Get quote
            quote = self._get_jupiter_quote(
                input_mint=token_address,
                output_mint=self.USDC_MINT,
                amount=amount_raw
            )

            expected_usdc = int(quote['outAmount']) / 1e6  # USDC has 6 decimals

            if expected_usdc < 0.01:
                raise Exception(f"Sell would receive only ${expected_usdc:.6f} USDC - too low")

            # Get and sign transaction
            serialized_tx = self._get_swap_transaction(quote)
            tx_signature = self._sign_and_send_transaction(serialized_tx)

            # Wait for confirmation
            time.sleep(2)

            # Calculate fill price
            fill_price = expected_usdc / amount_ui if amount_ui > 0 else 0

            token_info = self.get_token_info(token_address)
            print(f"[Solana] SELL: {amount_ui:,.4f} {token_info['symbol']} for ${expected_usdc:,.2f}")

            return (tx_signature, fill_price, expected_usdc)

        return self._retry_operation(execute_sell, "Sell token")


# Module testing
if __name__ == '__main__':
    import os
    from dotenv import load_dotenv

    load_dotenv()

    private_key = os.getenv('SOLANA_PRIVATE_KEY')
    rpc_url = os.getenv('SOLANA_RPC_URL', 'https://api.mainnet-beta.solana.com')

    if not private_key:
        print("ERROR: Set SOLANA_PRIVATE_KEY in .env file")
        exit(1)

    print("Testing Solana DEX Client...")

    try:
        client = SolanaDEXClient(private_key, rpc_url)

        print(f"\nSOL Balance: {client.get_sol_balance():.4f}")
        print(f"USDC Balance: ${client.get_usdc_balance():,.2f}")

        # Test price fetch
        test_token = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"  # USDC
        info = client.get_token_info(test_token)
        print(f"\nUSDC Info: {info}")

        print("\nAll tests passed!")

    except Exception as e:
        print(f"Error: {e}")
