"""
Backpack Exchange API Client
Handles authentication and API requests to Backpack Exchange.

Uses ED25519 signature authentication as per Backpack Exchange API specification.
"""

import base64
import json
import time
import logging
import requests
from typing import Dict, Any, Optional
from urllib.parse import urlencode

try:
    from nacl.signing import SigningKey
    from nacl.encoding import Base64Encoder
except ImportError:
    raise ImportError(
        "PyNaCl is required for ED25519 signing. Install it with: pip install pynacl"
    )

logger = logging.getLogger(__name__)


class BackpackAPI:
    """Client for interacting with Backpack Exchange API."""
    
    def __init__(self, api_key: str, api_secret: str, base_url: str = "https://api.backpack.exchange"):
        """
        Initialize Backpack API client.
        
        Args:
            api_key: Base64 encoded ED25519 public key (verifying key)
            api_secret: Base64 encoded ED25519 private key (signing key)
            base_url: Base URL for API endpoints
        """
        self.api_key = api_key  # Base64 encoded public key
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        
        # Decode the private key for signing
        try:
            private_key_bytes = base64.b64decode(api_secret)
            self.signing_key = SigningKey(private_key_bytes)
        except Exception as e:
            raise ValueError(f"Invalid API secret (must be base64 encoded ED25519 private key): {e}")
        
        logger.info(f"Backpack API client initialized with base URL: {base_url}")
    
    def _generate_signature(self, instruction: str, params: Dict[str, Any], timestamp: int, window: int = 5000) -> str:
        """
        Generate ED25519 signature for API request.
        
        Args:
            instruction: API instruction type (e.g., 'orderExecute', 'balanceQuery')
            params: Request parameters (sorted alphabetically)
            timestamp: Unix timestamp in milliseconds
            window: Time window in milliseconds (default 5000, max 60000)
            
        Returns:
            Base64 encoded signature string
        """
        # Sort parameters alphabetically and convert to query string
        sorted_params = sorted(params.items())
        param_string = urlencode(sorted_params)
        
        # Build the signing message
        if param_string:
            message = f"instruction={instruction}&{param_string}&timestamp={timestamp}&window={window}"
        else:
            message = f"instruction={instruction}&timestamp={timestamp}&window={window}"
        
        # Sign the message with ED25519
        signed = self.signing_key.sign(message.encode('utf-8'))
        signature = base64.b64encode(signed.signature).decode('utf-8')
        
        logger.debug(f"Signing message: {message}")
        return signature
    
    def _get_headers(self, instruction: str, params: Dict[str, Any], timestamp: int, window: int = 5000) -> Dict[str, str]:
        """
        Generate headers for authenticated API request.
        
        Args:
            instruction: API instruction type
            params: Request parameters
            timestamp: Unix timestamp in milliseconds
            window: Time window in milliseconds
            
        Returns:
            Dictionary of headers
        """
        signature = self._generate_signature(instruction, params, timestamp, window)
        
        headers = {
            "X-API-Key": self.api_key,
            "X-Timestamp": str(timestamp),
            "X-Window": str(window),
            "X-Signature": signature,
            "Content-Type": "application/json"
        }
        return headers
    
    def _request(self, method: str, endpoint: str, instruction: str = None, 
                 params: Optional[Dict] = None, data: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Make API request (authenticated or public).
        
        Args:
            method: HTTP method
            endpoint: API endpoint (without base URL)
            instruction: API instruction for signed requests (None for public endpoints)
            params: Query parameters
            data: Request body data
            
        Returns:
            API response as dictionary
        """
        url = f"{self.base_url}{endpoint}"
        timestamp = int(time.time() * 1000)
        
        # Prepare request parameters for signing
        request_params = {}
        if params:
            request_params.update(params)
        if data:
            request_params.update(data)
        
        # Generate headers (with signature if instruction provided)
        if instruction:
            headers = self._get_headers(instruction, request_params, timestamp)
        else:
            headers = {"Content-Type": "application/json"}
        
        try:
            if method == "GET":
                response = self.session.get(url, headers=headers, params=params)
            elif method == "POST":
                response = self.session.post(url, headers=headers, json=data)
            elif method == "DELETE":
                if data:
                    response = self.session.delete(url, headers=headers, json=data)
                else:
                    response = self.session.delete(url, headers=headers, params=params)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            if hasattr(e.response, 'text'):
                logger.error(f"Response: {e.response.text}")
            raise
    
    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        Get current ticker/price information for a symbol.
        
        Args:
            symbol: Trading pair symbol (e.g., "SOL_USDC")
            
        Returns:
            Ticker data including current price (lastPrice field)
        """
        endpoint = "/api/v1/ticker"
        params = {"symbol": symbol}
        
        logger.info(f"Fetching ticker for {symbol}")
        return self._request("GET", endpoint, instruction=None, params=params)
    
    def get_balance(self) -> Dict[str, Any]:
        """
        Get account balance.
        
        Returns:
            Dictionary mapping asset symbols to balance info (available, locked, staked)
        """
        endpoint = "/api/v1/capital"
        
        logger.info("Fetching account balance")
        return self._request("GET", endpoint, instruction="balanceQuery")
    
    def place_limit_order(self, symbol: str, side: str, price: float, quantity: float) -> Dict[str, Any]:
        """
        Place a limit order.
        
        Args:
            symbol: Trading pair symbol (e.g., "SOL_USDC")
            side: "Bid" or "Ask"
            price: Limit price
            quantity: Order quantity
            
        Returns:
            Order information including order ID
        """
        endpoint = "/api/v1/order"
        data = {
            "symbol": symbol,
            "side": side,
            "orderType": "Limit",
            "price": str(price),
            "quantity": str(quantity),
            "timeInForce": "GTC"
        }
        
        logger.info(f"Placing {side} limit order: {quantity} @ {price} for {symbol}")
        return self._request("POST", endpoint, instruction="orderExecute", data=data)
    
    def cancel_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """
        Cancel an open order.
        
        Args:
            symbol: Trading pair symbol
            order_id: Order ID to cancel
            
        Returns:
            Cancellation confirmation
        """
        endpoint = "/api/v1/order"
        data = {
            "symbol": symbol,
            "orderId": order_id
        }
        
        logger.info(f"Cancelling order {order_id} for {symbol}")
        return self._request("DELETE", endpoint, instruction="orderCancel", data=data)
    
    def get_order_status(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """
        Get status of a specific order.
        
        Args:
            symbol: Trading pair symbol
            order_id: Order ID to check
            
        Returns:
            Order status information
        """
        endpoint = "/api/v1/order"
        params = {
            "symbol": symbol,
            "orderId": order_id
        }
        
        return self._request("GET", endpoint, instruction="orderQuery", params=params)
    
    def get_open_orders(self, symbol: str = None) -> list:
        """
        Get all open orders for a symbol (or all symbols if not specified).
        
        Args:
            symbol: Trading pair symbol (optional)
            
        Returns:
            List of open orders
        """
        endpoint = "/api/v1/orders"
        params = {}
        if symbol:
            params["symbol"] = symbol
        
        logger.info(f"Fetching open orders" + (f" for {symbol}" if symbol else ""))
        result = self._request("GET", endpoint, instruction="orderQueryAll", params=params)
        
        # API returns a list directly
        return result if isinstance(result, list) else []
    
    def cancel_all_orders(self, symbol: str) -> list:
        """
        Cancel all open orders for a symbol.
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            List of cancelled orders
        """
        endpoint = "/api/v1/orders"
        data = {"symbol": symbol}
        
        logger.warning(f"Cancelling ALL orders for {symbol}")
        result = self._request("DELETE", endpoint, instruction="orderCancelAll", data=data)
        
        # API returns a list of cancelled orders
        return result if isinstance(result, list) else []
