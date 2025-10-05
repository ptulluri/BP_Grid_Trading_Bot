# Backpack Exchange Grid Trading Bot

A Python-based grid trading bot for Backpack Exchange that automatically places buy and sell orders at predefined price levels to profit from market volatility.

## Features

- **Grid Trading Strategy**: Automatically places buy orders below current price and sell orders above
- **Auto-Price Mode**: Dynamically calculate grid boundaries based on current market price
- **Order Management**: Tracks orders and automatically rebalances the grid when orders fill
- **Configurable Parameters**: Customize grid levels, quantity, price range, and more
- **Graceful Shutdown**: Cancels all orders on exit (Ctrl+C)
- **Comprehensive Logging**: Detailed logs to file and console
- **Duration Control**: Run indefinitely or for a specific time period
- **ED25519 Authentication**: Secure API authentication using ED25519 signatures
- **WebSocket Support**: Real-time price updates via WebSocket (wss://ws.backpack.exchange)

## Grid Trading Strategy

The bot implements a classic grid trading strategy:

1. **Initial Setup**: Places buy orders at levels below current price and sell orders above
2. **When Buy Order Fills**: Automatically places a sell order at the next grid level up
3. **When Sell Order Fills**: Automatically places a buy order at the next grid level down
4. **Continuous Rebalancing**: Maintains the grid structure as orders execute

This strategy profits from price oscillations within the grid range.

## Installation

1. **Clone or download this repository**

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

This will install:
- `requests` - For HTTP API calls
- `PyNaCl` - For ED25519 signature generation
- `websocket-client` - For WebSocket real-time price updates

## API Key Setup

### ⚠️ ED25519 Keys Required

Backpack Exchange uses **ED25519 signature authentication**. You need to generate ED25519 keys and register them with Backpack Exchange.

### Generating ED25519 Keys

Run this Python script to generate a new key pair:

```python
from nacl.signing import SigningKey
from nacl.encoding import Base64Encoder

# Generate a new ED25519 key pair
signing_key = SigningKey.generate()
verify_key = signing_key.verify_key

# Get base64 encoded keys
private_key_b64 = signing_key.encode(encoder=Base64Encoder).decode('utf-8')
public_key_b64 = verify_key.encode(encoder=Base64Encoder).decode('utf-8')

print(f"Private Key (api_secret): {private_key_b64}")
print(f"Public Key (api_key): {public_key_b64}")
```

**IMPORTANT**: 
1. Save both keys securely
2. Register your **public key** with Backpack Exchange through their platform
3. Never share your **private key** with anyone

## Configuration

Edit `config.json` to configure the bot:

```json
{
  "api": {
    "base_url": "https://api.backpack.exchange",
    "api_key": "YOUR_BASE64_ENCODED_PUBLIC_KEY_HERE",
    "api_secret": "YOUR_BASE64_ENCODED_PRIVATE_KEY_HERE"
  },
  "trading": {
    "symbol": "SOL_USDC",
    "grid_upper": 150.0,
    "grid_lower": 100.0,
    "grid_num": 10,
    "quantity": 0.1,
    "auto_price": false,
    "price_range": 0.1,
    "duration": 0,
    "interval": 5
  }
}
```

### Configuration Parameters

#### API Settings
- `base_url`: Backpack Exchange API base URL (default: https://api.backpack.exchange)
- `api_key`: Your **base64-encoded ED25519 public key** (verifying key)
- `api_secret`: Your **base64-encoded ED25519 private key** (signing key)

#### Trading Settings
- `symbol`: Trading pair (e.g., "SOL_USDC", "BTC_USDC", "ETH_USDC")
- `grid_upper`: Upper price boundary for the grid
- `grid_lower`: Lower price boundary for the grid
- `grid_num`: Number of grid levels (minimum 2)
- `quantity`: Amount to trade per order (in base asset)
- `auto_price`: Enable automatic grid boundary calculation (true/false)
- `price_range`: Percentage range for auto-price mode (e.g., 0.1 = ±10%)
- `duration`: How long to run in seconds (0 = run indefinitely)
- `interval`: How often to check orders in seconds
- `use_websocket`: Enable WebSocket for real-time price updates (true/false, default: true)

### Auto-Price Mode

When `auto_price` is set to `true`:
- The bot fetches the current market price
- Calculates grid boundaries as: `current_price ± (current_price × price_range)`
- Example: If price is $100 and `price_range` is 0.1, grid will be $90-$110

## Usage

### Basic Usage

```bash
python grid_bot.py
```

### With Custom Config File

```bash
python grid_bot.py --config my_config.json
```

### Example Workflow

1. **Generate ED25519 keys** (see API Key Setup section)
2. **Register public key** with Backpack Exchange
3. **Configure settings** in `config.json`
4. **Add your API credentials** (base64-encoded keys)
5. **Run the bot**: `python grid_bot.py`
6. **Monitor the logs** in console and `grid_bot.log`
7. **Stop gracefully** with Ctrl+C (cancels all orders)

## WebSocket Real-Time Updates

The bot uses WebSocket connections to receive real-time price updates from Backpack Exchange:

- **Endpoint**: `wss://ws.backpack.exchange`
- **Stream**: Subscribes to `ticker.<symbol>` for price updates
- **Benefits**: 
  - Instant price updates without polling
  - Reduced API calls
  - Lower latency for price-sensitive operations
- **Fallback**: Automatically falls back to REST API if WebSocket disconnects
- **Auto-Reconnect**: Automatically reconnects if connection is lost

You can disable WebSocket and use REST API only by setting `use_websocket: false` in config.json.

## File Structure

```
backpack_grid_bot/
├── config.json           # Configuration file
├── grid_bot.py          # Main bot logic
├── backpack_api.py      # API client with ED25519 auth
├── websocket_client.py  # WebSocket client for real-time updates
├── grid_calculator.py   # Grid level calculations
├── order_manager.py     # Order tracking and management
├── requirements.txt     # Python dependencies
├── README.md           # This file
└── grid_bot.log        # Log file (created on run)
```

## How It Works

### 1. Initialization
- Loads configuration
- Initializes API client with ED25519 keys
- Sets up grid calculator
- Creates order manager

### 2. WebSocket Connection (if enabled)
- Connects to wss://ws.backpack.exchange
- Subscribes to ticker stream for real-time price updates
- Maintains connection with auto-reconnect

### 3. Grid Setup
- Calculates grid levels (or uses auto-price)
- Determines buy/sell levels based on current price
- Places initial orders at all grid levels

### 4. Main Loop
- Receives real-time price updates via WebSocket
- Checks order status every `interval` seconds
- Detects filled orders
- Places opposite orders at next grid level
- Logs statistics and progress with current price

### 5. Shutdown
- Closes WebSocket connection
- Cancels all open orders
- Logs final statistics
- Exits gracefully

## Example Scenarios

### Scenario 1: Fixed Grid Range
```json
{
  "grid_upper": 150.0,
  "grid_lower": 100.0,
  "grid_num": 10,
  "auto_price": false
}
```
Creates 10 levels between $100 and $150 (spacing: $5.56)

### Scenario 2: Auto-Price Mode
```json
{
  "grid_num": 20,
  "auto_price": true,
  "price_range": 0.15
}
```
If current price is $120, creates 20 levels between $102 and $138 (±15%)

## API Integration Details

The bot is fully integrated with Backpack Exchange API:

- **Authentication**: ED25519 signature-based authentication
- **Endpoints**: All endpoints verified against Backpack API specification
- **Order Sides**: Uses "Bid" for buy orders, "Ask" for sell orders
- **Response Handling**: Properly parses Backpack API responses
- **Error Handling**: Comprehensive error logging and handling

### Key API Methods

- `get_ticker()`: Fetches current market price (REST API fallback)
- `get_balance()`: Retrieves account balances
- `place_limit_order()`: Places limit orders on the grid
- `get_open_orders()`: Checks status of open orders
- `cancel_all_orders()`: Cancels all orders on shutdown

### WebSocket Features

- **Real-time Price Updates**: Subscribes to ticker stream for instant price updates
- **Auto-Reconnect**: Automatically reconnects if connection drops
- **Fallback Support**: Falls back to REST API if WebSocket unavailable
- **Connection Monitoring**: Logs connection status in real-time

## Risk Warnings

⚠️ **Trading involves risk. Use at your own risk.**

- Test with small amounts first
- Monitor the bot regularly
- Ensure sufficient balance for all orders
- Be aware of exchange fees
- Grid trading works best in ranging markets
- Trending markets may result in losses
- Keep your private keys secure
- Never share your API credentials

## Logging

The bot logs to both console and `grid_bot.log`:
- Order placements and fills
- Grid calculations
- API requests and responses
- Errors and warnings
- Statistics and progress

## Troubleshooting

### Bot won't start
- Check API credentials in `config.json` (must be base64-encoded ED25519 keys)
- Verify Python version (3.8+)
- Install dependencies: `pip install -r requirements.txt`
- Ensure public key is registered with Backpack Exchange

### Authentication errors
- Verify your public key is registered on Backpack Exchange
- Check that keys are properly base64-encoded
- Ensure private key matches the registered public key

### Orders not placing
- Check account balance
- Verify symbol format matches exchange (e.g., "SOL_USDC")
- Review API error messages in logs
- Ensure API key has trading permissions
- Check that grid prices are within market limits

### Price outside grid
- Adjust `grid_upper` and `grid_lower`
- Enable `auto_price` mode
- Wait for price to enter grid range

## Advanced Usage

### Running as a Service

On Linux, you can run the bot as a systemd service:

```bash
# Create service file
sudo nano /etc/systemd/system/grid-bot.service

# Add configuration (adjust paths):
[Unit]
Description=Backpack Grid Trading Bot
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/backpack_grid_bot
ExecStart=/usr/bin/python3 grid_bot.py
Restart=on-failure

[Install]
WantedBy=multi-user.target

# Enable and start
sudo systemctl enable grid-bot
sudo systemctl start grid-bot
```

## Support

For issues or questions:
1. Check the logs in `grid_bot.log`
2. Verify API credentials are correct
3. Consult Backpack Exchange API documentation at https://docs.backpack.exchange/
4. Test with small amounts first

## Security Best Practices

- Store your private key securely
- Never commit API keys to version control
- Use environment variables for sensitive data in production
- Regularly rotate your API keys
- Monitor your account for unauthorized activity
- Use separate API keys for testing and production

## License

This is a template/educational project. Use at your own risk.

## Disclaimer

This bot is provided as-is for educational purposes. The authors are not responsible for any financial losses incurred through its use. Always test thoroughly with small amounts before deploying with real funds. Cryptocurrency trading carries significant risk.
