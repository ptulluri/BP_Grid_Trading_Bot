"""
Async Grid Trading Bot for Backpack Exchange
Main runnable script with async implementation.
"""

import asyncio
import json
import logging
import signal
import sys
import time
from typing import Dict, Any, Optional
from datetime import datetime

from grid_calculator import GridCalculator
from backpack_api import BackpackAPI
from order_manager import OrderManager
from websocket_client import BackpackWebSocket
from risk_manager import RiskManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('grid_bot.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class GridBot:
    """Async Grid Trading Bot for Backpack Exchange."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize grid bot.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.running = False
        self.shutdown_event = asyncio.Event()
        
        # Components
        self.api: Optional[BackpackAPI] = None
        self.grid_calculator: Optional[GridCalculator] = None
        self.order_manager: Optional[OrderManager] = None
        self.ws_client: Optional[BackpackWebSocket] = None
        
        # Trading parameters
        self.symbol = config['trading']['symbol']
        self.quantity = config['trading']['quantity']
        self.monitor_interval = config['trading'].get('interval', 60)
        self.use_websocket = config['trading'].get('use_websocket', True)
        self.current_price: Optional[float] = None
        
        # Dry-run mode
        self.dry_run = config['trading'].get('dry_run', False)
        
        # Risk manager
        self.risk_manager: Optional[RiskManager] = None
        
        logger.info(f"GridBot initialized for {self.symbol}")
        if self.dry_run:
            logger.warning("🔶 DRY-RUN MODE ENABLED - No real orders will be placed!")
    
    def _on_price_update(self, price: float):
        """Callback for WebSocket price updates."""
        self.current_price = price
        logger.debug(f"Price update: {price:.4f}")
    
    async def init_bot(self):
        """Initialize bot components from config."""
        try:
            logger.info("=" * 70)
            logger.info("INITIALIZING GRID BOT")
            logger.info("=" * 70)
            
            # Initialize API client
            self.api = BackpackAPI(
                api_key=self.config['api']['api_key'],
                api_secret=self.config['api']['api_secret'],
                base_url=self.config['api']['base_url']
            )
            logger.info("✓ API client initialized")
            
            # Initialize order manager
            self.order_manager = OrderManager(self.symbol)
            logger.info("✓ Order manager initialized")
            
            # Initialize risk manager
            self.risk_manager = RiskManager(self.config)
            logger.info("✓ Risk manager initialized")
            
            # Initialize WebSocket if enabled
            if self.use_websocket:
                self.ws_client = BackpackWebSocket(
                    symbol=self.symbol,
                    on_price_update=self._on_price_update
                )
                self.ws_client.start()
                await asyncio.sleep(2)  # Wait for connection
                logger.info("✓ WebSocket connected")
            
            # Get current price
            current_price = await self._get_current_price()
            logger.info(f"✓ Current price: {current_price:.4f}")
            
            # Initialize grid calculator
            if self.config['trading']['auto_price']:
                price_range = self.config['trading']['price_range']
                grid_lower, grid_upper = GridCalculator.calculate_auto_price_range(
                    current_price, price_range
                )
                logger.info(f"Auto-price mode: ±{price_range*100}%")
            else:
                grid_lower = self.config['trading']['grid_lower']
                grid_upper = self.config['trading']['grid_upper']
                logger.info(f"Fixed grid mode")
            
            self.grid_calculator = GridCalculator(
                grid_upper=grid_upper,
                grid_lower=grid_lower,
                grid_num=self.config['trading']['grid_num']
            )
            
            logger.info(f"✓ Grid: {grid_lower:.2f} - {grid_upper:.2f} ({self.config['trading']['grid_num']} levels)")
            logger.info(f"✓ Grid spacing: {self.grid_calculator.get_grid_spacing():.2f}")
            
            # Set initial balance for risk management
            if self.risk_manager:
                # Estimate initial balance (would need actual balance from API in production)
                estimated_balance = 10000.0  # TODO: Get from API
                self.risk_manager.set_initial_balance(estimated_balance)
            
            logger.info("=" * 70)
            
        except Exception as e:
            logger.error(f"Failed to initialize bot: {e}", exc_info=True)
            raise
    
    async def _get_current_price(self) -> float:
        """Get current market price."""
        # Try WebSocket first
        if self.use_websocket and self.ws_client:
            ws_price = self.ws_client.get_last_price()
            if ws_price is not None:
                return ws_price
        
        # Fall back to REST API
        try:
            loop = asyncio.get_event_loop()
            ticker = await loop.run_in_executor(None, self.api.get_ticker, self.symbol)
            price = float(ticker.get('lastPrice', 0))
            if price == 0:
                raise ValueError("Invalid price from API")
            return price
        except Exception as e:
            logger.error(f"Failed to get price: {e}")
            raise
    
    async def place_initial_grid(self):
        """Place initial grid orders."""
        try:
            logger.info("=" * 70)
            logger.info("PLACING INITIAL GRID")
            logger.info("=" * 70)
            
            current_price = await self._get_current_price()
            logger.info(f"Current price: {current_price:.4f}")
            
            # Check grid health
            if not self.grid_calculator.is_within_grid(current_price):
                logger.error(f"Price {current_price:.4f} outside grid boundaries!")
                logger.error(f"Grid range: {self.grid_calculator.grid_lower:.2f} - {self.grid_calculator.grid_upper:.2f}")
                return
            
            # Get balanced levels
            buy_levels, sell_levels = self.grid_calculator.calculate_balanced_buy_sell_levels(current_price)
            
            logger.info(f"Placing {len(buy_levels)} buy orders and {len(sell_levels)} sell orders...")
            
            # Place buy orders
            buy_success = 0
            for i, price in enumerate(buy_levels, 1):
                try:
                    logger.info(f"[{i}/{len(buy_levels)}] Placing BUY at {price:.4f}...")
                    
                    if self.dry_run:
                        # Dry-run mode: log only, don't place real order
                        order_id = f"DRY_buy_{int(time.time())}_{i}"
                        logger.info(f"  🔶 DRY-RUN: Would place BUY | Price: {price:.4f} | Qty: {self.quantity}")
                    else:
                        # Real mode: place actual order
                        loop = asyncio.get_event_loop()
                        response = await loop.run_in_executor(
                            None,
                            lambda p=price: self.api.place_limit_order(
                                symbol=self.symbol,
                                side="Bid",
                                price=p,
                                quantity=self.quantity
                            )
                        )
                        order_id = response.get('id', f"buy_{int(time.time())}_{i}")
                        logger.info(f"  ✓ BUY order placed | ID: {order_id} | Price: {price:.4f} | Qty: {self.quantity}")
                    
                    self.order_manager.add_order(order_id, "buy", price, self.quantity)
                    buy_success += 1
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    logger.error(f"  ✗ Failed to place BUY at {price:.4f}: {e}")
                    if self.risk_manager:
                        self.risk_manager.send_alert("ORDER ERROR", f"Failed to place BUY order at {price:.4f}: {e}")
            
            # Place sell orders
            sell_success = 0
            for i, price in enumerate(sell_levels, 1):
                try:
                    logger.info(f"[{i}/{len(sell_levels)}] Placing SELL at {price:.4f}...")
                    
                    if self.dry_run:
                        # Dry-run mode: log only, don't place real order
                        order_id = f"DRY_sell_{int(time.time())}_{i}"
                        logger.info(f"  🔶 DRY-RUN: Would place SELL | Price: {price:.4f} | Qty: {self.quantity}")
                    else:
                        # Real mode: place actual order
                        loop = asyncio.get_event_loop()
                        response = await loop.run_in_executor(
                            None,
                            lambda p=price: self.api.place_limit_order(
                                symbol=self.symbol,
                                side="Ask",
                                price=p,
                                quantity=self.quantity
                            )
                        )
                        order_id = response.get('id', f"sell_{int(time.time())}_{i}")
                        logger.info(f"  ✓ SELL order placed | ID: {order_id} | Price: {price:.4f} | Qty: {self.quantity}")
                    
                    self.order_manager.add_order(order_id, "sell", price, self.quantity)
                    sell_success += 1
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    logger.error(f"  ✗ Failed to place SELL at {price:.4f}: {e}")
                    if self.risk_manager:
                        self.risk_manager.send_alert("ORDER ERROR", f"Failed to place SELL order at {price:.4f}: {e}")
            
            logger.info("=" * 70)
            logger.info(f"GRID PLACEMENT COMPLETE: {buy_success} buys, {sell_success} sells")
            logger.info("=" * 70)
            
        except Exception as e:
            logger.error(f"Error placing initial grid: {e}", exc_info=True)
            raise
    
    async def monitor_and_rebalance(self):
        """Monitor positions and rebalance grid (cancel unfilled, replace on fills)."""
        try:
            # Check risk controls
            if self.risk_manager and self.risk_manager.is_paused():
                logger.warning(f"⚠️ TRADING PAUSED: {self.risk_manager.get_pause_reason()}")
                return
            
            logger.debug("Monitoring and rebalancing...")
            
            # Get current price for risk checks
            current_price = await self._get_current_price()
            
            # Check volatility
            if self.risk_manager and self.risk_manager.check_volatility(current_price):
                logger.error("⚠️ Trading paused due to high volatility")
                return
            
            # Check drawdown (would need actual balance from API)
            # For now, using estimated portfolio value
            estimated_portfolio = 10000.0  # TODO: Calculate from actual balances
            if self.risk_manager and self.risk_manager.check_drawdown(estimated_portfolio):
                logger.error("⚠️ Trading paused due to excessive drawdown")
                return
            
            # Get open orders from exchange
            loop = asyncio.get_event_loop()
            exchange_orders = await loop.run_in_executor(
                None,
                self.api.get_open_orders,
                self.symbol
            )
            
            exchange_order_ids = {order.get('id') for order in exchange_orders if order.get('id')}
            
            # Check tracked orders
            filled_orders = []
            for order in self.order_manager.get_open_orders():
                if order.order_id not in exchange_order_ids:
                    # Order filled
                    self.order_manager.mark_filled(order.order_id)
                    filled_orders.append(order)
                    logger.info(f"🎯 ORDER FILLED | ID: {order.order_id} | Side: {order.side.upper()} | Price: {order.price:.4f}")
            
            # Replace filled orders
            for filled_order in filled_orders:
                try:
                    if filled_order.side == "buy":
                        # Buy filled -> place sell above
                        next_price = self.grid_calculator.get_next_level_up(filled_order.price)
                        if next_price and not self.order_manager.has_order_at_price(next_price, "sell"):
                            logger.info(f"  → Replacing with SELL at {next_price:.4f}...")
                            
                            if self.dry_run:
                                order_id = f"DRY_sell_repl_{int(time.time())}"
                                logger.info(f"  🔶 DRY-RUN: Would place SELL | Price: {next_price:.4f}")
                            else:
                                response = await loop.run_in_executor(
                                    None,
                                    lambda: self.api.place_limit_order(
                                        symbol=self.symbol,
                                        side="Ask",
                                        price=next_price,
                                        quantity=self.quantity
                                    )
                                )
                                order_id = response.get('id', f"sell_repl_{int(time.time())}")
                                logger.info(f"  ✓ Replacement SELL placed | ID: {order_id} | Price: {next_price:.4f}")
                            
                            self.order_manager.add_order(order_id, "sell", next_price, self.quantity)
                    
                    elif filled_order.side == "sell":
                        # Sell filled -> place buy below
                        next_price = self.grid_calculator.get_next_level_down(filled_order.price)
                        if next_price and not self.order_manager.has_order_at_price(next_price, "buy"):
                            logger.info(f"  → Replacing with BUY at {next_price:.4f}...")
                            
                            if self.dry_run:
                                order_id = f"DRY_buy_repl_{int(time.time())}"
                                logger.info(f"  🔶 DRY-RUN: Would place BUY | Price: {next_price:.4f}")
                            else:
                                response = await loop.run_in_executor(
                                    None,
                                    lambda: self.api.place_limit_order(
                                        symbol=self.symbol,
                                        side="Bid",
                                        price=next_price,
                                        quantity=self.quantity
                                    )
                                )
                                order_id = response.get('id', f"buy_repl_{int(time.time())}")
                                logger.info(f"  ✓ Replacement BUY placed | ID: {order_id} | Price: {next_price:.4f}")
                            
                            self.order_manager.add_order(order_id, "buy", next_price, self.quantity)
                
                except Exception as e:
                    logger.error(f"Failed to replace order: {e}")
            
            # Log status
            stats = self.order_manager.get_statistics()
            current_price = self.current_price or await self._get_current_price()
            
            ws_status = "Connected" if (self.ws_client and self.ws_client.is_connected()) else "Disconnected"
            mode_status = "DRY-RUN" if self.dry_run else "LIVE"
            risk_status = f" | PAUSED: {self.risk_manager.get_pause_reason()}" if (self.risk_manager and self.risk_manager.is_paused()) else ""
            
            logger.info(f"📊 STATUS | Mode: {mode_status} | Price: {current_price:.4f} | WS: {ws_status} | "
                       f"Open: {stats['open']} | Filled: {stats['filled']} | "
                       f"Buys: {stats['buy_orders']} | Sells: {stats['sell_orders']}{risk_status}")
            
        except Exception as e:
            logger.error(f"Error in monitor_and_rebalance: {e}", exc_info=True)
    
    async def cleanup(self):
        """Cleanup and cancel all orders."""
        try:
            logger.info("=" * 70)
            logger.info("CLEANUP - Cancelling all orders...")
            logger.info("=" * 70)
            
            # Stop WebSocket
            if self.ws_client:
                self.ws_client.stop()
                logger.info("✓ WebSocket stopped")
            
            # Cancel all orders
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self.api.cancel_all_orders, self.symbol)
                logger.info("✓ All orders cancelled")
            except Exception as e:
                logger.error(f"Error cancelling orders: {e}")
            
            # Final stats
            if self.order_manager:
                stats = self.order_manager.get_statistics()
                logger.info("=" * 70)
                logger.info("FINAL STATISTICS")
                logger.info("=" * 70)
                logger.info(f"Total orders: {stats['total']}")
                logger.info(f"Filled orders: {stats['filled']}")
                logger.info(f"Buy orders: {stats['buy_orders']}")
                logger.info(f"Sell orders: {stats['sell_orders']}")
                logger.info("=" * 70)
        
        except Exception as e:
            logger.error(f"Error during cleanup: {e}", exc_info=True)
    
    def request_shutdown(self):
        """Request graceful shutdown."""
        logger.info("Shutdown requested...")
        self.running = False
        self.shutdown_event.set()


async def main():
    """
    Main async function:
    - Load config
    - Init bot
    - Place initial grid
    - Loop every 60s to monitor and rebalance
    - Run indefinitely with signal handling for graceful shutdown
    """
    
    # Load config
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
        logger.info("Configuration loaded")
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        sys.exit(1)
    
    # Create bot
    bot = GridBot(config)
    
    # Setup signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        logger.info(f"Signal {signum} received (Ctrl+C)")
        bot.request_shutdown()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        logger.info("=" * 70)
        logger.info("BACKPACK EXCHANGE GRID TRADING BOT")
        logger.info("=" * 70)
        logger.info(f"Symbol: {bot.symbol}")
        logger.info(f"Quantity: {bot.quantity}")
        logger.info(f"Monitor interval: {bot.monitor_interval}s")
        logger.info(f"Mode: {'DRY-RUN (No real orders)' if bot.dry_run else 'LIVE TRADING'}")
        logger.info(f"Press Ctrl+C to stop")
        logger.info("=" * 70)
        
        # Initialize bot
        await bot.init_bot()
        
        # Place initial grid
        await bot.place_initial_grid()
        
        # Set running flag
        bot.running = True
        
        # Main loop - monitor and rebalance every 60s
        logger.info("=" * 70)
        logger.info(f"ENTERING MONITORING LOOP (every {bot.monitor_interval}s)")
        logger.info("=" * 70)
        
        while bot.running:
            try:
                # Monitor and rebalance
                await bot.monitor_and_rebalance()
                
                # Wait for next interval or shutdown
                try:
                    await asyncio.wait_for(
                        bot.shutdown_event.wait(),
                        timeout=bot.monitor_interval
                    )
                    # Shutdown requested
                    break
                except asyncio.TimeoutError:
                    # Normal timeout, continue loop
                    pass
            
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                await asyncio.sleep(5)  # Brief pause before retry
        
        logger.info("Main loop exited")
    
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt")
    
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    
    finally:
        # Cleanup
        await bot.cleanup()
        logger.info("Bot shutdown complete")


if __name__ == "__main__":
    """
    Run the bot:
    python grid_bot.py
    
    Test on testnet by configuring testnet API endpoint in config.json
    Monitor console for order placements and fills
    """
    asyncio.run(main())
