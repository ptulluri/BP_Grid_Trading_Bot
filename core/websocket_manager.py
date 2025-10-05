"""
Backpack Exchange WebSocket Client
Handles real-time price updates via WebSocket connection.
"""

import json
import logging
import threading
import time
from typing import Callable, Optional
import websocket

logger = logging.getLogger(__name__)


class BackpackWebSocket:
    """WebSocket client for Backpack Exchange real-time data."""
    
    def __init__(self, symbol: str, on_price_update: Callable[[float], None]):
        """
        Initialize WebSocket client.
        
        Args:
            symbol: Trading pair symbol (e.g., "SOL_USDC")
            on_price_update: Callback function to handle price updates
        """
        self.symbol = symbol
        self.on_price_update = on_price_update
        self.ws_url = "wss://ws.backpack.exchange"
        self.ws = None
        self.thread = None
        self.running = False
        self.last_price = None
        self.reconnect_delay = 5
        
        logger.info(f"WebSocket client initialized for {symbol}")
    
    def _on_message(self, ws, message):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(message)
            
            # Check if this is a ticker update
            if data.get('stream') == f'ticker.{self.symbol}':
                ticker_data = data.get('data', {})
                last_price = ticker_data.get('c')  # 'c' is last price in ticker stream
                
                if last_price:
                    price = float(last_price)
                    self.last_price = price
                    logger.debug(f"Price update: {price}")
                    
                    # Call the callback function
                    if self.on_price_update:
                        self.on_price_update(price)
            
            # Handle subscription confirmation
            elif 'result' in data:
                logger.info(f"Subscription confirmed: {data}")
        
        except Exception as e:
            logger.error(f"Error processing WebSocket message: {e}")
    
    def _on_error(self, ws, error):
        """Handle WebSocket errors."""
        logger.error(f"WebSocket error: {error}")
    
    def _on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket connection close."""
        logger.warning(f"WebSocket connection closed: {close_status_code} - {close_msg}")
        
        # Attempt to reconnect if still running
        if self.running:
            logger.info(f"Attempting to reconnect in {self.reconnect_delay} seconds...")
            time.sleep(self.reconnect_delay)
            if self.running:
                self._connect()
    
    def _on_open(self, ws):
        """Handle WebSocket connection open."""
        logger.info("WebSocket connection established")
        
        # Subscribe to ticker stream for the symbol
        subscribe_message = {
            "method": "SUBSCRIBE",
            "params": [f"ticker.{self.symbol}"]
        }
        
        ws.send(json.dumps(subscribe_message))
        logger.info(f"Subscribed to ticker.{self.symbol}")
    
    def _connect(self):
        """Establish WebSocket connection."""
        try:
            self.ws = websocket.WebSocketApp(
                self.ws_url,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
                on_open=self._on_open
            )
            
            # Run WebSocket in a separate thread
            self.ws.run_forever(ping_interval=30, ping_timeout=10)
        
        except Exception as e:
            logger.error(f"WebSocket connection error: {e}")
            if self.running:
                time.sleep(self.reconnect_delay)
                self._connect()
    
    def start(self):
        """Start WebSocket connection in a background thread."""
        if self.running:
            logger.warning("WebSocket already running")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._connect, daemon=True)
        self.thread.start()
        logger.info("WebSocket client started")
    
    def stop(self):
        """Stop WebSocket connection."""
        logger.info("Stopping WebSocket client...")
        self.running = False
        
        if self.ws:
            self.ws.close()
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
        
        logger.info("WebSocket client stopped")
    
    def get_last_price(self) -> Optional[float]:
        """
        Get the last received price.
        
        Returns:
            Last price or None if no price received yet
        """
        return self.last_price
    
    def is_connected(self) -> bool:
        """
        Check if WebSocket is connected.
        
        Returns:
            True if connected, False otherwise
        """
        return self.ws is not None and self.ws.sock and self.ws.sock.connected
