#!/usr/bin/env python3
"""
Backpack Grid Trading Bot
Main entry point with CLI interface

Usage:
    python main.py --config config/config.json --mode paper
    python main.py --config config/config.json --mode backtest --no-plot
    python main.py --config config/config.json --mode live --save-results results.json
"""

import argparse
import asyncio
import json
import logging
import signal
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from core.exchange import BackpackAPI
from strategies.grid_strategy import GridCalculator
from core.position_manager import OrderManager
from core.websocket_manager import BackpackWebSocket
from risk.risk_manager import RiskManager
from notifications.telegram_notifier import TelegramNotifier

# Try to load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed

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


class GridBotCLI:
    """Command-line interface for the grid trading bot."""
    
    def __init__(self, args):
        """Initialize CLI with parsed arguments."""
        self.args = args
        self.config = None
        self.bot = None
        self.running = False
        
    def load_config(self) -> dict:
        """Load configuration from file."""
        try:
            config_path = Path(self.args.config)
            if not config_path.exists():
                raise FileNotFoundError(f"Config file not found: {config_path}")
            
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            logger.info(f"Configuration loaded from {config_path}")
            
            # Override with CLI arguments if provided
            if self.args.mode:
                config['trading']['mode'] = self.args.mode
            
            if self.args.symbol:
                config['trading']['symbol'] = self.args.symbol
            
            if self.args.dry_run:
                config['trading']['dry_run'] = True
            
            return config
            
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise
    
    async def run(self):
        """Main run method."""
        try:
            # Load configuration
            self.config = self.load_config()
            
            # Display banner
            self.print_banner()
            
            # Get trading mode
            mode = self.config['trading'].get('mode', 'paper')
            
            # Run appropriate mode
            if mode == 'backtest':
                await self.run_backtest()
            elif mode == 'paper':
                await self.run_paper_trading()
            elif mode == 'live':
                await self.run_live_trading()
            else:
                raise ValueError(f"Unknown trading mode: {mode}")
                
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            sys.exit(1)
    
    def print_banner(self):
        """Print startup banner."""
        mode = self.config['trading'].get('mode', 'paper').upper()
        symbol = self.config['trading'].get('symbol', 'N/A')
        dry_run = self.config['trading'].get('dry_run', False)
        
        print("=" * 70)
        print("BACKPACK EXCHANGE GRID TRADING BOT")
        print("=" * 70)
        print(f"Mode:        {mode}")
        print(f"Symbol:      {symbol}")
        print(f"Dry Run:     {'YES' if dry_run else 'NO'}")
        print(f"Config:      {self.args.config}")
        print(f"Started:     {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        print()
    
    async def run_backtest(self):
        """Run backtesting mode."""
        logger.info("Starting backtest mode...")
        
        # Import backtest module
        from scripts.backtest import GridBotBacktest
        
        # Create and run backtest
        backtest = GridBotBacktest(self.config, initial_balance=10000.0)
        
        symbol = self.config['trading']['symbol'].replace('_', '/')
        backtest.run_backtest(symbol, days=30)
        
        # Save results if requested
        if self.args.save_results:
            logger.info(f"Saving results to {self.args.save_results}")
            # TODO: Implement results saving
        
        logger.info("Backtest complete")
    
    async def run_paper_trading(self):
        """Run paper trading mode (simulated live)."""
        logger.info("Starting paper trading mode...")
        
        # This would use the same logic as live but with dry_run=True
        self.config['trading']['dry_run'] = True
        await self.run_live_trading()
    
    async def run_live_trading(self):
        """Run live trading mode."""
        dry_run = self.config['trading'].get('dry_run', False)
        mode_str = "DRY-RUN" if dry_run else "LIVE TRADING"
        
        logger.info(f"Starting {mode_str} mode...")
        
        # Initialize components
        api = BackpackAPI(
            api_key=self.config['api']['api_key'],
            api_secret=self.config['api']['api_secret'],
            base_url=self.config['api']['base_url']
        )
        
        symbol = self.config['trading']['symbol']
        quantity = self.config['trading']['quantity']
        
        # Initialize grid calculator
        if self.config['trading']['auto_price']:
            # Get current price
            ticker = api.get_ticker(symbol)
            current_price = float(ticker.get('lastPrice', 0))
            
            price_range = self.config['trading']['price_range']
            grid_lower, grid_upper = GridCalculator.calculate_auto_price_range(
                current_price, price_range
            )
        else:
            grid_lower = self.config['trading']['grid_lower']
            grid_upper = self.config['trading']['grid_upper']
        
        grid_calculator = GridCalculator(
            grid_upper=grid_upper,
            grid_lower=grid_lower,
            grid_num=self.config['trading']['grid_num']
        )
        
        logger.info(f"Grid initialized: {grid_lower:.2f} - {grid_upper:.2f}")
        
        # Initialize other components
        order_manager = OrderManager(symbol)
        risk_manager = RiskManager(self.config)
        
        # Initialize notifications if enabled
        telegram = None
        if self.config.get('telegram', {}).get('enabled', False):
            telegram = TelegramNotifier(self.config)
            telegram.notify_bot_start(symbol, mode_str)
        
        # Setup signal handlers
        def signal_handler(signum, frame):
            logger.info(f"Signal {signum} received")
            self.running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Main trading loop
        self.running = True
        logger.info("Entering main trading loop...")
        
        try:
            while self.running:
                # Trading logic would go here
                # This is a simplified version
                await asyncio.sleep(self.config['trading'].get('interval', 60))
                
                # Check risk controls
                if risk_manager.is_paused():
                    logger.warning(f"Trading paused: {risk_manager.get_pause_reason()}")
                    continue
                
                logger.info("Bot running...")
                
        finally:
            # Cleanup
            logger.info("Shutting down...")
            
            if telegram:
                stats = order_manager.get_statistics()
                telegram.notify_bot_stop(stats)
            
            logger.info("Shutdown complete")


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Backpack Exchange Grid Trading Bot',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run in paper trading mode
  python main.py --config config/config.json --mode paper
  
  # Run backtest
  python main.py --config config/config.json --mode backtest
  
  # Run live trading
  python main.py --config config/config.json --mode live
  
  # Run with dry-run enabled
  python main.py --config config/config.json --mode live --dry-run
  
  # Save backtest results
  python main.py --config config/config.json --mode backtest --save-results results.json
        """
    )
    
    # Required arguments
    parser.add_argument(
        '--config',
        type=str,
        required=True,
        help='Path to configuration file (e.g., config/config.json)'
    )
    
    # Optional arguments
    parser.add_argument(
        '--mode',
        type=str,
        choices=['backtest', 'paper', 'live'],
        help='Trading mode (overrides config file)'
    )
    
    parser.add_argument(
        '--symbol',
        type=str,
        help='Trading symbol (overrides config file, e.g., SOL_USDC)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Enable dry-run mode (no real orders)'
    )
    
    parser.add_argument(
        '--no-plot',
        action='store_true',
        help='Disable plots in backtest mode'
    )
    
    parser.add_argument(
        '--save-results',
        type=str,
        metavar='FILE',
        help='Save backtest results to file (e.g., results.json)'
    )
    
    parser.add_argument(
        '--profile',
        action='store_true',
        help='Enable performance profiling'
    )
    
    parser.add_argument(
        '--log-level',
        type=str,
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        default='INFO',
        help='Set logging level'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version='Backpack Grid Bot v1.0.0'
    )
    
    return parser.parse_args()


async def main():
    """Main entry point."""
    # Parse arguments
    args = parse_arguments()
    
    # Set logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # Create and run CLI
    cli = GridBotCLI(args)
    await cli.run()


if __name__ == "__main__":
    """
    Entry point for the grid trading bot.
    
    Run with:
        python main.py --config config/config.json --mode paper
    
    For help:
        python main.py --help
    """
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"\nFatal error: {e}")
        sys.exit(1)
