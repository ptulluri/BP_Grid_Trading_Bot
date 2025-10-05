"""
Grid Calculator Module
Handles calculation of grid levels and order prices for grid trading strategy.
Uses pandas for efficient price array operations.
"""

import logging
import pandas as pd
import numpy as np
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)


class GridCalculator:
    """Calculate grid levels and manage grid trading parameters with pandas."""
    
    def __init__(self, grid_upper: float, grid_lower: float, grid_num: int):
        """
        Initialize grid calculator.
        
        Args:
            grid_upper: Upper price boundary
            grid_lower: Lower price boundary
            grid_num: Number of grid levels
        """
        if grid_upper <= grid_lower:
            raise ValueError("grid_upper must be greater than grid_lower")
        if grid_num < 2:
            raise ValueError("grid_num must be at least 2")
            
        self.grid_upper = grid_upper
        self.grid_lower = grid_lower
        self.grid_num = grid_num
        self.grid_levels_df = self._calculate_grid_levels()
        
        logger.info(f"Grid initialized: {grid_num} levels between {grid_lower} and {grid_upper}")
        logger.info(f"Grid spacing: {self.get_grid_spacing():.2f}")
    
    def _calculate_grid_levels(self) -> pd.DataFrame:
        """
        Calculate evenly spaced grid price levels using pandas.
        
        Returns:
            DataFrame with grid levels and metadata
        """
        # Create evenly spaced price levels using numpy linspace
        prices = np.linspace(self.grid_lower, self.grid_upper, self.grid_num)
        
        # Create DataFrame with grid information
        df = pd.DataFrame({
            'level': range(self.grid_num),
            'price': prices,
            'type': 'neutral'  # Will be set to 'buy' or 'sell' based on current price
        })
        
        logger.debug(f"Grid levels calculated:\n{df}")
        return df
    
    def get_grid_levels(self) -> List[float]:
        """Get all grid levels as a list."""
        return self.grid_levels_df['price'].tolist()
    
    def get_grid_levels_array(self) -> np.ndarray:
        """Get grid levels as numpy array for efficient calculations."""
        return self.grid_levels_df['price'].values
    
    def get_grid_dataframe(self) -> pd.DataFrame:
        """Get complete grid DataFrame with all metadata."""
        return self.grid_levels_df.copy()
    
    def calculate_balanced_buy_sell_levels(self, current_price: float) -> Tuple[List[float], List[float]]:
        """
        Calculate balanced buy/sell levels ensuring equal distribution.
        For grid_num=10, creates 5 buy orders below and 5 sell orders above current price.
        
        Args:
            current_price: Current market price
            
        Returns:
            Tuple of (buy_levels, sell_levels)
        """
        # Find the closest grid level to current price
        price_array = self.grid_levels_df['price'].values
        closest_idx = np.argmin(np.abs(price_array - current_price))
        
        # Calculate how many levels should be buy vs sell
        total_levels = self.grid_num
        target_buy_count = total_levels // 2
        target_sell_count = total_levels - target_buy_count
        
        # Get buy levels (below current price)
        buy_mask = self.grid_levels_df['price'] < current_price
        buy_levels = self.grid_levels_df[buy_mask]['price'].tolist()
        
        # Get sell levels (above current price)
        sell_mask = self.grid_levels_df['price'] > current_price
        sell_levels = self.grid_levels_df[sell_mask]['price'].tolist()
        
        # Adjust if needed to maintain balance
        if len(buy_levels) > target_buy_count:
            buy_levels = buy_levels[-target_buy_count:]  # Take highest buy levels
        if len(sell_levels) > target_sell_count:
            sell_levels = sell_levels[:target_sell_count]  # Take lowest sell levels
        
        logger.info(f"Balanced grid at price {current_price:.2f}:")
        logger.info(f"  Buy levels ({len(buy_levels)}): {[f'{p:.2f}' for p in buy_levels]}")
        logger.info(f"  Sell levels ({len(sell_levels)}): {[f'{p:.2f}' for p in sell_levels]}")
        
        return buy_levels, sell_levels
    
    def get_buy_sell_levels(self, current_price: float) -> Tuple[List[float], List[float]]:
        """
        Determine which levels should have buy orders and which should have sell orders.
        
        Args:
            current_price: Current market price
            
        Returns:
            Tuple of (buy_levels, sell_levels)
        """
        buy_levels = self.grid_levels_df[self.grid_levels_df['price'] < current_price]['price'].tolist()
        sell_levels = self.grid_levels_df[self.grid_levels_df['price'] > current_price]['price'].tolist()
        
        logger.info(f"Current price: {current_price:.2f}")
        logger.info(f"Buy levels: {len(buy_levels)}, Sell levels: {len(sell_levels)}")
        
        return buy_levels, sell_levels
    
    def check_and_adjust_grid(self, current_price: float, adjustment_threshold: float = 0.1) -> bool:
        """
        Check if current price is outside grid boundaries and suggest adjustment.
        
        Args:
            current_price: Current market price
            adjustment_threshold: Percentage threshold for adjustment (default 10%)
            
        Returns:
            True if grid needs adjustment, False otherwise
        """
        # Check if price is within grid
        if self.is_within_grid(current_price):
            distance_from_lower = (current_price - self.grid_lower) / (self.grid_upper - self.grid_lower)
            distance_from_upper = (self.grid_upper - current_price) / (self.grid_upper - self.grid_lower)
            
            # Check if price is too close to boundaries
            if distance_from_lower < adjustment_threshold or distance_from_upper < adjustment_threshold:
                logger.warning(f"Price {current_price:.2f} is close to grid boundary")
                logger.warning(f"Consider adjusting grid or using auto-price mode")
                return True
            
            logger.info(f"Price {current_price:.2f} is within grid boundaries")
            return False
        else:
            logger.error(f"Price {current_price:.2f} is OUTSIDE grid boundaries!")
            logger.error(f"Grid range: {self.grid_lower:.2f} - {self.grid_upper:.2f}")
            logger.error("Grid adjustment REQUIRED - consider using auto-price mode")
            return True
    
    def suggest_grid_adjustment(self, current_price: float, price_range: float = 0.1) -> Tuple[float, float]:
        """
        Suggest new grid boundaries centered on current price.
        
        Args:
            current_price: Current market price
            price_range: Percentage range for new grid (default 10%)
            
        Returns:
            Tuple of (suggested_lower, suggested_upper)
        """
        suggested_lower = current_price * (1 - price_range)
        suggested_upper = current_price * (1 + price_range)
        
        logger.info(f"Suggested grid adjustment for price {current_price:.2f}:")
        logger.info(f"  New range: {suggested_lower:.2f} - {suggested_upper:.2f}")
        logger.info(f"  Current range: {self.grid_lower:.2f} - {self.grid_upper:.2f}")
        
        return suggested_lower, suggested_upper
    
    def get_next_level_up(self, price: float) -> Optional[float]:
        """
        Get the next grid level above the given price using pandas.
        
        Args:
            price: Reference price
            
        Returns:
            Next level up or None if at top
        """
        higher_levels = self.grid_levels_df[self.grid_levels_df['price'] > price]['price']
        if len(higher_levels) > 0:
            return higher_levels.iloc[0]
        return None
    
    def get_next_level_down(self, price: float) -> Optional[float]:
        """
        Get the next grid level below the given price using pandas.
        
        Args:
            price: Reference price
            
        Returns:
            Next level down or None if at bottom
        """
        lower_levels = self.grid_levels_df[self.grid_levels_df['price'] < price]['price']
        if len(lower_levels) > 0:
            return lower_levels.iloc[-1]
        return None
    
    def is_within_grid(self, price: float) -> bool:
        """Check if price is within grid boundaries."""
        return self.grid_lower <= price <= self.grid_upper
    
    @staticmethod
    def calculate_auto_price_range(current_price: float, price_range: float) -> Tuple[float, float]:
        """
        Calculate grid boundaries based on current price and percentage range.
        
        Args:
            current_price: Current market price
            price_range: Percentage range (e.g., 0.1 for 10%)
            
        Returns:
            Tuple of (grid_lower, grid_upper)
        """
        grid_lower = current_price * (1 - price_range)
        grid_upper = current_price * (1 + price_range)
        
        logger.info(f"Auto-price range: {grid_lower:.2f} - {grid_upper:.2f} (±{price_range*100}%)")
        
        return grid_lower, grid_upper
    
    def get_grid_spacing(self) -> float:
        """Get the spacing between grid levels."""
        if len(self.grid_levels_df) < 2:
            return 0
        return self.grid_levels_df['price'].iloc[1] - self.grid_levels_df['price'].iloc[0]
    
    def get_grid_statistics(self) -> dict:
        """
        Get comprehensive grid statistics.
        
        Returns:
            Dictionary with grid statistics
        """
        prices = self.grid_levels_df['price']
        return {
            'num_levels': self.grid_num,
            'lower_bound': self.grid_lower,
            'upper_bound': self.grid_upper,
            'spacing': self.get_grid_spacing(),
            'range': self.grid_upper - self.grid_lower,
            'mean_price': prices.mean(),
            'median_price': prices.median(),
            'std_dev': prices.std()
        }
    
    def print_grid_summary(self):
        """Print a formatted summary of the grid."""
        stats = self.get_grid_statistics()
        print("\n" + "="*60)
        print("GRID SUMMARY")
        print("="*60)
        print(f"Number of levels: {stats['num_levels']}")
        print(f"Price range: {stats['lower_bound']:.2f} - {stats['upper_bound']:.2f}")
        print(f"Grid spacing: {stats['spacing']:.2f}")
        print(f"Total range: {stats['range']:.2f}")
        print(f"Mean price: {stats['mean_price']:.2f}")
        print(f"Median price: {stats['median_price']:.2f}")
        print("\nGrid Levels:")
        for idx, row in self.grid_levels_df.iterrows():
            print(f"  Level {row['level']:2d}: {row['price']:10.2f}")
        print("="*60 + "\n")
    
    def __repr__(self) -> str:
        return f"GridCalculator(levels={self.grid_num}, range={self.grid_lower:.2f}-{self.grid_upper:.2f}, spacing={self.get_grid_spacing():.2f})"


