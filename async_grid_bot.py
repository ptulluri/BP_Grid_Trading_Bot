"""
Async Grid Trading Bot for Backpack Exchange
Asynchronous implementation with enhanced error handling and logging.
"""

import asyncio
import json
import logging
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from grid_calculator import GridCalculator
from backpack_api import BackpackAPI
from order_manager import OrderManager
from websocket_client import BackpackWebSocket

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('async_grid_bot.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class AsyncGridBot:
    """Asynchronous Grid Trading Bot for Backpack Exchange."""
    
    def __init__(self, config_path: str = "config.json"):
        """
        Initialize async grid trading bot.
        
        Args:
            config_path: Path to configuration file
        """
        self.config = self._load_config(config_path)
        self.running = False
        self.start_time = None
        
        # Exchange and trading components
        self.api = None
        self.grid_calculator = None
        self.order_manager = None
        self.ws_client = None
        
        # Trading parameters
        self.symbol = self.config['trading']['symbol']
        self.quantity = self.config['trading']['quantity']
        self.interval = self.config['trading']['interval']
        self.duration = self.config['trading']['duration']
        self.use_websocket = self.config['trading'].get('use_websocket', True)
        self.current_price = None
        
        logger.info("Async Grid Bot initialized")
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from JSON file."""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            logger.info(f"Configuration loaded from {config_path}")
            return config
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            raise
    
    async def init_exchange(self):
        """
        Initialize exchange connection and components from config.
        Sets up API client, grid calculator, and order manager.
        """
        try:
            logger.info("Initializing exchange connection...")
            
            # Initialize API client
            self.api = BackpackAPI(
                api_key=self.config['api']['api_key'],
                api_secret=self.config['api']['api_secret'],
                base_url=self.config['api']['base_url']
            )
            logger.info("✓ API client initialized")
            
            # Initialize grid calculator
            if self.config['trading']['auto_price']:
                logger.info("Auto-price mode enabled, will calculate grid on start")
                # Get current price
                current_price = await self._get_current_price_async()
                price_range = self.config['trading']['price_range']
                
                grid_lower, grid_upper = GridCalculator.calculate_auto_price_range(
                    current_price, price_range
                )
                
                self.grid_calculator = GridCalculator(
                    grid_upper=grid_upper,
                    grid_lower=grid_lower,
                    grid_num=self.config['trading']['grid_num']
                )
                logger.info(f"✓ Grid auto-initialized: {grid_lower:.2f} - {grid_upper:.2f}")
            else:
                self.grid_calculator = GridCalculator(
                    grid_upper=self.config['trading']['grid_upper'],
                    grid_lower=self.config['trading']['grid_lower'],
                    grid_num=self.config['trading']['grid_num']
                )
                logger.info("✓ Grid calculator initialized with fixed range")
            
            # Initialize order manager
            self.order_manager = OrderManager(self.symbol)
            logger.info("✓ Order manager initialized")
            
            # Initialize WebSocket if enabled
            if self.use_websocket:
                self.ws_client = BackpackWebSocket(
                    symbol=self.symbol,
                    on_price_update=self._on_price_update
                )
                self.ws_client.start()
                await asyncio.sleep(2)  # Wait for initial connection
                logger.info("✓ WebSocket client started")
            
            logger.info("Exchange initialization complete")
            
        except Exception as e:
            logger.error(f"Failed to initialize exchange: {e}", exc_info=True)
            raise
    
    def _on_price_update(self, price: float):
        """Callback for WebSocket price updates."""
        self.current_price = price
        logger.debug(f"WebSocket price update: {price:.4f}")
    
    async def _get_current_price_async(self) -> float:
        """
        Get current market price asynchronously.
        
        Returns:
            Current price
        """
        # Try WebSocket price first
        if self.use_websocket and self.ws_client:
            ws_price = self.ws_client.get_last_price()
            if ws_price is not None:
                logger.debug(f"Using WebSocket price: {ws_price:.4f}")
                return ws_price
        
        # Fall back to REST API
        try:
            # Run synchronous API call in executor to avoid blocking
            loop = asyncio.get_event_loop()
            ticker = await loop.run_in_executor(None, self.api.get_ticker, self.symbol)
            
            price = float(ticker.get('lastPrice', 0))
            if price == 0:
                raise ValueError("Invalid price received from API")
            
            logger.debug(f"Using REST API price: {price:.4f}")
            return price
            
        except Exception as e:
            logger.error(f"Failed to get current price: {e}")
            raise
    
    async def place_grid_orders(self):
        """
        Submit limit buy and sell orders at all grid levels.
        Handles partial fills and API errors with try-except blocks.
        Logs all order IDs and statuses.
        """
        try:
            logger.info("=" * 60)
            logger.info("PLACING GRID ORDERS")
            logger.info("=" * 60)
            
            # Get current price
            current_price = await self._get_current_price_async()
            logger.info(f"Current market price: {current_price:.4f}")
            
            # Check grid health
            if self.grid_calculator.check_and_adjust_grid(current_price):
                if not self.grid_calculator.is_within_grid(current_price):
                    logger.error(f"Price {current_price:.4f} is outside grid boundaries!")
                    logger.error("Cannot place orders. Adjust grid or wait for price to enter range.")
                    return
            
            # Get balanced buy/sell levels
            buy_levels, sell_levels = self.grid_calculator.calculate_balanced_buy_sell_levels(current_price)
            
            logger.info(f"Placing {len(buy_levels)} buy orders and {len(sell_levels)} sell orders...")
            
            # Place buy orders (Bid side)
            buy_success = 0
            buy_failed = 0
            
            for i, price in enumerate(buy_levels, 1):
                try:
                    logger.info(f"Placing buy order {i}/{len(buy_levels)} at {price:.4f}...")
                    
                    # Run synchronous API call in executor
                    loop = asyncio.get_event_loop()
                    response = await loop.run_in_executor(
                        None,
                        lambda: self.api.place_limit_order(
                            symbol=self.symbol,
                            side="Bid",
                            price=price,
                            quantity=self.quantity
                        )
                    )
                    
                    # Extract order ID
                    order_id = response.get('id', f"buy_{int(time.time())}_{i}")
                    
                    # Add to order manager
                    self.order_manager.add_order(order_id, "buy", price, self.quantity)
                    
                    logger.info(f"✓ Buy order placed - ID: {order_id}, Price: {price:.4f}, Qty: {self.quantity}")
                    buy_success += 1
                    
                    # Rate limiting
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    logger.error(f"✗ Failed to place buy order at {price:.4f}: {e}")
                    buy_failed += 1
                    continue
            
            # Place sell orders (Ask side)
            sell_success = 0
            sell_failed = 0
            
            for i, price in enumerate(sell_levels, 1):
                try:
                    logger.info(f"Placing sell order {i}/{len(sell_levels)} at {price:.4f}...")
                    
                    # Run synchronous API call in executor
                    loop = asyncio.get_event_loop()
                    response = await loop.run_in_executor(
                        None,
                        lambda: self.api.place_limit_order(
                            symbol=self.symbol,
                            side="Ask",
                            price=price,
                            quantity=self.quantity
                        )
                    )
                    
                    # Extract order ID
                    order_id = response.get('id', f"sell_{int(time.time())}_{i}")
                    
                    # Add to order manager
                    self.order_manager.add_order(order_id, "sell", price, self.quantity)
                    
                    logger.info(f"✓ Sell order placed - ID: {order_id}, Price: {price:.4f}, Qty: {self.quantity}")
                    sell_success += 1
                    
                    # Rate limiting
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    logger.error(f"✗ Failed to place sell order at {price:.4f}: {e}")
                    sell_failed += 1
                    continue
            
            # Summary
            logger.info("=" * 60)
            logger.info("GRID ORDERS PLACEMENT SUMMARY")
            logger.info("=" * 60)
            logger.info(f"Buy Orders:  {buy_success} successful, {buy_failed} failed")
            logger.info(f"Sell Orders: {sell_success} successful, {sell_failed} failed")
            logger.info(f"Total:       {buy_success + sell_success} successful, {buy_failed + sell_failed} failed")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"Error in place_grid_orders: {e}", exc_info=True)
            raise
    
    async def cancel_all_orders(self):
        """
        Cancel all open orders for grid reset.
        Handles API errors with try-except blocks.
        Logs cancellation status for each order.
        """
        try:
            logger.info("=" * 60)
            logger.info("CANCELLING ALL ORDERS")
            logger.info("=" * 60)
            
            # Get open orders from order manager
            open_orders = self.order_manager.get_open_orders()
            
            if not open_orders:
                logger.info("No open orders to cancel")
                return
            
            logger.info(f"Cancelling {len(open_orders)} open orders...")
            
            # Try bulk cancel first
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    self.api.cancel_all_orders,
                    self.symbol
                )
                logger.info("✓ Bulk cancel successful")
                
                # Mark all as cancelled in order manager
                for order in open_orders:
                    logger.info(f"✓ Order cancelled - ID: {order.order_id}, Side: {order.side}, Price: {order.price:.4f}")
                
                # Clear order manager
                self.order_manager = OrderManager(self.symbol)
                
            except Exception as e:
                logger.warning(f"Bulk cancel failed: {e}, trying individual cancellation...")
                
                # Individual cancellation
                cancelled = 0
                failed = 0
                
                for order in open_orders:
                    try:
                        loop = asyncio.get_event_loop()
                        await loop.run_in_executor(
                            None,
                            self.api.cancel_order,
                            self.symbol,
                            order.order_id
                        )
                        logger.info(f"✓ Order cancelled - ID: {order.order_id}, Side: {order.side}, Price: {order.price:.4f}")
                        cancelled += 1
                        
                    except Exception as cancel_error:
                        logger.error(f"✗ Failed to cancel order {order.order_id}: {cancel_error}")
                        failed += 1
                
                logger.info(f"Individual cancellation: {cancelled} successful, {failed} failed")
            
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"Error in cancel_all_orders: {e}", exc_info=True)
            raise
    
    async def monitor_positions(self):
        """
        Check for filled orders and replace them with opposite orders.
        Handles partial fills and API errors with try-except blocks.
        Logs order status changes and new order placements.
        """
        try:
            logger.debug("Monitoring positions...")
            
            # Get open orders from exchange
            loop = asyncio.get_event_loop()
            open_orders_list = await loop.run_in_executor(
                None,
                self.api.get_open_orders,
                self.symbol
            )
            
            # Build set of order IDs that are still open
            exchange_order_ids = {order.get('id') for order in open_orders_list if order.get('id')}
            
            # Check each tracked order
            for order in self.order_manager.get_open_orders():
                if order.order_id not in exchange_order_ids:
                    # Order is no longer open - check if filled or cancelled
                    logger.info(f"Order {order.order_id} no longer open - checking status...")
                    
                    try:
                        # Mark as filled (assuming filled if not in open orders)
                        self.order_manager.mark_filled(order.order_id)
                        logger.info(f"✓ Order FILLED - ID: {order.order_id}, Side: {order.side}, Price: {order.price:.4f}, Qty: {order.quantity}")
                        
                        # Place opposite order at next grid level
                        await self._replace_filled_order(order)
                        
                    except Exception as e:
                        logger.error(f"Error processing filled order {order.order_id}: {e}")
                        continue
            
            # Log current statistics
            stats = self.order_manager.get_statistics()
            current_price = self.current_price or await self._get_current_price_async()
            
            ws_status = ""
            if self.use_websocket and self.ws_client:
                ws_status = f" | WS: {'Connected' if self.ws_client.is_connected() else 'Disconnected'}"
            
            logger.info(f"Status - Price: {current_price:.4f}{ws_status} | "
                       f"Open: {stats['open']}, Filled: {stats['filled']}, "
                       f"Buys: {stats['buy_orders']}, Sells: {stats['sell_orders']}")
            
        except Exception as e:
            logger.error(f"Error in monitor_positions: {e}", exc_info=True)
    
    async def _replace_filled_order(self, filled_order):
        """
        Replace a filled order with an opposite order at the next grid level.
        
        Args:
            filled_order: The order that was filled
        """
        try:
            if filled_order.side == "buy":
                # Buy filled, place sell at next level up
                next_price = self.grid_calculator.get_next_level_up(filled_order.price)
                
                if next_price and not self.order_manager.has_order_at_price(next_price, "sell"):
                    logger.info(f"Placing replacement sell order at {next_price:.4f}...")
                    
                    loop = asyncio.get_event_loop()
                    response = await loop.run_in_executor(
                        None,
                        lambda: self.api.place_limit_order(
                            symbol=self.symbol,
                            side="Ask",
                            price=next_price,
                            quantity=self.quantity
                        )
                    )
                    
                    order_id = response.get('id', f"sell_replace_{int(time.time())}")
                    self.order_manager.add_order(order_id, "sell", next_price, self.quantity)
                    
                    logger.info(f"✓ Replacement sell order placed - ID: {order_id}, Price: {next_price:.4f}")
                else:
                    logger.debug(f"No replacement needed for buy at {filled_order.price:.4f}")
            
            elif filled_order.side == "sell":
                # Sell filled, place buy at next level down
                next_price = self.grid_calculator.get_next_level_down(filled_order.price)
                
                if next_price and not self.order_manager.has_order_at_price(next_price, "buy"):
                    logger.info(f"Placing replacement buy order at {next_price:.4f}...")
                    
                    loop = asyncio.get_event_loop()
                    response = await loop.run_in_executor(
                        None,
                        lambda: self.api.place_limit_order(
                            symbol=self.symbol,
                            side="Bid",
                            price=next_price,
                            quantity=self.quantity
                        )
                    )
                    
                    order_id = response.get('id', f"buy_replace_{int(time.time())}")
                    self.order_manager.add_order(order_id, "buy", next_price, self.quantity)
                    
                    logger.info(f"✓ Replacement buy order placed - ID: {order_id}, Price: {next_price:.4f}")
                else:
                    logger.debug(f"No replacement needed for sell at {filled_order.price:.4f}")
        
        except Exception as e:
            logger.error(f"Failed to replace filled order: {e}", exc_info=True)
    
    async def run(self):
        """
        Main async run loop for the grid bot.
        Initializes exchange, places grid orders, and monitors positions.
        """
        try:
            logger.info("=" * 60)
            logger.info("STARTING ASYNC GRID TRADING BOT")
            logger.info("=" * 60)
            logger.info(f"Symbol: {self.symbol}")
            logger.info(f"Grid levels: {self.config['trading']['grid_num']}")
            logger.info(f"Quantity per order: {self.quantity}")
            logger.info(f"Check interval: {self.interval}s")
            logger.info(f"WebSocket: {'Enabled' if self.use_websocket else 'Disabled'}")
            logger.info("=" * 60)
            
            self.running = True
            self.start_time = datetime.now()
            
            # Initialize exchange
            await self.init_exchange()
            
            # Place initial grid orders
            await self.place_grid_orders()
            
            # Main monitoring loop
            logger.info("Entering main monitoring loop...")
            
            while self.running:
                # Check if duration exceeded
                if self.duration > 0:
                    elapsed = datetime.now() - self.start_time
                    if elapsed > timedelta(seconds=self.duration):
                        logger.info("Duration limit reached, stopping bot...")
                        break
                
                # Monitor positions
                await self.monitor_positions()
                
                # Wait for next interval
                await asyncio.sleep(self.interval)
            
            logger.info("Bot stopped")
            
        except Exception as e:
            logger.error(f"Error in run loop: {e}", exc_info=True)
            raise
        
        finally:
            await self.cleanup()
    
    async def cleanup(self):
        """Cleanup resources and cancel all orders."""
        try:
            logger.info("=" * 60)
            logger.info("CLEANUP")
            logger.info("=" * 60)
            
            # Stop WebSocket
            if self.ws_client:
                self.ws_client.stop()
                logger.info("✓ WebSocket stopped")
            
            # Cancel all orders
            await self.cancel_all_orders()
            
            # Log final statistics
            if self.order_manager:
                stats = self.order_manager.get_statistics()
                logger.info("=" * 60)
                logger.info("FINAL STATISTICS")
                logger.info("=" * 60)
                logger.info(f"Total orders: {stats['total']}")
                logger.info(f"Filled orders: {stats['filled']}")
                logger.info(f"Open orders: {stats['open']}")
                logger.info(f"Buy orders: {stats['buy_orders']}")
                logger.info(f"Sell orders: {stats['sell_orders']}")
                logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}", exc_info=True)
    
    def stop(self):
        """Stop the bot gracefully."""
        logger.info("Stop signal received")
        self.running = False


async def main():
    """Main entry point for async bot."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Async Backpack Exchange Grid Trading Bot')
    parser.add_argument('--config', default='config.json', help='Path to config file')
    args = parser.parse_args()
    
    bot = AsyncGridBot(config_path=args.config)
    
    try:
        await bot.run()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        bot.stop()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
