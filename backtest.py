"""
Grid Bot Backtesting Script
Simulates grid trading strategy on historical data using CCXT.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import ccxt

from grid_calculator import GridCalculator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('backtest.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class VirtualOrder:
    """Represents a virtual order in the backtest."""
    
    def __init__(self, order_id: str, side: str, price: float, quantity: float):
        self.order_id = order_id
        self.side = side  # 'buy' or 'sell'
        self.price = price
        self.quantity = quantity
        self.filled = False
        self.fill_price = None
        self.fill_time = None
    
    def __repr__(self):
        return f"Order({self.side}, {self.price:.2f}, {self.quantity}, filled={self.filled})"


class GridBotBacktest:
    """Backtesting engine for grid trading strategy."""
    
    def __init__(self, config: Dict, initial_balance: float = 10000.0):
        """
        Initialize backtest.
        
        Args:
            config: Trading configuration
            initial_balance: Starting USDT balance
        """
        self.config = config
        self.initial_balance = initial_balance
        
        # Virtual balances
        self.usdt_balance = initial_balance
        self.base_balance = 0.0  # e.g., SOL
        
        # Trading state
        self.orders: List[VirtualOrder] = []
        self.filled_orders: List[VirtualOrder] = []
        self.trades: List[Dict] = []
        
        # Grid calculator
        self.grid_calculator = None
        
        # Statistics
        self.total_trades = 0
        self.winning_trades = 0
        self.total_fees = 0.0
        self.fee_rate = 0.001  # 0.1% per trade
        
        logger.info(f"Backtest initialized with {initial_balance} USDT")
    
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
            
            # Initialize exchange (using Binance as data source)
            exchange = ccxt.binance({
                'enableRateLimit': True,
            })
            
            # Calculate timeframe
            since = exchange.parse8601((datetime.now() - timedelta(days=days)).isoformat())
            
            # Fetch OHLCV data (1 hour candles)
            ohlcv = exchange.fetch_ohlcv(symbol, '1h', since=since, limit=1000)
            
            logger.info(f"Fetched {len(ohlcv)} candles")
            return ohlcv
            
        except Exception as e:
            logger.error(f"Failed to fetch historical data: {e}")
            raise
    
    def initialize_grid(self, current_price: float):
        """Initialize grid calculator based on config."""
        if self.config['trading']['auto_price']:
            price_range = self.config['trading']['price_range']
            grid_lower, grid_upper = GridCalculator.calculate_auto_price_range(
                current_price, price_range
            )
        else:
            grid_lower = self.config['trading']['grid_lower']
            grid_upper = self.config['trading']['grid_upper']
        
        self.grid_calculator = GridCalculator(
            grid_upper=grid_upper,
            grid_lower=grid_lower,
            grid_num=self.config['trading']['grid_num']
        )
        
        logger.info(f"Grid initialized: {grid_lower:.2f} - {grid_upper:.2f}")
    
    def place_initial_grid(self, current_price: float):
        """Place initial grid orders."""
        if not self.grid_calculator.is_within_grid(current_price):
            logger.warning(f"Price {current_price:.2f} outside grid, skipping initial placement")
            return
        
        buy_levels, sell_levels = self.grid_calculator.calculate_balanced_buy_sell_levels(current_price)
        
        quantity = self.config['trading']['quantity']
        
        # Place buy orders
        for i, price in enumerate(buy_levels):
            order = VirtualOrder(f"buy_{i}", "buy", price, quantity)
            self.orders.append(order)
        
        # Place sell orders
        for i, price in enumerate(sell_levels):
            order = VirtualOrder(f"sell_{i}", "sell", price, quantity)
            self.orders.append(order)
        
        logger.info(f"Placed {len(buy_levels)} buy and {len(sell_levels)} sell orders")
    
    def check_fills(self, candle: List) -> List[VirtualOrder]:
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
            if order.filled:
                continue
            
            # Check if price touched order level
            if order.side == "buy" and low <= order.price:
                # Buy order filled
                order.filled = True
                order.fill_price = order.price
                order.fill_time = timestamp
                filled.append(order)
                
            elif order.side == "sell" and high >= order.price:
                # Sell order filled
                order.filled = True
                order.fill_price = order.price
                order.fill_time = timestamp
                filled.append(order)
        
        return filled
    
    def execute_fill(self, order: VirtualOrder):
        """Execute a filled order and update balances."""
        cost = order.price * order.quantity
        fee = cost * self.fee_rate
        
        if order.side == "buy":
            # Buy: spend USDT, receive base asset
            total_cost = cost + fee
            if self.usdt_balance >= total_cost:
                self.usdt_balance -= total_cost
                self.base_balance += order.quantity
                self.total_fees += fee
                
                logger.debug(f"BUY filled: {order.quantity} @ {order.price:.2f}, fee: {fee:.2f}")
            else:
                logger.warning(f"Insufficient USDT for buy order")
                return
        
        else:  # sell
            # Sell: spend base asset, receive USDT
            if self.base_balance >= order.quantity:
                self.base_balance -= order.quantity
                self.usdt_balance += (cost - fee)
                self.total_fees += fee
                
                logger.debug(f"SELL filled: {order.quantity} @ {order.price:.2f}, fee: {fee:.2f}")
            else:
                logger.warning(f"Insufficient base asset for sell order")
                return
        
        # Record trade
        self.trades.append({
            'time': datetime.fromtimestamp(order.fill_time / 1000),
            'side': order.side,
            'price': order.price,
            'quantity': order.quantity,
            'fee': fee
        })
        
        self.total_trades += 1
        self.filled_orders.append(order)
    
    def replace_filled_order(self, filled_order: VirtualOrder):
        """Replace a filled order with opposite order at next grid level."""
        if filled_order.side == "buy":
            # Buy filled, place sell above
            next_price = self.grid_calculator.get_next_level_up(filled_order.price)
            if next_price:
                new_order = VirtualOrder(
                    f"sell_repl_{self.total_trades}",
                    "sell",
                    next_price,
                    filled_order.quantity
                )
                self.orders.append(new_order)
                logger.debug(f"Replaced buy with sell at {next_price:.2f}")
        
        else:  # sell filled
            # Sell filled, place buy below
            next_price = self.grid_calculator.get_next_level_down(filled_order.price)
            if next_price:
                new_order = VirtualOrder(
                    f"buy_repl_{self.total_trades}",
                    "buy",
                    next_price,
                    filled_order.quantity
                )
                self.orders.append(new_order)
                logger.debug(f"Replaced sell with buy at {next_price:.2f}")
    
    def calculate_pnl(self, current_price: float) -> Tuple[float, float]:
        """
        Calculate current PNL.
        
        Args:
            current_price: Current market price
            
        Returns:
            (realized_pnl, unrealized_pnl)
        """
        # Current portfolio value
        portfolio_value = self.usdt_balance + (self.base_balance * current_price)
        
        # Realized PNL (from completed trades)
        realized_pnl = portfolio_value - self.initial_balance
        
        # Unrealized PNL (from open positions)
        unrealized_pnl = self.base_balance * current_price
        
        return realized_pnl, unrealized_pnl
    
    def calculate_win_rate(self) -> float:
        """Calculate win rate from completed round trips."""
        if len(self.trades) < 2:
            return 0.0
        
        # Find buy-sell pairs
        buys = [t for t in self.trades if t['side'] == 'buy']
        sells = [t for t in self.trades if t['side'] == 'sell']
        
        wins = 0
        total_pairs = min(len(buys), len(sells))
        
        for i in range(total_pairs):
            buy_price = buys[i]['price']
            sell_price = sells[i]['price']
            if sell_price > buy_price:
                wins += 1
        
        return (wins / total_pairs * 100) if total_pairs > 0 else 0.0
    
    def run_backtest(self, symbol: str, days: int = 30):
        """
        Run the backtest simulation.
        
        Args:
            symbol: Trading pair
            days: Number of days to backtest
        """
        logger.info("=" * 70)
        logger.info("STARTING BACKTEST")
        logger.info("=" * 70)
        logger.info(f"Symbol: {symbol}")
        logger.info(f"Period: {days} days")
        logger.info(f"Initial balance: {self.initial_balance} USDT")
        logger.info("=" * 70)
        
        # Fetch historical data
        ohlcv = self.fetch_historical_data(symbol, days)
        
        if not ohlcv:
            logger.error("No historical data available")
            return
        
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
            
            # Log progress every 100 candles
            if i % 100 == 0:
                pnl, _ = self.calculate_pnl(close)
                logger.info(f"Progress: {i}/{len(ohlcv)} candles, Price: {close:.2f}, PNL: {pnl:.2f} USDT")
        
        # Final results
        final_price = ohlcv[-1][4]
        realized_pnl, unrealized_pnl = self.calculate_pnl(final_price)
        win_rate = self.calculate_win_rate()
        
        logger.info("=" * 70)
        logger.info("BACKTEST COMPLETE")
        logger.info("=" * 70)
        logger.info(f"Final price: {final_price:.2f}")
        logger.info(f"Total trades: {self.total_trades}")
        logger.info(f"Win rate: {win_rate:.2f}%")
        logger.info(f"Total fees: {self.total_fees:.2f} USDT")
        logger.info(f"Net profit: {realized_pnl:.2f} USDT ({(realized_pnl/self.initial_balance*100):.2f}%)")
        logger.info(f"Final balance: {self.usdt_balance:.2f} USDT + {self.base_balance:.4f} base")
        logger.info(f"Portfolio value: {self.usdt_balance + (self.base_balance * final_price):.2f} USDT")
        logger.info("=" * 70)
        
        # Print summary
        self.print_summary(final_price, realized_pnl, win_rate)
    
    def print_summary(self, final_price: float, net_profit: float, win_rate: float):
        """Print simple summary."""
        print("\n" + "=" * 70)
        print("BACKTEST SUMMARY")
        print("=" * 70)
        print(f"Total Trades:     {self.total_trades}")
        print(f"Win Rate:         {win_rate:.2f}%")
        print(f"Net Profit:       {net_profit:.2f} USDT ({(net_profit/self.initial_balance*100):.2f}%)")
        print(f"Total Fees:       {self.total_fees:.2f} USDT")
        print(f"Final Portfolio:  {self.usdt_balance + (self.base_balance * final_price):.2f} USDT")
        print("=" * 70)
        
        if net_profit > 0:
            print("✓ Strategy was PROFITABLE in backtest")
        else:
            print("✗ Strategy was NOT profitable in backtest")
        
        print("\nNote: Past performance does not guarantee future results.")
        print("=" * 70 + "\n")


def main():
    """Main backtest entry point."""
    # Load config
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
        logger.info("Configuration loaded")
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return
    
    # Convert symbol format (SOL_USDC -> SOL/USDC for CCXT)
    symbol = config['trading']['symbol'].replace('_', '/')
    
    # Create backtest
    backtest = GridBotBacktest(config, initial_balance=10000.0)
    
    # Run backtest
    try:
        backtest.run_backtest(symbol, days=30)
    except Exception as e:
        logger.error(f"Backtest failed: {e}", exc_info=True)


if __name__ == "__main__":
    """
    Run backtest:
    python backtest.py
    
    This will:
    - Fetch last 30 days of OHLCV data
    - Simulate grid trading strategy
    - Track virtual balance starting at 10000 USDT
    - Log PNL and trades
    - Output summary with total trades, win rate, net profit
    
    Use this to validate strategy before going live!
    """
    main()
