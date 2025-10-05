"""
Base Strategy Class
Abstract base class for all grid trading strategies.
"""

from abc import ABC, abstractmethod
from typing import List, Tuple, Dict, Any
import pandas as pd
import numpy as np


class BaseGridStrategy(ABC):
    """
    Abstract base class for grid trading strategies.
    
    All grid strategies must implement the core methods defined here.
    """
    
    def __init__(self, grid_upper: float, grid_lower: float, grid_num: int):
        """
        Initialize base grid strategy.
        
        Args:
            grid_upper: Upper price boundary of the grid
            grid_lower: Lower price boundary of the grid
            grid_num: Number of grid levels
        """
        if grid_upper <= grid_lower:
            raise ValueError("grid_upper must be greater than grid_lower")
        
        if grid_num < 2:
            raise ValueError("grid_num must be at least 2")
        
        self.grid_upper = grid_upper
        self.grid_lower = grid_lower
        self.grid_num = grid_num
        self.grid_levels = self.calculate_grid_levels()
    
    @abstractmethod
    def calculate_grid_levels(self) -> List[float]:
        """
        Calculate grid price levels.
        
        This method must be implemented by subclasses to define
        how grid levels are spaced (arithmetic, geometric, etc.)
        
        Returns:
            List of price levels
        """
        pass
    
    def get_grid_levels(self) -> List[float]:
        """
        Get the calculated grid levels.
        
        Returns:
            List of grid price levels
        """
        return self.grid_levels
    
    def get_grid_levels_array(self) -> np.ndarray:
        """
        Get grid levels as numpy array.
        
        Returns:
            Numpy array of grid levels
        """
        return np.array(self.grid_levels)
    
    def get_grid_spacing(self) -> float:
        """
        Get the average spacing between grid levels.
        
        Returns:
            Average spacing
        """
        if len(self.grid_levels) < 2:
            return 0.0
        
        spacings = np.diff(self.grid_levels)
        return float(np.mean(spacings))
    
    def is_within_grid(self, price: float) -> bool:
        """
        Check if price is within grid boundaries.
        
        Args:
            price: Price to check
            
        Returns:
            True if price is within grid, False otherwise
        """
        return self.grid_lower <= price <= self.grid_upper
    
    def get_buy_sell_levels(self, current_price: float) -> Tuple[List[float], List[float]]:
        """
        Get buy and sell levels based on current price.
        
        Args:
            current_price: Current market price
            
        Returns:
            Tuple of (buy_levels, sell_levels)
        """
        buy_levels = [level for level in self.grid_levels if level < current_price]
        sell_levels = [level for level in self.grid_levels if level > current_price]
        
        return buy_levels, sell_levels
    
    def calculate_balanced_buy_sell_levels(
        self, current_price: float
    ) -> Tuple[List[float], List[float]]:
        """
        Calculate balanced buy/sell levels around current price.
        
        Ensures roughly equal number of buy and sell orders.
        
        Args:
            current_price: Current market price
            
        Returns:
            Tuple of (buy_levels, sell_levels)
        """
        # Find closest grid level to current price
        closest_idx = min(
            range(len(self.grid_levels)),
            key=lambda i: abs(self.grid_levels[i] - current_price)
        )
        
        # Split levels around current price
        half_levels = self.grid_num // 2
        
        # Calculate buy levels (below current price)
        buy_start = max(0, closest_idx - half_levels)
        buy_end = closest_idx
        buy_levels = self.grid_levels[buy_start:buy_end]
        
        # Calculate sell levels (above current price)
        sell_start = closest_idx + 1
        sell_end = min(len(self.grid_levels), sell_start + half_levels)
        sell_levels = self.grid_levels[sell_start:sell_end]
        
        return buy_levels, sell_levels
    
    def get_next_level_up(self, price: float) -> float | None:
        """
        Get the next grid level above the given price.
        
        Args:
            price: Reference price
            
        Returns:
            Next level up, or None if at top
        """
        for level in self.grid_levels:
            if level > price:
                return level
        return None
    
    def get_next_level_down(self, price: float) -> float | None:
        """
        Get the next grid level below the given price.
        
        Args:
            price: Reference price
            
        Returns:
            Next level down, or None if at bottom
        """
        for level in reversed(self.grid_levels):
            if level < price:
                return level
        return None
    
    def get_grid_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive grid statistics.
        
        Returns:
            Dictionary of statistics
        """
        levels_array = np.array(self.grid_levels)
        
        return {
            'num_levels': len(self.grid_levels),
            'lower_bound': self.grid_lower,
            'upper_bound': self.grid_upper,
            'spacing': self.get_grid_spacing(),
            'range': self.grid_upper - self.grid_lower,
            'mean_price': float(np.mean(levels_array)),
            'median_price': float(np.median(levels_array)),
            'std_dev': float(np.std(levels_array)),
        }
    
    def get_grid_dataframe(self) -> pd.DataFrame:
        """
        Get grid levels as pandas DataFrame.
        
        Returns:
            DataFrame with grid information
        """
        df = pd.DataFrame({
            'level': range(len(self.grid_levels)),
            'price': self.grid_levels,
            'type': ['grid'] * len(self.grid_levels)
        })
        
        return df
    
    def check_and_adjust_grid(self, current_price: float) -> bool:
        """
        Check if grid needs adjustment based on current price.
        
        Args:
            current_price: Current market price
            
        Returns:
            True if grid was adjusted, False otherwise
        """
        if not self.is_within_grid(current_price):
            # Price is outside grid boundaries
            return True
        
        return False
    
    @staticmethod
    def calculate_auto_price_range(
        current_price: float, price_range: float
    ) -> Tuple[float, float]:
        """
        Calculate grid boundaries based on current price and range.
        
        Args:
            current_price: Current market price
            price_range: Price range as decimal (e.g., 0.1 for 10%)
            
        Returns:
            Tuple of (grid_lower, grid_upper)
        """
        grid_lower = current_price * (1 - price_range)
        grid_upper = current_price * (1 + price_range)
        
        return grid_lower, grid_upper
    
    def __repr__(self) -> str:
        """String representation of the strategy."""
        return (
            f"{self.__class__.__name__}("
            f"lower={self.grid_lower:.2f}, "
            f"upper={self.grid_upper:.2f}, "
            f"levels={self.grid_num})"
        )