def verify_grid_calculation(current_price: float = 55000, grid_num: int = 10, price_range: float = 0.1):
    """
    Verification function to test grid calculations with sample data.
    
    Args:
        current_price: Sample current price (default: 55000)
        grid_num: Number of grid levels (default: 10)
        price_range: Price range percentage (default: 0.1 = 10%)
    """
    print("\n" + "="*60)
    print("GRID CALCULATION VERIFICATION")
    print("="*60)
    print(f"Current Price: {current_price}")
    print(f"Grid Levels: {grid_num}")
    print(f"Price Range: ±{price_range*100}%")
    print("="*60)
    
    # Calculate grid boundaries
    grid_lower, grid_upper = GridCalculator.calculate_auto_price_range(current_price, price_range)
    
    # Create grid calculator
    calculator = GridCalculator(grid_upper, grid_lower, grid_num)
    
    # Print grid summary
    calculator.print_grid_summary()
    
    # Get balanced buy/sell levels
    buy_levels, sell_levels = calculator.calculate_balanced_buy_sell_levels(current_price)
    
    print("\nBALANCED ORDER DISTRIBUTION:")
    print(f"Buy Orders ({len(buy_levels)}):")
    for i, price in enumerate(buy_levels, 1):
        print(f"  Buy {i}: {price:10.2f}")
    
    print(f"\nSell Orders ({len(sell_levels)}):")
    for i, price in enumerate(sell_levels, 1):
        print(f"  Sell {i}: {price:10.2f}")
    
    # Check grid adjustment
    print("\nGRID HEALTH CHECK:")
    needs_adjustment = calculator.check_and_adjust_grid(current_price)
    if needs_adjustment:
        suggested_lower, suggested_upper = calculator.suggest_grid_adjustment(current_price, price_range)
    
    print("="*60 + "\n")
    
    return calculator


if __name__ == "__main__":
    # Run verification with sample data
    print("Running verification with sample data...")
    
    # Test 1: Price at 55000 with 10 levels
    verify_grid_calculation(current_price=55000, grid_num=10, price_range=0.1)
    
    # Test 2: Different price
    verify_grid_calculation(current_price=150, grid_num=10, price_range=0.15)
    
    # Test 3: More levels
    verify_grid_calculation(current_price=1000, grid_num=20, price_range=0.2)
