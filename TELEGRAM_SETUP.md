# Telegram Bot Integration Guide

## Overview
The grid bot now supports real-time Telegram notifications for all trading activities, alerts, and status updates.

## Setup Instructions

### Step 1: Create a Telegram Bot

1. Open Telegram and search for `@BotFather`
2. Send the command: `/newbot`
3. Follow the prompts to:
   - Choose a name for your bot (e.g., "My Grid Bot")
   - Choose a username (must end in 'bot', e.g., "my_grid_bot")
4. **Save the bot token** (looks like: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### Step 2: Get Your Chat ID

1. Start a chat with your new bot (click the link provided by BotFather)
2. Send any message to your bot (e.g., "Hello")
3. Open this URL in your browser (replace `<YOUR_BOT_TOKEN>` with your actual token):
   ```
   https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
   ```
4. Look for `"chat":{"id":` in the response
5. **Save your chat ID** (a number like: `123456789`)

### Step 3: Configure the Bot

Edit `config.json` and update the telegram section:

```json
{
  "telegram": {
    "enabled": true,
    "bot_token": "123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
    "chat_id": "123456789"
  }
}
```

### Step 4: Test the Connection

Run this command to test your Telegram setup:

```bash
cd backpack_grid_bot
python telegram_notifier.py
```

Or test programmatically:

```python
from telegram_notifier import TelegramNotifier
import json

config = json.load(open('config.json'))
notifier = TelegramNotifier(config)
notifier.test_connection()
```

You should receive a test message on Telegram!

## Notification Types

### 🤖 Bot Start/Stop
- Notified when bot starts
- Final statistics when bot stops

### 🟢🔴 Order Placement
- Real-time notifications for each order placed
- Includes side (BUY/SELL), price, quantity, and order ID

### ✅ Order Fills
- Instant notification when orders are filled
- Shows which orders executed

### 📊 Grid Status
- Initial grid placement summary
- Periodic status updates

### ⚠️ Risk Alerts
- Drawdown warnings
- High volatility alerts
- Trading pause notifications

### ❌ Error Notifications
- Order placement failures
- API errors
- System issues

## Example Notifications

### Bot Start
```
🤖 Grid Bot Started

Symbol: SOL_USDC
Mode: LIVE
Status: ✅ Running
```

### Order Filled
```
✅ Order Filled!

Side: BUY
Price: 54388.89
Quantity: 0.1
Order ID: abc123
```

### Risk Alert
```
⚠️ RISK ALERT

Type: High Volatility
Details: ATR 2.5% > 2.0%
Action: 🛑 Trading Paused
```

## Integration in Code

To add Telegram notifications to your bot:

```python
from telegram_notifier import TelegramNotifier

# Initialize
telegram = TelegramNotifier(config)

# Send custom message
telegram.send_message("📈 <b>Custom Alert</b>\n\nYour message here")

# Use built-in notifications
telegram.notify_order_filled("buy", 55000.0, 0.1, "order_123")
telegram.notify_risk_alert("Drawdown", "5.2% exceeded limit")
```

## Troubleshooting

### Bot not receiving messages
- Verify bot token is correct
- Ensure you've started a chat with the bot
- Check chat ID is correct
- Make sure `enabled: true` in config

### "Unauthorized" error
- Bot token is invalid
- Create a new bot and update token

### Messages not formatted correctly
- The bot uses HTML parse mode
- Use `<b>bold</b>`, `<code>code</code>`, `<i>italic</i>`

## Privacy & Security

- **Never share your bot token** - it's like a password
- Bot tokens can be regenerated via @BotFather if compromised
- Only you (the chat ID owner) will receive notifications
- Messages are sent via Telegram's encrypted API

## Advanced Usage

### Multiple Recipients
To send to multiple users, create a Telegram group:
1. Create a group and add your bot
2. Get the group chat ID (negative number)
3. Use the group chat ID in config

### Custom Notifications
```python
# In your code
if some_condition:
    telegram.send_message(
        f"🎯 <b>Custom Event</b>\n\n"
        f"Price: <code>{price}</code>\n"
        f"Action: Something happened"
    )
```

## Disable Telegram

To disable Telegram notifications:

```json
{
  "telegram": {
    "enabled": false
  }
}
```

The bot will work normally without Telegram.
