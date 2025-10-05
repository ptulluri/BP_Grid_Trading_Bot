"""
Performance Metrics Calculator
Comprehensive metrics for grid trading strategy evaluation.
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Any, Tuple
from datetime import datetime, timedelta


class PerformanceMetrics:
    """
    Calculate comprehensive performance metrics for grid trading strategies.
    
    Grid Trading Targets:
    - Total Return: > 5-10% annualized
    - Maximum Drawdown: < 10-15%
    - Sharpe Ratio: > 1.0
    - Win Rate: > 50%
    - Total Trades: > 100 for statistical validity
    - Profit Factor: > 1.5
    """
    
    def __init__(
        self,
        trades: List[Dict],
        initial_balance: float,
        final_balance: float,
        equity_curve: List[float],
        timestamps: List[datetime] = None,
    ):
        """
        Initialize performance metrics calculator.
        
        Args:
            trades: List of trade dictionaries with 'pnl', 'side', 'price', etc.
            initial_balance: Starting capital
            final_balance: Ending capital
            equity_curve: Time series of portfolio values
            timestamps: Optional timestamps for equity curve
        """
        self.trades = trades
        self.initial_balance = initial_balance
        self.final_balance = final_balance
        self.equity_curve = np.array(equity_curve)
        self.timestamps = timestamps or list(range(len(equity_curve)))
        
        # Calculate all metrics
        self.metrics = self.calculate_all_metrics()
    
    def calculate_all_metrics(self) -> Dict[str, Any]:
        """Calculate comprehensive performance metrics."""
        return {
            # Returns
            'total_return': self.calculate_total_return(),
            'annualized_return': self.calculate_annualized_return(),
            'cagr': self.calculate_cagr(),
            
            # Risk
            'max_drawdown': self.calculate_max_drawdown(),
            'avg_drawdown': self.calculate_avg_drawdown(),
            'volatility': self.calculate_volatility(),
            'downside_deviation': self.calculate_downside_deviation(),
            
            # Risk-Adjusted
            'sharpe_ratio': self.calculate_sharpe_ratio(),
            'sortino_ratio': self.calculate_sortino_ratio(),
            'calmar_ratio': self.calculate_calmar_ratio(),
            
            # Trading
            'total_trades': self.calculate_total_trades(),
            'win_rate': self.calculate_win_rate(),
            'profit_factor': self.calculate_profit_factor(),
            'avg_win': self.calculate_avg_win(),
            'avg_loss': self.calculate_avg_loss(),
            'largest_win': self.calculate_largest_win(),
            'largest_loss': self.calculate_largest_loss(),
            'avg_trade': self.calculate_avg_trade(),
            
            # Additional
            'recovery_factor': self.calculate_recovery_factor(),
            'expectancy': self.calculate_expectancy(),
            'consecutive_wins': self.calculate_consecutive_wins(),
            'consecutive_losses': self.calculate_consecutive_losses(),
        }
    
    # ==================== RETURN METRICS ====================
    
    def calculate_total_return(self) -> Dict[str, Any]:
        """
        Total return as percentage of initial capital.
        Target: > 5-10% annualized
        """
        total_return = ((self.final_balance - self.initial_balance) / 
                       self.initial_balance * 100)
        
        return {
            'value': total_return,
            'target': 5.0,
            'meets_target': total_return >= 5.0,
            'grade': self._grade_return(total_return),
        }
    
    def calculate_annualized_return(self) -> Dict[str, Any]:
        """Calculate annualized return."""
        if len(self.equity_curve) < 2:
            return {'value': 0.0, 'target': 5.0, 'meets_target': False}
        
        # Assume daily data
        days = len(self.equity_curve)
        years = days / 365.0
        
        if years > 0:
            total_return = (self.final_balance / self.initial_balance) - 1
            annualized = ((1 + total_return) ** (1 / years) - 1) * 100
        else:
            annualized = 0.0
        
        return {
            'value': annualized,
            'target': 5.0,
            'meets_target': annualized >= 5.0,
        }
    
    def calculate_cagr(self) -> Dict[str, Any]:
        """Compound Annual Growth Rate."""
        return self.calculate_annualized_return()
    
    # ==================== RISK METRICS ====================
    
    def calculate_max_drawdown(self) -> Dict[str, Any]:
        """
        Maximum drawdown - largest peak-to-trough decline.
        Target: < 10-15%
        """
        if len(self.equity_curve) < 2:
            return {'value': 0.0, 'target': 10.0, 'meets_target': True}
        
        # Calculate running maximum
        running_max = np.maximum.accumulate(self.equity_curve)
        
        # Calculate drawdown at each point
        drawdown = (running_max - self.equity_curve) / running_max * 100
        
        # Find maximum drawdown
        max_dd = np.max(drawdown)
        max_dd_idx = np.argmax(drawdown)
        
        # Find peak before max drawdown
        peak_idx = np.argmax(self.equity_curve[:max_dd_idx+1]) if max_dd_idx > 0 else 0
        
        # Calculate recovery
        recovery_idx = None
        if max_dd_idx < len(self.equity_curve) - 1:
            for i in range(max_dd_idx + 1, len(self.equity_curve)):
                if self.equity_curve[i] >= self.equity_curve[peak_idx]:
                    recovery_idx = i
                    break
        
        recovery_time = (recovery_idx - max_dd_idx) if recovery_idx else None
        
        return {
            'value': max_dd,
            'target': 10.0,
            'meets_target': max_dd <= 10.0,
            'peak_value': self.equity_curve[peak_idx],
            'trough_value': self.equity_curve[max_dd_idx],
            'peak_idx': peak_idx,
            'trough_idx': max_dd_idx,
            'recovery_time': recovery_time,
            'grade': self._grade_drawdown(max_dd),
        }
    
    def calculate_avg_drawdown(self) -> Dict[str, Any]:
        """Average drawdown."""
        if len(self.equity_curve) < 2:
            return {'value': 0.0}
        
        running_max = np.maximum.accumulate(self.equity_curve)
        drawdown = (running_max - self.equity_curve) / running_max * 100
        
        # Only consider periods in drawdown
        dd_periods = drawdown[drawdown > 0]
        avg_dd = np.mean(dd_periods) if len(dd_periods) > 0 else 0.0
        
        return {'value': avg_dd}
    
    def calculate_volatility(self) -> Dict[str, Any]:
        """Annualized volatility (standard deviation of returns)."""
        if len(self.equity_curve) < 2:
            return {'value': 0.0}
        
        returns = np.diff(self.equity_curve) / self.equity_curve[:-1]
        volatility = np.std(returns) * np.sqrt(365) * 100  # Annualized
        
        return {'value': volatility}
    
    def calculate_downside_deviation(self) -> Dict[str, Any]:
        """Downside deviation (volatility of negative returns only)."""
        if len(self.equity_curve) < 2:
            return {'value': 0.0}
        
        returns = np.diff(self.equity_curve) / self.equity_curve[:-1]
        negative_returns = returns[returns < 0]
        
        if len(negative_returns) > 0:
            downside_dev = np.std(negative_returns) * np.sqrt(365) * 100
        else:
            downside_dev = 0.0
        
        return {'value': downside_dev}
    
    # ==================== RISK-ADJUSTED METRICS ====================
    
    def calculate_sharpe_ratio(self, risk_free_rate: float = 0.02) -> Dict[str, Any]:
        """
        Sharpe Ratio - risk-adjusted return.
        Target: > 1.0
        """
        if len(self.equity_curve) < 2:
            return {'value': 0.0, 'target': 1.0, 'meets_target': False}
        
        returns = np.diff(self.equity_curve) / self.equity_curve[:-1]
        
        # Annualize
        avg_return = np.mean(returns) * 365
        volatility = np.std(returns) * np.sqrt(365)
        
        sharpe = (avg_return - risk_free_rate) / volatility if volatility > 0 else 0
        
        return {
            'value': sharpe,
            'target': 1.0,
            'meets_target': sharpe >= 1.0,
            'avg_return': avg_return * 100,
            'volatility': volatility * 100,
            'grade': self._grade_sharpe(sharpe),
        }
    
    def calculate_sortino_ratio(self, risk_free_rate: float = 0.02) -> Dict[str, Any]:
        """Sortino Ratio - return / downside deviation."""
        if len(self.equity_curve) < 2:
            return {'value': 0.0}
        
        returns = np.diff(self.equity_curve) / self.equity_curve[:-1]
        avg_return = np.mean(returns) * 365
        
        downside_dev = self.calculate_downside_deviation()['value'] / 100
        
        sortino = (avg_return - risk_free_rate) / downside_dev if downside_dev > 0 else 0
        
        return {'value': sortino}
    
    def calculate_calmar_ratio(self) -> Dict[str, Any]:
        """Calmar Ratio - annualized return / max drawdown."""
        ann_return = self.calculate_annualized_return()['value']
        max_dd = self.calculate_max_drawdown()['value']
        
        calmar = ann_return / max_dd if max_dd > 0 else 0
        
        return {'value': calmar}
    
    # ==================== TRADING METRICS ====================
    
    def calculate_total_trades(self) -> Dict[str, Any]:
        """
        Total number of trades.
        Target: > 100 for statistical validity
        """
        total = len(self.trades)
        
        return {
            'value': total,
            'target': 100,
            'meets_target': total >= 100,
            'statistically_valid': total >= 30,
            'grade': self._grade_trade_count(total),
        }
    
    def calculate_win_rate(self) -> Dict[str, Any]:
        """
        Percentage of profitable trades.
        Target: > 50%
        """
        if not self.trades:
            return {
                'value': 0,
                'target': 50.0,
                'meets_target': False,
                'winning_trades': 0,
                'losing_trades': 0,
                'breakeven_trades': 0,
                'total_trades': 0,
                'grade': 'F (No trades)',
            }
        
        wins = [t for t in self.trades if t.get('pnl', 0) > 0]
        losses = [t for t in self.trades if t.get('pnl', 0) < 0]
        breakeven = [t for t in self.trades if t.get('pnl', 0) == 0]
        
        total = len(self.trades)
        win_count = len(wins)
        
        win_rate = (win_count / total * 100) if total > 0 else 0
        
        return {
            'value': win_rate,
            'target': 50.0,
            'meets_target': win_rate >= 50.0,
            'winning_trades': win_count,
            'losing_trades': len(losses),
            'breakeven_trades': len(breakeven),
            'total_trades': total,
            'grade': self._grade_win_rate(win_rate),
        }
    
    def calculate_profit_factor(self) -> Dict[str, Any]:
        """
        Profit Factor - gross profit / gross loss.
        Target: > 1.5
        """
        if not self.trades:
            return {
                'value': 0,
                'target': 1.5,
                'meets_target': False,
                'gross_profit': 0,
                'gross_loss': 0,
                'grade': 'F (No trades)',
            }
        
        gross_profit = sum(t.get('pnl', 0) for t in self.trades if t.get('pnl', 0) > 0)
        gross_loss = abs(sum(t.get('pnl', 0) for t in self.trades if t.get('pnl', 0) < 0))
        
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        return {
            'value': profit_factor,
            'target': 1.5,
            'meets_target': profit_factor >= 1.5,
            'gross_profit': gross_profit,
            'gross_loss': gross_loss,
            'grade': self._grade_profit_factor(profit_factor),
        }
    
    def calculate_avg_win(self) -> Dict[str, Any]:
        """Average winning trade."""
        wins = [t.get('pnl', 0) for t in self.trades if t.get('pnl', 0) > 0]
        avg_win = np.mean(wins) if wins else 0.0
        
        return {'value': avg_win}
    
    def calculate_avg_loss(self) -> Dict[str, Any]:
        """Average losing trade."""
        losses = [t.get('pnl', 0) for t in self.trades if t.get('pnl', 0) < 0]
        avg_loss = np.mean(losses) if losses else 0.0
        
        return {'value': avg_loss}
    
    def calculate_largest_win(self) -> Dict[str, Any]:
        """Largest winning trade."""
        wins = [t.get('pnl', 0) for t in self.trades if t.get('pnl', 0) > 0]
        largest = max(wins) if wins else 0.0
        
        return {'value': largest}
    
    def calculate_largest_loss(self) -> Dict[str, Any]:
        """Largest losing trade."""
        losses = [t.get('pnl', 0) for t in self.trades if t.get('pnl', 0) < 0]
        largest = min(losses) if losses else 0.0
        
        return {'value': largest}
    
    def calculate_avg_trade(self) -> Dict[str, Any]:
        """Average trade P&L."""
        if not self.trades:
            return {'value': 0.0}
        
        avg = np.mean([t.get('pnl', 0) for t in self.trades])
        return {'value': avg}
    
    # ==================== ADDITIONAL METRICS ====================
    
    def calculate_recovery_factor(self) -> Dict[str, Any]:
        """Recovery Factor - net profit / max drawdown."""
        net_profit = self.final_balance - self.initial_balance
        max_dd_value = self.calculate_max_drawdown()['value'] / 100 * self.initial_balance
        
        recovery = net_profit / max_dd_value if max_dd_value > 0 else 0
        
        return {'value': recovery}
    
    def calculate_expectancy(self) -> Dict[str, Any]:
        """Expectancy - average expected profit per trade."""
        if not self.trades:
            return {'value': 0.0}
        
        win_rate = self.calculate_win_rate()['value'] / 100
        avg_win = self.calculate_avg_win()['value']
        avg_loss = abs(self.calculate_avg_loss()['value'])
        
        expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
        
        return {'value': expectancy}
    
    def calculate_consecutive_wins(self) -> Dict[str, Any]:
        """Maximum consecutive winning trades."""
        if not self.trades:
            return {'value': 0}
        
        max_consecutive = 0
        current_consecutive = 0
        
        for trade in self.trades:
            if trade.get('pnl', 0) > 0:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0
        
        return {'value': max_consecutive}
    
    def calculate_consecutive_losses(self) -> Dict[str, Any]:
        """Maximum consecutive losing trades."""
        if not self.trades:
            return {'value': 0}
        
        max_consecutive = 0
        current_consecutive = 0
        
        for trade in self.trades:
            if trade.get('pnl', 0) < 0:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0
        
        return {'value': max_consecutive}
    
    # ==================== GRADING FUNCTIONS ====================
    
    def _grade_return(self, return_pct: float) -> str:
        """Grade return performance."""
        if return_pct >= 15:
            return 'A+ (Excellent)'
        elif return_pct >= 10:
            return 'A (Very Good)'
        elif return_pct >= 5:
            return 'B (Good)'
        elif return_pct >= 0:
            return 'C (Acceptable)'
        else:
            return 'F (Poor)'
    
    def _grade_drawdown(self, dd_pct: float) -> str:
        """Grade drawdown performance."""
        if dd_pct <= 5:
            return 'A+ (Excellent)'
        elif dd_pct <= 10:
            return 'A (Very Good)'
        elif dd_pct <= 15:
            return 'B (Good)'
        elif dd_pct <= 20:
            return 'C (Acceptable)'
        else:
            return 'F (Poor)'
    
    def _grade_sharpe(self, sharpe: float) -> str:
        """Grade Sharpe ratio."""
        if sharpe >= 2.0:
            return 'A+ (Excellent)'
        elif sharpe >= 1.5:
            return 'A (Very Good)'
        elif sharpe >= 1.0:
            return 'B (Good)'
        elif sharpe >= 0.5:
            return 'C (Acceptable)'
        else:
            return 'F (Poor)'
    
    def _grade_win_rate(self, win_rate: float) -> str:
        """Grade win rate."""
        if win_rate >= 70:
            return 'A+ (Excellent)'
        elif win_rate >= 60:
            return 'A (Very Good)'
        elif win_rate >= 50:
            return 'B (Good)'
        elif win_rate >= 40:
            return 'C (Acceptable)'
        else:
            return 'F (Poor)'
    
    def _grade_profit_factor(self, pf: float) -> str:
        """Grade profit factor."""
        if pf >= 2.5:
            return 'A+ (Excellent)'
        elif pf >= 2.0:
            return 'A (Very Good)'
        elif pf >= 1.5:
            return 'B (Good)'
        elif pf >= 1.0:
            return 'C (Acceptable)'
        else:
            return 'F (Poor)'
    
    def _grade_trade_count(self, count: int) -> str:
        """Grade trade count."""
        if count >= 200:
            return 'A+ (Excellent sample)'
        elif count >= 100:
            return 'A (Good sample)'
        elif count >= 50:
            return 'B (Acceptable sample)'
        elif count >= 30:
            return 'C (Minimum sample)'
        else:
            return 'F (Insufficient data)'
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of key metrics."""
        m = self.metrics
        
        return {
            'total_return': m['total_return']['value'],
            'max_drawdown': m['max_drawdown']['value'],
            'sharpe_ratio': m['sharpe_ratio']['value'],
            'win_rate': m['win_rate']['value'],
            'total_trades': m['total_trades']['value'],
            'profit_factor': m['profit_factor']['value'],
        }
    
    def meets_all_targets(self) -> bool:
        """Check if all key metrics meet targets."""
        m = self.metrics
        
        return all([
            m['total_return']['meets_target'],
            m['max_drawdown']['meets_target'],
            m['sharpe_ratio']['meets_target'],
            m['win_rate']['meets_target'],
            m['total_trades']['meets_target'],
            m['profit_factor']['meets_target'],
        ])
