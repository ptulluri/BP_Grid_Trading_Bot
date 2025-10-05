"""
Unit tests for GridCalculator
Uses pytest for testing grid calculation logic.
"""

import pytest
import numpy as np
import pandas as pd
import sys
from pathlib import Path

# Add parent directory to path to import from strategies
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from strategies.grid_strategy import GridCalculator


class TestGridCalculatorInitialization:
    """Test GridCalculator initialization."""
    
    def test_valid_initialization(self):
        """Test valid grid initialization."""
        calc = GridCalculator(grid_upper=100.0, grid_lower=50.0, grid_num=10)
        assert calc.grid_upper == 100.0
        assert calc.grid_lower == 50.0
        assert calc.grid_num == 10
        assert len(calc.grid_levels_df) == 10
    
    def test_invalid_upper_lower(self):
        """Test that upper must be greater than lower."""
        with pytest.raises(ValueError, match="grid_upper must be greater than grid_lower"):
            GridCalculator(grid_upper=50.0, grid_lower=100.0, grid_num=10)
    
    def test_invalid_grid_num(self):
        """Test that grid_num must be at least 2."""
        with pytest.raises(ValueError, match="grid_num must be at least 2"):
            GridCalculator(grid_upper=100.0, grid_lower=50.0, grid_num=1)
    
    def test_equal_upper_lower(self):
        """Test that upper and lower cannot be equal."""
        with pytest.raises(ValueError):
            GridCalculator(grid_upper=100.0, grid_lower=100.0, grid_num=10)


class TestGridLevelCalculation:
    """Test grid level calculation."""
    
    def test_evenly_spaced_levels(self):
        """Test that grid levels are evenly spaced."""
        calc = GridCalculator(grid_upper=100.0, grid_lower=50.0, grid_num=11)
        levels = calc.get_grid_levels()
        
        # Check first and last
        assert levels[0] == 50.0
        assert levels[-1] == 100.0
        
        # Check spacing
        spacing = calc.get_grid_spacing()
        assert spacing == pytest.approx(5.0, rel=1e-9)
        
        # Check all levels
        for i in range(len(levels) - 1):
            assert levels[i+1] - levels[i] == pytest.approx(spacing, rel=1e-9)
    
    def test_grid_levels_count(self):
        """Test correct number of grid levels."""
        for num in [2, 5, 10, 20, 50]:
            calc = GridCalculator(grid_upper=100.0, grid_lower=50.0, grid_num=num)
            assert len(calc.get_grid_levels()) == num
    
    def test_grid_levels_array(self):
        """Test numpy array output."""
        calc = GridCalculator(grid_upper=100.0, grid_lower=50.0, grid_num=10)
        array = calc.get_grid_levels_array()
        
        assert isinstance(array, np.ndarray)
        assert len(array) == 10
        assert array[0] == 50.0
        assert array[-1] == 100.0


class TestBuySellLevels:
    """Test buy/sell level determination."""
    
    def test_balanced_distribution(self):
        """Test balanced buy/sell distribution."""
        calc = GridCalculator(grid_upper=110.0, grid_lower=90.0, grid_num=10)
        buy_levels, sell_levels = calc.calculate_balanced_buy_sell_levels(100.0)
        
        # Should have 5 buy and 5 sell for 10 levels
        assert len(buy_levels) == 5
        assert len(sell_levels) == 5
        
        # All buy levels should be below current price
        assert all(level < 100.0 for level in buy_levels)
        
        # All sell levels should be above current price
        assert all(level > 100.0 for level in sell_levels)
    
    def test_price_at_boundary(self):
        """Test when price is at grid boundary."""
        calc = GridCalculator(grid_upper=100.0, grid_lower=50.0, grid_num=10)
        
        # Price at lower boundary
        buy_levels, sell_levels = calc.get_buy_sell_levels(50.0)
        assert len(buy_levels) == 0
        assert len(sell_levels) > 0
        
        # Price at upper boundary
        buy_levels, sell_levels = calc.get_buy_sell_levels(100.0)
        assert len(buy_levels) > 0
        assert len(sell_levels) == 0
    
    def test_price_in_middle(self):
        """Test when price is in the middle."""
        calc = GridCalculator(grid_upper=100.0, grid_lower=50.0, grid_num=10)
        buy_levels, sell_levels = calc.get_buy_sell_levels(75.0)
        
        # Should have roughly equal distribution
        assert len(buy_levels) > 0
        assert len(sell_levels) > 0


class TestNextLevelFunctions:
    """Test next level up/down functions."""
    
    def test_next_level_up(self):
        """Test getting next level up."""
        calc = GridCalculator(grid_upper=100.0, grid_lower=50.0, grid_num=6)
        levels = calc.get_grid_levels()
        
        # Test from each level
        for i in range(len(levels) - 1):
            next_up = calc.get_next_level_up(levels[i])
            assert next_up == pytest.approx(levels[i+1], rel=1e-9)
        
        # Test from top level
        assert calc.get_next_level_up(levels[-1]) is None
    
    def test_next_level_down(self):
        """Test getting next level down."""
        calc = GridCalculator(grid_upper=100.0, grid_lower=50.0, grid_num=6)
        levels = calc.get_grid_levels()
        
        # Test from each level
        for i in range(1, len(levels)):
            next_down = calc.get_next_level_down(levels[i])
            assert next_down == pytest.approx(levels[i-1], rel=1e-9)
        
        # Test from bottom level
        assert calc.get_next_level_down(levels[0]) is None
    
    def test_next_level_between_grids(self):
        """Test next level when price is between grid levels."""
        calc = GridCalculator(grid_upper=100.0, grid_lower=50.0, grid_num=6)
        
        # Price between levels
        next_up = calc.get_next_level_up(65.0)
        next_down = calc.get_next_level_down(65.0)
        
        assert next_up is not None
        assert next_down is not None
        assert next_down < 65.0 < next_up


