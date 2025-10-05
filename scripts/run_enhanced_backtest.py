#!/usr/bin/env python3
"""
Enhanced Backtest Runner
Runs comprehensive backtest with advanced performance metrics and reporting.
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import numpy as np

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import ccxt
except ImportError:
    print("ERROR: ccxt not installed. Install with: pip install ccxt")
    sys.exit(1)

from grid_calculator import GridCalculator
from backtesting.metrics.performance_metrics import PerformanceMetrics
from backtesting.metrics.performance_report import PerformanceReport

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('backtest_enhanced.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class EnhancedBacktester:
    """
    Enhanced backtesting engine with comprehensive performance metrics.
    """
    
    def __init__(self, config: Dict, initial_balance: float = 10000.0):
        """
        Initialize enhanced backtester.
        
        Args:
            config: Trading configuration
            initial_balance: Starting USDC balance
        """
        self.config = config
        self.initial_balance = initial_balance
        
        # Virtual balances
        self.usdt_balance = initial_balance
        self.base_balance = 0.0
        
        # Trading state
        self.orders = []
        self.filled_orders = []
        self.trades = []
        self.equity_curve = [initial_balance]
        self.timestamps = []
        
        # Grid calculator
        self.grid_calculator = None
        
        # Statistics
        self.total_trades = 0
        self.fee_rate = 0.001  # 0.1% per trade
        self.total_fees = 0.0
        
        logger.info(f"Enhanced Backtester initialized with ${initial_balance:,.2f}")
    
    def fetch_historical_data(self, symbol: str, days: int = 30) -> List[List]:
        """
        Fetch OHLCV data from CCXT.
        
        Args:
            symbol: Trading pair (e.g., 'SOL/USDC')
            days: Number of days of historical data
            
        Returns:
            List of OHLCV candles
        """
        try:
            logger.info(f"Fetching {days} days of historical data for {symbol}...")
            
            # Initialize exchange (using Coinbase as data source)
            exchange = ccxt.coinbase({'enableRateLimit': True})
            
            # Calculate timeframe
            since = exchange.parse8601(
                (datetime.now() - timedelta(days=days)).isoformat()
            )
            
            # Fetch OHLCV data (1 hour candles)
            ohlcv = exchange.fetch_ohlcv(symbol, '1h', since=since, limit=1000)
            
            logger.info(f"Fetched {len(ohlcv)} candles")
            return ohlcv
            
        except Exception as e:
            logger.error(f"Failed to fetch historical data: {e}")
            raise
    
    def initialize_grid(self, current_price: float):
        """Initialize grid calculator."""
        grid_lower = self.config['trading']['grid_lower']
        grid_upper = self.config['trading']['grid_upper']
        grid_num = self.config['trading']['grid_num']
        
        self.grid_calculator = GridCalculator(
            grid_upper=grid_upper,
            grid_lower=grid_lower,
            grid_num=grid_num
        )
        
        logger.info(f"Grid initialized: ${grid_lower:.2f} - ${grid_upper:.2f}")
        logger.info(f"Grid levels: {grid_num}")
        logger.info(f"Grid spacing: ${self.grid_calculator.get_grid_spacing():.2f}")
    
    def place_initial_grid(self, current_price: float):
        """Place initial grid orders."""
        if not self.grid_calculator.is_within_grid(current_price):
            logger.warning(
                f"Price ${current_price:.2f} outside grid, "
                f"skipping initial placement"
            )
            return
        
        buy_levels, sell_levels = self.grid_calculator.calculate_balanced_buy_sell_levels(
            current_price
        )
        
        quantity = self.config['trading']['quantity']
        
        # Place buy orders
        for i, price in enumerate(buy_levels):
            order = {
                'id': f"buy_{i}",
                'side': 'buy',
                'price': price,
                'quantity': quantity,
                'filled': False,
                'fill_price': None,
                'fill_time': None,
            }
            self.orders.append(order)
        
        # Place sell orders
        for i, price in enumerate(sell_levels):
            order = {
                'id': f"sell_{i}",
                'side': 'sell',
                'price': price,
                'quantity': quantity,
                'filled': False,
                'fill_price': None,
                'fill_time': None,
            }
            self.orders.append(order)
        
        logger.info(
            f"Placed {len(buy_levels)} buy and {len(sell_levels)} sell orders"
        )
    
    def check_fills(self, candle: List) -> List[Dict]:
        """
        Check if any orders were filled by the candle.
        
        Args:
            candle: [timestamp, open, high, low, close, volume]
            
        Returns:
            List of filled orders
        """
        timestamp, open_price, high, low, close, volume = candle
        filled = []
        
        for order in self.orders:
            if order['filled']:
                continue
            
            # Check if price touched order level
            if order['side'] == "buy" and low <= order['price']:
                order['filled'] = True
                order['fill_price'] = order['price']
                order['fill_time'] = timestamp
                filled.append(order)
                
            elif order['side'] == "sell" and high >= order['price']:
                order['filled'] = True
                order['fill_price'] = order['price']
                order['fill_time'] = timestamp
                filled.append(order)
        
        return filled
    
    def execute_fill(self, order: Dict):
        """Execute a filled order and update balances."""
        cost = order['price'] * order['quantity']
        fee = cost * self.fee_rate
        
        if order['side'] == "buy":
            # Buy: spend USDT, receive base asset
            total_cost = cost + fee
            if self.usdt_balance >= total_cost:
                self.usdt_balance -= total_cost
                self.base_balance += order['quantity']
                self.total_fees += fee
                
                # Record trade with PNL (will be calculated on sell)
                self.trades.append({
                    'time': datetime.fromtimestamp(order['fill_time'] / 1000),
                    'side': order['side'],
                    'price': order['price'],
                    'quantity': order['quantity'],
                    'fee': fee,
                    'pnl': 0,  # Will be updated on corresponding sell
                })
                
                logger.debug(
                    f"BUY filled: {order['quantity']} @ ${order['price']:.2f}, "
                    f"fee: ${fee:.2f}"
                )
            else:
                logger.warning("Insufficient USDT for buy order")
                return
        
        else:  # sell
            # Sell: spend base asset, receive USDT
            if self.base_balance >= order['quantity']:
                self.base_balance -= order['quantity']
                self.usdt_balance += (cost - fee)
                self.total_fees += fee
                
                # Calculate PNL (simplified - assumes FIFO)
                # Find corresponding buy
                buy_price = self._find_avg_buy_price()
                pnl = (order['price'] - buy_price) * order['quantity'] - fee
                
                self.trades.append({
                    'time': datetime.fromtimestamp(order['fill_time'] / 1000),
                    'side': order['side'],
                    'price': order['price'],
                    'quantity': order['quantity'],
                    'fee': fee,
                    'pnl': pnl,
                })
                
                logger.debug(
                    f"SELL filled: {order['quantity']} @ ${order['price']:.2f}, "
                    f"fee: ${fee:.2f}, PNL: ${pnl:.2f}"
                )
            else:
                logger.warning("Insufficient base asset for sell order")
                return
        
        self.total_trades += 1
        self.filled_orders.append(order)
    
    def _find_avg_buy_price(self) -> float:
        """Find average buy price for PNL calculation."""
        buy_trades = [t for t in self.trades if t['side'] == 'buy']
        if not buy_trades:
            return 0.0
        
        total_cost = sum(t['price'] * t['quantity'] for t in buy_trades)
        total_qty = sum(t['quantity'] for t in buy_trades)
        
        return total_cost / total_qty if total_qty > 0 else 0.0
    
    def replace_filled_order(self, filled_order: Dict):
        """Replace a filled order with opposite order at next grid level."""
        if filled_order['side'] == "buy":
            # Buy filled, place sell above
            next_price = self.grid_calculator.get_next_level_up(filled_order['price'])
            if next_price:
                new_order = {
                    'id': f"sell_repl_{self.total_trades}",
                    'side': 'sell',
                    'price': next_price,
                    'quantity': filled_order['quantity'],
                    'filled': False,
                    'fill_price': None,
                    'fill_time': None,
                }
                self.orders.append(new_order)
        
        else:  # sell filled
            # Sell filled, place buy below
            next_price = self.grid_calculator.get_next_level_down(filled_order['price'])
            if next_price:
                new_order = {
                    'id': f"buy_repl_{self.total_trades}",
                    'side': 'buy',
                    'price': next_price,
                    'quantity': filled_order['quantity'],
                    'filled': False,
                    'fill_price': None,
                    'fill_time': None,
                }
                self.orders.append(new_order)
    
    def update_equity_curve(self, current_price: float, timestamp: int):
        """Update equity curve with current portfolio value."""
        portfolio_value = self.usdt_balance + (self.base_balance * current_price)
        self.equity_curve.append(portfolio_value)
        self.timestamps.append(datetime.fromtimestamp(timestamp / 1000))
    
    def run_backtest(self, symbol: str, days: int = 30):
        """
        Run the backtest simulation.
        
        Args:
            symbol: Trading pair
            days: Number of days to backtest
        """
        logger.info("=" * 80)
        logger.info("STARTING ENHANCED BACKTEST")
        logger.info("=" * 80)
        logger.info(f"Symbol: {symbol}")
        logger.info(f"Period: {days} days")
        logger.info(f"Initial balance: ${self.initial_balance:,.2f}")
        logger.info("=" * 80)
        
        # Fetch historical data
        ohlcv = self.fetch_historical_data(symbol, days)
        
        if not ohlcv:
            logger.error("No historical data available")
            return None
        
        # Initialize grid with first price
        first_price = ohlcv[0][4]  # close price
        self.initialize_grid(first_price)
        
        # Place initial grid
        self.place_initial_grid(first_price)
        
        # Replay historical data
        logger.info("Replaying historical data...")
        
        for i, candle in enumerate(ohlcv):
            timestamp, open_price, high, low, close, volume = candle
            
            # Check for fills
            filled = self.check_fills(candle)
            
            # Execute fills and replace orders
            for order in filled:
                self.execute_fill(order)
                self.replace_filled_order(order)
            
            # Update equity curve
            self.update_equity_curve(close, timestamp)
            
            # Log progress every 100 candles
            if i % 100 == 0 and i > 0:
                current_value = self.equity_curve[-1]
                pnl = current_value - self.initial_balance
                logger.info(
                    f"Progress: {i}/{len(ohlcv)} candles, "
                    f"Price: ${close:.2f}, "
                    f"Portfolio: ${current_value:,.2f}, "
                    f"PNL: ${pnl:,.2f}"
                )
        
        # Calculate final metrics
        final_price = ohlcv[-1][4]
        final_balance = self.equity_curve[-1]
        
        logger.info("=" * 80)
        logger.info("BACKTEST SIMULATION COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Final price: ${final_price:.2f}")
        logger.info(f"Total trades: {self.total_trades}")
        logger.info(f"Total fees: ${self.total_fees:.2f}")
        logger.info(f"Final portfolio: ${final_balance:,.2f}")
        logger.info(f"Net P&L: ${final_balance - self.initial_balance:,.2f}")
        logger.info("=" * 80)
        
        # Calculate comprehensive metrics
        logger.info("\nCalculating performance metrics...")
        
        metrics = PerformanceMetrics(
            trades=self.trades,
            initial_balance=self.initial_balance,
            final_balance=final_balance,
            equity_curve=self.equity_curve,
            timestamps=self.timestamps,
        )
        
        return metrics


def main():
    """Main backtest entry point."""
    # Load config
    try:
        config_path = Path(__file__).parent.parent / 'config.json'
        with open(config_path, 'r') as f:
            config = json.load(f)
        logger.info("Configuration loaded")
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return
    
    # Convert symbol format (SOL_USDC -> SOL/USDC for CCXT)
    symbol = config['trading']['symbol'].replace('_', '/')
    
    # Create backtest
    backtest = EnhancedBacktester(config, initial_balance=10000.0)
    
    # Run backtest
    try:
        metrics = backtest.run_backtest(symbol, days=90)
        
        if metrics is None:
            logger.error("Backtest failed to produce metrics")
            return
        
        # Generate comprehensive report
        logger.info("\nGenerating performance report...")
        report = PerformanceReport(metrics)
        
        # Print to console
        print("\n")
        report.print_summary()
        
        # Create results directory
        results_dir = Path(__file__).parent.parent / 'results'
        results_dir.mkdir(exist_ok=True)
        
        # Export results
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        json_path = results_dir / f'backtest_metrics_{timestamp}.json'
        csv_path = results_dir / f'backtest_metrics_{timestamp}.csv'
        md_path = results_dir / f'BACKTEST_REPORT_{timestamp}.md'
        
        report.export_to_json(str(json_path))
        report.export_to_csv(str(csv_path))
        report.export_to_markdown(str(md_path))
        
        logger.info(f"\nReports saved to:")
        logger.info(f"  - {json_path}")
        logger.info(f"  - {csv_path}")
        logger.info(f"  - {md_path}")
        
        # Final recommendation
        print("\n" + "=" * 80)
        if metrics.meets_all_targets():
            print("✓ STRATEGY APPROVED - All targets met!")
            print("  Ready for live trading consideration.")
        else:
            print("⚠ STRATEGY NEEDS OPTIMIZATION")
            print("  Some targets not met. Review metrics and adjust parameters.")
        print("=" * 80)
        
    except Exception as e:
        logger.error(f"Backtest failed: {e}", exc_info=True)


if __name__ == "__main__":
    """
    Run enhanced backtest:
    python scripts/run_enhanced_backtest.py
    
    This will:
    - Fetch last 30 days of OHLCV data
    - Simulate grid trading strategy
    - Calculate 20+ performance metrics
    - Generate comprehensive reports (JSON, CSV, Markdown)
    - Provide pass/fail validation against targets
    """
    main()
