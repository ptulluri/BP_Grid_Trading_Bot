"""
Telegram Notifier Module
Sends real-time notifications via Telegram Bot API.
"""

import logging
import asyncio
from typing import Optional
import requests

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Sends notifications via Telegram Bot."""
    
    def __init__(self, config: dict):
        """
        Initialize Telegram notifier.
        
        Args:
            config: Configuration dictionary with Telegram settings
        """
        self.config = config
        self.telegram_config = config.get('telegram', {})
        
        self.enabled = self.telegram_config.get('enabled', False)
        self.bot_token = self.telegram_config.get('bot_token', '')
        self.chat_id = self.telegram_config.get('chat_id', '')
        
        if self.enabled and (not self.bot_token or not self.chat_id):
            logger.warning("Telegram enabled but bot_token or chat_id missing")
            self.enabled = False
        
        if self.enabled:
            logger.info(f"Telegram notifier initialized - Chat ID: {self.chat_id}")
        else:
            logger.info("Telegram notifications disabled")
    
    def send_message(self, message: str, parse_mode: str = 'HTML'):
        """
        Send a message via Telegram.
        
        Args:
            message: Message text to send
            parse_mode: Parse mode (HTML or Markdown)
        """
        if not self.enabled:
            return
        
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            
            payload = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': parse_mode
            }
            
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                logger.debug("Telegram message sent successfully")
            else:
                logger.error(f"Failed to send Telegram message: {response.text}")
        
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
    
    async def send_message_async(self, message: str, parse_mode: str = 'HTML'):
        """
        Send a message via Telegram asynchronously.
        
        Args:
            message: Message text to send
            parse_mode: Parse mode (HTML or Markdown)
        """
        if not self.enabled:
            return
        
        # Run in executor to avoid blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.send_message, message, parse_mode)
    
    def notify_bot_start(self, symbol: str, mode: str):
        """Notify bot start."""
        message = (
            f"🤖 <b>Grid Bot Started</b>\n\n"
            f"Symbol: <code>{symbol}</code>\n"
            f"Mode: <b>{mode}</b>\n"
            f"Status: ✅ Running"
        )
        self.send_message(message)
    
    def notify_bot_stop(self, stats: dict):
        """Notify bot stop with statistics."""
        message = (
            f"🛑 <b>Grid Bot Stopped</b>\n\n"
            f"Total Orders: {stats.get('total', 0)}\n"
            f"Filled Orders: {stats.get('filled', 0)}\n"
            f"Buy Orders: {stats.get('buy_orders', 0)}\n"
            f"Sell Orders: {stats.get('sell_orders', 0)}"
        )
        self.send_message(message)
    
    def notify_order_placed(self, side: str, price: float, quantity: float, order_id: str):
        """Notify order placement."""
        emoji = "🟢" if side.lower() == "buy" else "🔴"
        message = (
            f"{emoji} <b>Order Placed</b>\n\n"
            f"Side: <b>{side.upper()}</b>\n"
            f"Price: <code>{price:.4f}</code>\n"
            f"Quantity: <code>{quantity}</code>\n"
            f"Order ID: <code>{order_id}</code>"
        )
        self.send_message(message)
    
    def notify_order_filled(self, side: str, price: float, quantity: float, order_id: str):
        """Notify order fill."""
        emoji = "✅"
        message = (
            f"{emoji} <b>Order Filled!</b>\n\n"
            f"Side: <b>{side.upper()}</b>\n"
            f"Price: <code>{price:.4f}</code>\n"
            f"Quantity: <code>{quantity}</code>\n"
            f"Order ID: <code>{order_id}</code>"
        )
        self.send_message(message)
    
    def notify_grid_placed(self, buy_count: int, sell_count: int, price: float):
        """Notify initial grid placement."""
        message = (
            f"📊 <b>Grid Placed</b>\n\n"
            f"Buy Orders: {buy_count}\n"
            f"Sell Orders: {sell_count}\n"
            f"Current Price: <code>{price:.4f}</code>\n"
            f"Status: ✅ Active"
        )
        self.send_message(message)
    
    def notify_risk_alert(self, alert_type: str, details: str):
        """Notify risk alert."""
        message = (
            f"⚠️ <b>RISK ALERT</b>\n\n"
            f"Type: <b>{alert_type}</b>\n"
            f"Details: {details}\n"
            f"Action: 🛑 Trading Paused"
        )
        self.send_message(message)
    
    def notify_error(self, error_type: str, error_message: str):
        """Notify error."""
        message = (
            f"❌ <b>Error Occurred</b>\n\n"
            f"Type: <b>{error_type}</b>\n"
            f"Message: <code>{error_message}</code>"
        )
        self.send_message(message)
    
    def notify_status(self, price: float, open_orders: int, filled_orders: int, 
                     buy_orders: int, sell_orders: int, mode: str):
        """Notify periodic status update."""
        message = (
            f"📈 <b>Status Update</b>\n\n"
            f"Mode: <b>{mode}</b>\n"
            f"Price: <code>{price:.4f}</code>\n"
            f"Open: {open_orders} | Filled: {filled_orders}\n"
            f"Buys: {buy_orders} | Sells: {sell_orders}"
        )
        self.send_message(message)
    
    def test_connection(self) -> bool:
        """
        Test Telegram connection.
        
        Returns:
            True if connection successful, False otherwise
        """
        if not self.enabled:
            logger.warning("Telegram not enabled")
            return False
        
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getMe"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('ok'):
                    bot_info = data.get('result', {})
                    logger.info(f"✓ Telegram connection successful - Bot: {bot_info.get('username')}")
                    
                    # Send test message
                    self.send_message(
                        "✅ <b>Telegram Connection Test</b>\n\n"
                        "Grid bot is connected and ready to send notifications!"
                    )
                    return True
            
            logger.error(f"Telegram connection failed: {response.text}")
            return False
        
        except Exception as e:
            logger.error(f"Telegram connection test failed: {e}")
            return False


def get_telegram_setup_instructions():
    """Return instructions for setting up Telegram bot."""
    return """
    TELEGRAM BOT SETUP INSTRUCTIONS
    ================================
    
    1. Create a Telegram Bot:
       - Open Telegram and search for @BotFather
       - Send /newbot command
       - Follow instructions to create your bot
       - Copy the bot token (looks like: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz)
    
    2. Get Your Chat ID:
       - Start a chat with your new bot
       - Send any message to the bot
       - Visit: https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
       - Find "chat":{"id": YOUR_CHAT_ID} in the response
       - Copy the chat ID (a number like: 123456789)
    
    3. Update config.json:
       {
         "telegram": {
           "enabled": true,
           "bot_token": "YOUR_BOT_TOKEN_HERE",
           "chat_id": "YOUR_CHAT_ID_HERE"
         }
       }
    
    4. Test Connection:
       python -c "from telegram_notifier import TelegramNotifier; import json; config = json.load(open('config.json')); notifier = TelegramNotifier(config); notifier.test_connection()"
    
    That's it! You'll now receive real-time notifications on Telegram.
    """


if __name__ == "__main__":
    """Test Telegram notifier."""
    print(get_telegram_setup_instructions())
