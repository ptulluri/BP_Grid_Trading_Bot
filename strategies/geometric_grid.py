"""
Geometric Grid Strategy
Grid with proportional (percentage-based) spacing between levels.
"""

from typing import List
import numpy as np
from strategies.base_strategy import BaseGridStrategy


class GeometricGrid(BaseGridStrategy):
    """
    Geometric grid strategy with proportional spacing.
    
    In a geometric grid, levels are spaced by a constant percentage
    rather than a constant price difference. This is better suited
    for assets with high volatility or exponential price movements.
    
    Example:
        If lower=100, upper=200, num=5:
        Arithmetic: [100, 125, 150, 175, 200] (equal $25 spacing)
        Geometric:  [100, 122.5, 150, 183.7, 225] (equal ~22.5% spacing)
    """
    
    def calculate_grid_levels(self) -> List[float]:
        """
        Calculate grid levels with geometric (proportional) spacing.
        
        The ratio between consecutive levels is constant:
        ratio = (upper / lower) ^ (1 / (num - 1))
        
        Returns:
            List of geometrically spaced price levels
        """
        # Calculate the geometric ratio
        ratio = (self.grid_upper / self.grid_lower) ** (1 / (self.grid_num - 1))
        
        # Generate levels using the ratio
        levels = []
        for i in range(self.grid_num):
            level = self.grid_lower * (ratio ** i)
            levels.append(level)
        
        return levels
    
    def get_percentage_spacing(self) -> float:
        """
        Get the percentage spacing between grid levels.
        
        Returns:
            Average percentage change between levels
        """
        if len(self.grid_levels) < 2:
            return 0.0
        
        # Calculate percentage changes
        pct_changes = []
        for i in range(len(self.grid_levels) - 1):
            pct_change = (self.grid_levels[i+1] - self.grid_levels[i]) / self.grid_levels[i]
            pct_changes.append(pct_change)
        
        return float(np.mean(pct_changes)) * 100  # Return as percentage
    
    def get_grid_ratio(self) -> float:
        """
        Get the geometric ratio between consecutive levels.
        
        Returns:
            Geometric ratio
        """
        return (self.grid_upper / self.grid_lower) ** (1 / (self.grid_num - 1))
    
    def __repr__(self) -> str:
        """String representation with geometric info."""
        ratio = self.get_grid_ratio()
        pct = self.get_percentage_spacing()
        return (
            f"GeometricGrid("
            f"lower={self.grid_lower:.2f}, "
            f"upper={self.grid_upper:.2f}, "
            f"levels={self.grid_num}, "
            f"ratio={ratio:.4f}, "
            f"spacing={pct:.2f}%)"
        )


# Example usage and comparison
if __name__ == "__main__":
    """
    Demonstrate geometric grid vs arithmetic grid.
    """
    print("=" * 70)
    print("GEOMETRIC GRID DEMONSTRATION")
    print("=" * 70)
    
    # Create geometric grid
    geo_grid = GeometricGrid(grid_upper=200.0, grid_lower=100.0, grid_num=10)
    
    print(f"\nGeometric Grid: {geo_grid}")
    print(f"Ratio: {geo_grid.get_grid_ratio():.4f}")
    print(f"Percentage Spacing: {geo_grid.get_percentage_spacing():.2f}%")
    print("\nGrid Levels:")
    for i, level in enumerate(geo_grid.get_grid_levels()):
        print(f"  Level {i}: ${level:.2f}")
    
    # Show statistics
    print("\nStatistics:")
    stats = geo_grid.get_grid_statistics()
    for key, value in stats.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.2f}")
        else:
            print(f"  {key}: {value}")
    
    # Test buy/sell levels
    current_price = 150.0
    buy_levels, sell_levels = geo_grid.calculate_balanced_buy_sell_levels(current_price)
    
    print(f"\nAt current price ${current_price:.2f}:")
    print(f"  Buy levels: {len(buy_levels)}")
    print(f"  Sell levels: {len(sell_levels)}")
    
    print("\n" + "=" * 70)