class TestGridBoundaries:
    """Test grid boundary checks."""
    
    def test_is_within_grid(self):
        """Test boundary checking."""
        calc = GridCalculator(grid_upper=100.0, grid_lower=50.0, grid_num=10)
        
        assert calc.is_within_grid(75.0) is True
        assert calc.is_within_grid(50.0) is True
        assert calc.is_within_grid(100.0) is True
        assert calc.is_within_grid(49.9) is False
        assert calc.is_within_grid(100.1) is False


class TestAutoPriceRange:
    """Test auto-price range calculation."""
    
    def test_auto_price_calculation(self):
        """Test auto-price range calculation."""
        current_price = 100.0
        price_range = 0.1  # 10%
        
        lower, upper = GridCalculator.calculate_auto_price_range(current_price, price_range)
        
        assert lower == pytest.approx(90.0, rel=1e-9)
        assert upper == pytest.approx(110.0, rel=1e-9)
    
    def test_auto_price_different_ranges(self):
        """Test different price ranges."""
        current_price = 1000.0
        
        # 5% range
        lower, upper = GridCalculator.calculate_auto_price_range(current_price, 0.05)
        assert lower == pytest.approx(950.0, rel=1e-9)
        assert upper == pytest.approx(1050.0, rel=1e-9)
        
        # 20% range
        lower, upper = GridCalculator.calculate_auto_price_range(current_price, 0.20)
        assert lower == pytest.approx(800.0, rel=1e-9)
        assert upper == pytest.approx(1200.0, rel=1e-9)


class TestGridStatistics:
    """Test grid statistics."""
    
    def test_grid_spacing(self):
        """Test grid spacing calculation."""
        calc = GridCalculator(grid_upper=100.0, grid_lower=50.0, grid_num=11)
        spacing = calc.get_grid_spacing()
        assert spacing == pytest.approx(5.0, rel=1e-9)
    
    def test_grid_statistics(self):
        """Test comprehensive statistics."""
        calc = GridCalculator(grid_upper=100.0, grid_lower=50.0, grid_num=11)
        stats = calc.get_grid_statistics()
        
        assert stats['num_levels'] == 11
        assert stats['lower_bound'] == 50.0
        assert stats['upper_bound'] == 100.0
        assert stats['spacing'] == pytest.approx(5.0, rel=1e-9)
        assert stats['range'] == 50.0
        assert stats['mean_price'] == pytest.approx(75.0, rel=1e-9)
        assert stats['median_price'] == pytest.approx(75.0, rel=1e-9)


class TestPandasIntegration:
    """Test pandas DataFrame integration."""
    
    def test_dataframe_structure(self):
        """Test DataFrame structure."""
        calc = GridCalculator(grid_upper=100.0, grid_lower=50.0, grid_num=10)
        df = calc.get_grid_dataframe()
        
        assert isinstance(df, pd.DataFrame)
        assert 'level' in df.columns
        assert 'price' in df.columns
        assert 'type' in df.columns
        assert len(df) == 10
    
    def test_dataframe_values(self):
        """Test DataFrame values."""
        calc = GridCalculator(grid_upper=100.0, grid_lower=50.0, grid_num=10)
        df = calc.get_grid_dataframe()
        
        # Check level column
        assert list(df['level']) == list(range(10))
        
        # Check price column
        assert df['price'].iloc[0] == pytest.approx(50.0, rel=1e-9)
        assert df['price'].iloc[-1] == pytest.approx(100.0, rel=1e-9)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_very_small_range(self):
        """Test with very small price range."""
        calc = GridCalculator(grid_upper=100.01, grid_lower=100.00, grid_num=10)
        levels = calc.get_grid_levels()
        
        assert len(levels) == 10
        assert levels[0] == pytest.approx(100.00, rel=1e-9)
        assert levels[-1] == pytest.approx(100.01, rel=1e-9)
    
    def test_large_grid_num(self):
        """Test with large number of grid levels."""
        calc = GridCalculator(grid_upper=100.0, grid_lower=50.0, grid_num=1000)
        levels = calc.get_grid_levels()
        
        assert len(levels) == 1000
        assert levels[0] == 50.0
        assert levels[-1] == 100.0
    
    def test_two_levels_minimum(self):
        """Test minimum 2 levels."""
        calc = GridCalculator(grid_upper=100.0, grid_lower=50.0, grid_num=2)
        levels = calc.get_grid_levels()
        
        assert len(levels) == 2
        assert levels[0] == 50.0
        assert levels[1] == 100.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
