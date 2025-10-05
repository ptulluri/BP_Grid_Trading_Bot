"""
Risk Management Module
Handles drawdown monitoring, volatility checks, and alerts.
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
from datetime import datetime
import numpy as np

logger = logging.getLogger(__name__)


class RiskManager:
    """Manages risk controls for the grid bot."""
    
    def __init__(self, config: dict):
        """
        Initialize risk manager.
        
        Args:
            config: Configuration dictionary with risk settings
        """
        self.config = config
        self.risk_config = config.get('risk', {})
        
        # Drawdown settings
        self.max_drawdown = self.risk_config.get('max_drawdown', 0.05)  # 5%
        self.initial_balance = None
        self.peak_balance = None
        
        # Volatility settings
        self.volatility_pause = self.risk_config.get('volatility_pause', True)
        self.atr_threshold = self.risk_config.get('atr_threshold', 2.0)
        self.atr_period = self.risk_config.get('atr_period', 14)
        self.price_history: List[float] = []
        
        # Alert settings
        self.email_alerts = self.risk_config.get('email_alerts', False)
        self.email_config = config.get('email', {})
        
        # State
        self.paused = False
        self.pause_reason = None
        
        logger.info(f"Risk Manager initialized - Max DD: {self.max_drawdown*100}%, ATR threshold: {self.atr_threshold}")
    
    def set_initial_balance(self, balance: float):
        """Set initial balance for drawdown calculation."""
        self.initial_balance = balance
        self.peak_balance = balance
        logger.info(f"Initial balance set: {balance:.2f}")
    
    def check_drawdown(self, current_balance: float) -> bool:
        """
        Check if drawdown exceeds threshold.
        
        Args:
            current_balance: Current portfolio value
            
        Returns:
            True if drawdown exceeded, False otherwise
        """
        if self.initial_balance is None:
            return False
        
        # Update peak
        if current_balance > self.peak_balance:
            self.peak_balance = current_balance
        
        # Calculate drawdown from peak
        drawdown = (self.peak_balance - current_balance) / self.peak_balance
        
        if drawdown > self.max_drawdown:
            logger.error(f"⚠️ DRAWDOWN EXCEEDED: {drawdown*100:.2f}% > {self.max_drawdown*100:.2f}%")
            logger.error(f"Peak: {self.peak_balance:.2f}, Current: {current_balance:.2f}")
            self.paused = True
            self.pause_reason = f"Drawdown {drawdown*100:.2f}% exceeded limit"
            self.send_alert(
                "DRAWDOWN ALERT",
                f"Bot paused due to excessive drawdown: {drawdown*100:.2f}%\n"
                f"Peak balance: {self.peak_balance:.2f}\n"
                f"Current balance: {current_balance:.2f}"
            )
            return True
        
        if drawdown > self.max_drawdown * 0.8:  # Warning at 80% of limit
            logger.warning(f"⚠️ Drawdown warning: {drawdown*100:.2f}% (limit: {self.max_drawdown*100:.2f}%)")
        
        return False
    
    def calculate_atr(self, prices: List[float]) -> Optional[float]:
        """
        Calculate Average True Range (ATR) for volatility measurement.
        
        Args:
            prices: List of recent prices
            
        Returns:
            ATR value or None if insufficient data
        """
        if len(prices) < self.atr_period + 1:
            return None
        
        # Calculate true ranges
        true_ranges = []
        for i in range(1, len(prices)):
            high_low = abs(prices[i] - prices[i-1])
            true_ranges.append(high_low)
        
        # Calculate ATR (simple moving average of true ranges)
        if len(true_ranges) >= self.atr_period:
            atr = np.mean(true_ranges[-self.atr_period:])
            return atr
        
        return None
    
    def check_volatility(self, current_price: float) -> bool:
        """
        Check if volatility is too high.
        
        Args:
            current_price: Current market price
            
        Returns:
            True if volatility exceeded, False otherwise
        """
        if not self.volatility_pause:
            return False
        
        # Add price to history
        self.price_history.append(current_price)
        
        # Keep only recent prices
        if len(self.price_history) > self.atr_period * 2:
            self.price_history = self.price_history[-self.atr_period * 2:]
        
        # Calculate ATR
        atr = self.calculate_atr(self.price_history)
        
        if atr is None:
            return False
        
        # Calculate ATR as percentage of price
        atr_pct = (atr / current_price) * 100
        
        if atr_pct > self.atr_threshold:
            logger.warning(f"⚠️ HIGH VOLATILITY: ATR {atr_pct:.2f}% > {self.atr_threshold}%")
            self.paused = True
            self.pause_reason = f"High volatility: ATR {atr_pct:.2f}%"
            self.send_alert(
                "VOLATILITY ALERT",
                f"Bot paused due to high volatility\n"
                f"ATR: {atr_pct:.2f}%\n"
                f"Threshold: {self.atr_threshold}%\n"
                f"Current price: {current_price:.2f}"
            )
            return True
        
        return False
    
    def send_alert(self, subject: str, message: str):
        """
        Send email alert.
        
        Args:
            subject: Email subject
            message: Email message body
        """
        if not self.email_alerts:
            logger.debug("Email alerts disabled")
            return
        
        try:
            # Get email config
            smtp_server = self.email_config.get('smtp_server', 'smtp.gmail.com')
            smtp_port = self.email_config.get('smtp_port', 587)
            sender_email = self.email_config.get('sender_email')
            sender_password = self.email_config.get('sender_password')
            recipient_email = self.email_config.get('recipient_email')
            
            if not all([sender_email, sender_password, recipient_email]):
                logger.warning("Email configuration incomplete, skipping alert")
                return
            
            # Create message
            msg = MIMEMultipart()
            msg['From'] = sender_email
            msg['To'] = recipient_email
            msg['Subject'] = f"Grid Bot Alert: {subject}"
            
            body = f"""
Grid Trading Bot Alert
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

{message}

This is an automated alert from your grid trading bot.
"""
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(sender_email, sender_password)
                server.send_message(msg)
            
            logger.info(f"✓ Alert email sent: {subject}")
            
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
    
    def is_paused(self) -> bool:
        """Check if trading is paused."""
        return self.paused
    
    def get_pause_reason(self) -> Optional[str]:
        """Get reason for pause."""
        return self.pause_reason
    
    def resume(self):
        """Resume trading (manual override)."""
        logger.info("Trading resumed manually")
        self.paused = False
        self.pause_reason = None
    
    def reset(self):
        """Reset risk manager state."""
        self.paused = False
        self.pause_reason = None
        self.price_history = []
        logger.info("Risk manager reset")
