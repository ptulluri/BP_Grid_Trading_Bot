"""
Performance Report Generator
Generate comprehensive reports from performance metrics.
"""

import json
import csv
from typing import Dict, Any
from datetime import datetime
from backtesting.metrics.performance_metrics import PerformanceMetrics


class PerformanceReport:
    """
    Generate comprehensive performance reports with multiple export formats.
    """
    
    def __init__(self, metrics: PerformanceMetrics):
        """
        Initialize report generator.
        
        Args:
            metrics: PerformanceMetrics instance
        """
        self.metrics = metrics
    
    def generate_summary_report(self) -> str:
        """
        Generate formatted summary report with pass/fail for each metric.
        
        Returns:
            str: Formatted report text
        """
        m = self.metrics.metrics
        
        report = []
        report.append("=" * 80)
        report.append("GRID TRADING STRATEGY - PERFORMANCE REPORT")
        report.append("=" * 80)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        # Overall Assessment
        passed_metrics = sum(
            1 for metric in m.values() 
            if isinstance(metric, dict) and metric.get('meets_target', False)
        )
        total_metrics = sum(
            1 for metric in m.values() 
            if isinstance(metric, dict) and 'meets_target' in metric
        )
        
        pass_rate = (passed_metrics / total_metrics * 100) if total_metrics > 0 else 0
        
        report.append(f"OVERALL SCORE: {passed_metrics}/{total_metrics} metrics passed ({pass_rate:.1f}%)")
        report.append("")
        
        # Key Metrics Table
        report.append("KEY PERFORMANCE METRICS")
        report.append("-" * 80)
        report.append(f"{'Metric':<25} {'Value':>15} {'Target':>15} {'Status':>10} {'Grade':>15}")
        report.append("-" * 80)
        
        # Total Return
        tr = m['total_return']
        report.append(
            f"{'Total Return':<25} {tr['value']:>14.2f}% {tr['target']:>14.1f}% "
            f"{'✓ PASS' if tr['meets_target'] else '✗ FAIL':>10} {tr['grade']:>15}"
        )
        
        # Maximum Drawdown
        dd = m['max_drawdown']
        report.append(
            f"{'Maximum Drawdown':<25} {dd['value']:>14.2f}% {dd['target']:>14.1f}% "
            f"{'✓ PASS' if dd['meets_target'] else '✗ FAIL':>10} {dd['grade']:>15}"
        )
        
        # Sharpe Ratio
        sr = m['sharpe_ratio']
        report.append(
            f"{'Sharpe Ratio':<25} {sr['value']:>15.2f} {sr['target']:>15.1f} "
            f"{'✓ PASS' if sr['meets_target'] else '✗ FAIL':>10} {sr['grade']:>15}"
        )
        
        # Win Rate
        wr = m['win_rate']
        report.append(
            f"{'Win Rate':<25} {wr['value']:>14.2f}% {wr['target']:>14.1f}% "
            f"{'✓ PASS' if wr['meets_target'] else '✗ FAIL':>10} {wr['grade']:>15}"
        )
        
        # Total Trades
        tt = m['total_trades']
        report.append(
            f"{'Total Trades':<25} {tt['value']:>15} {tt['target']:>15} "
            f"{'✓ PASS' if tt['meets_target'] else '✗ FAIL':>10} {tt['grade']:>15}"
        )
        
        # Profit Factor
        pf = m['profit_factor']
        report.append(
            f"{'Profit Factor':<25} {pf['value']:>15.2f} {pf['target']:>15.1f} "
            f"{'✓ PASS' if pf['meets_target'] else '✗ FAIL':>10} {pf['grade']:>15}"
        )
        
        report.append("-" * 80)
        report.append("")
        
        # Detailed Metrics
        report.append("DETAILED METRICS")
        report.append("-" * 80)
        report.append(f"Annualized Return:        {m['annualized_return']['value']:>10.2f}%")
        report.append(f"CAGR:                     {m['cagr']['value']:>10.2f}%")
        report.append(f"Volatility:               {sr['volatility']:>10.2f}%")
        report.append(f"Downside Deviation:       {m['downside_deviation']['value']:>10.2f}%")
        report.append(f"Sortino Ratio:            {m['sortino_ratio']['value']:>10.2f}")
        report.append(f"Calmar Ratio:             {m['calmar_ratio']['value']:>10.2f}")
        report.append(f"Average Drawdown:         {m['avg_drawdown']['value']:>10.2f}%")
        report.append("")
        
        # Trading Statistics
        report.append("TRADING STATISTICS")
        report.append("-" * 80)
        report.append(f"Winning Trades:           {wr['winning_trades']:>10}")
        report.append(f"Losing Trades:            {wr['losing_trades']:>10}")
        report.append(f"Breakeven Trades:         {wr['breakeven_trades']:>10}")
        report.append(f"Average Win:              ${m['avg_win']['value']:>10.2f}")
        report.append(f"Average Loss:             ${m['avg_loss']['value']:>10.2f}")
        report.append(f"Largest Win:              ${m['largest_win']['value']:>10.2f}")
        report.append(f"Largest Loss:             ${m['largest_loss']['value']:>10.2f}")
        report.append(f"Average Trade:            ${m['avg_trade']['value']:>10.2f}")
        report.append(f"Expectancy:               ${m['expectancy']['value']:>10.2f}")
        report.append(f"Consecutive Wins (Max):   {m['consecutive_wins']['value']:>10}")
        report.append(f"Consecutive Losses (Max): {m['consecutive_losses']['value']:>10}")
        report.append("")
        
        # Additional Metrics
        report.append("ADDITIONAL METRICS")
        report.append("-" * 80)
        report.append(f"Recovery Factor:          {m['recovery_factor']['value']:>10.2f}")
        report.append(f"Gross Profit:             ${pf['gross_profit']:>10.2f}")
        report.append(f"Gross Loss:               ${pf['gross_loss']:>10.2f}")
        
        # Drawdown Details
        if dd['recovery_time'] is not None:
            report.append(f"Drawdown Recovery Time:   {dd['recovery_time']:>10} periods")
        else:
            report.append(f"Drawdown Recovery Time:   {'Not recovered':>10}")
        
        report.append("")
        
        # Final Recommendation
        report.append("=" * 80)
        report.append("RECOMMENDATION")
        report.append("=" * 80)
        
        if pass_rate >= 80:
            recommendation = "✓ APPROVED - Strategy meets all key targets. Ready for live trading."
            status = "APPROVED"
        elif pass_rate >= 60:
            recommendation = "⚠ CAUTION - Strategy shows promise but needs optimization."
            status = "CAUTION"
        else:
            recommendation = "✗ REJECTED - Strategy does not meet minimum requirements."
            status = "REJECTED"
        
        report.append(recommendation)
        report.append("")
        report.append(f"Pass Rate: {pass_rate:.1f}%")
        report.append(f"Status: {status}")
        report.append("=" * 80)
        
        return "\n".join(report)
    
    def generate_compact_summary(self) -> str:
        """Generate compact one-line summary."""
        m = self.metrics.metrics
        
        return (
            f"Return: {m['total_return']['value']:.2f}% | "
            f"DD: {m['max_drawdown']['value']:.2f}% | "
            f"Sharpe: {m['sharpe_ratio']['value']:.2f} | "
            f"Win Rate: {m['win_rate']['value']:.1f}% | "
            f"Trades: {m['total_trades']['value']} | "
            f"PF: {m['profit_factor']['value']:.2f}"
        )
    
    def export_to_json(self, filepath: str):
        """
        Export metrics to JSON file.
        
        Args:
            filepath: Path to save JSON file
        """
        # Convert metrics to JSON-serializable format
        json_data = {
            'timestamp': datetime.now().isoformat(),
            'summary': self.metrics.get_summary(),
            'all_metrics': self._serialize_metrics(self.metrics.metrics),
            'meets_all_targets': self.metrics.meets_all_targets(),
        }
        
        with open(filepath, 'w') as f:
            json.dump(json_data, f, indent=2, default=str)
    
    def export_to_csv(self, filepath: str):
        """
        Export metrics to CSV file.
        
        Args:
            filepath: Path to save CSV file
        """
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Metric', 'Value', 'Target', 'Meets Target', 'Grade'])
            
            for name, data in self.metrics.metrics.items():
                if isinstance(data, dict) and 'value' in data:
                    writer.writerow([
                        name,
                        data['value'],
                        data.get('target', 'N/A'),
                        data.get('meets_target', 'N/A'),
                        data.get('grade', 'N/A'),
                    ])
    
    def export_to_markdown(self, filepath: str):
        """
        Export metrics to Markdown file.
        
        Args:
            filepath: Path to save Markdown file
        """
        m = self.metrics.metrics
        
        md = []
        md.append("# Grid Trading Strategy - Performance Report")
        md.append("")
        md.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        md.append("")
        
        # Summary
        md.append("## Summary")
        md.append("")
        md.append("| Metric | Value | Target | Status | Grade |")
        md.append("|--------|-------|--------|--------|-------|")
        
        metrics_to_show = [
            ('Total Return', 'total_return', '%'),
            ('Max Drawdown', 'max_drawdown', '%'),
            ('Sharpe Ratio', 'sharpe_ratio', ''),
            ('Win Rate', 'win_rate', '%'),
            ('Total Trades', 'total_trades', ''),
            ('Profit Factor', 'profit_factor', ''),
        ]
        
        for name, key, unit in metrics_to_show:
            metric = m[key]
            status = '✓ PASS' if metric.get('meets_target', False) else '✗ FAIL'
            md.append(
                f"| {name} | {metric['value']:.2f}{unit} | "
                f"{metric.get('target', 'N/A')}{unit} | {status} | "
                f"{metric.get('grade', 'N/A')} |"
            )
        
        md.append("")
        
        # Detailed Metrics
        md.append("## Detailed Metrics")
        md.append("")
        md.append("### Returns")
        md.append(f"- Annualized Return: {m['annualized_return']['value']:.2f}%")
        md.append(f"- CAGR: {m['cagr']['value']:.2f}%")
        md.append("")
        
        md.append("### Risk")
        md.append(f"- Volatility: {m['volatility']['value']:.2f}%")
        md.append(f"- Downside Deviation: {m['downside_deviation']['value']:.2f}%")
        md.append(f"- Average Drawdown: {m['avg_drawdown']['value']:.2f}%")
        md.append("")
        
        md.append("### Risk-Adjusted")
        md.append(f"- Sortino Ratio: {m['sortino_ratio']['value']:.2f}")
        md.append(f"- Calmar Ratio: {m['calmar_ratio']['value']:.2f}")
        md.append("")
        
        md.append("### Trading")
        md.append(f"- Winning Trades: {m['win_rate']['winning_trades']}")
        md.append(f"- Losing Trades: {m['win_rate']['losing_trades']}")
        md.append(f"- Average Win: ${m['avg_win']['value']:.2f}")
        md.append(f"- Average Loss: ${m['avg_loss']['value']:.2f}")
        md.append(f"- Expectancy: ${m['expectancy']['value']:.2f}")
        md.append("")
        
        # Recommendation
        if self.metrics.meets_all_targets():
            md.append("## ✓ Recommendation: APPROVED")
            md.append("Strategy meets all key targets and is ready for live trading.")
        else:
            md.append("## ⚠ Recommendation: NEEDS IMPROVEMENT")
            md.append("Strategy does not meet all targets. Further optimization recommended.")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(md))
    
    def _serialize_metrics(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Convert metrics to JSON-serializable format."""
        serialized = {}
        
        for key, value in metrics.items():
            if isinstance(value, dict):
                serialized[key] = {
                    k: float(v) if isinstance(v, (int, float, np.float64, np.int64)) else v
                    for k, v in value.items()
                }
            else:
                serialized[key] = value
        
        return serialized
    
    def print_summary(self):
        """Print summary report to console."""
        print(self.generate_summary_report())
    
    def print_compact(self):
        """Print compact summary to console."""
        print(self.generate_compact_summary())


# Import numpy for serialization
import numpy as np
