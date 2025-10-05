"""
Order Manager Module
Tracks and manages grid trading orders.
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class Order:
    """Represents a trading order."""
    order_id: str
    symbol: str
    side: str  # "buy" or "sell"
    price: float
    quantity: float
    status: str = "open"  # open, filled, cancelled
    created_at: datetime = field(default_factory=datetime.now)
    filled_at: Optional[datetime] = None
    
    def __repr__(self) -> str:
        return f"Order({self.side} {self.quantity} @ {self.price}, status={self.status})"


class OrderManager:
    """Manages grid trading orders and their lifecycle."""
    
    def __init__(self, symbol: str):
        """
        Initialize order manager.
        
        Args:
            symbol: Trading pair symbol
        """
        self.symbol = symbol
        self.orders: Dict[str, Order] = {}  # order_id -> Order
        self.buy_orders: Dict[float, str] = {}  # price -> order_id
        self.sell_orders: Dict[float, str] = {}  # price -> order_id
        
        logger.info(f"Order manager initialized for {symbol}")
    
    def add_order(self, order_id: str, side: str, price: float, quantity: float) -> Order:
        """
        Add a new order to tracking.
        
        Args:
            order_id: Unique order identifier
            side: "buy" or "sell"
            price: Order price
            quantity: Order quantity
            
        Returns:
            Created Order object
        """
        order = Order(
            order_id=order_id,
            symbol=self.symbol,
            side=side,
            price=price,
            quantity=quantity
        )
        
        self.orders[order_id] = order
        
        if side == "buy":
            self.buy_orders[price] = order_id
        else:
            self.sell_orders[price] = order_id
        
        logger.info(f"Added order: {order}")
        return order
    
    def mark_filled(self, order_id: str) -> Optional[Order]:
        """
        Mark an order as filled.
        
        Args:
            order_id: Order ID to mark as filled
            
        Returns:
            Updated Order object or None if not found
        """
        if order_id not in self.orders:
            logger.warning(f"Order {order_id} not found")
            return None
        
        order = self.orders[order_id]
        order.status = "filled"
        order.filled_at = datetime.now()
        
        # Remove from active orders
        if order.side == "buy" and order.price in self.buy_orders:
            del self.buy_orders[order.price]
        elif order.side == "sell" and order.price in self.sell_orders:
            del self.sell_orders[order.price]
        
        logger.info(f"Order filled: {order}")
        return order
    
    def mark_cancelled(self, order_id: str) -> Optional[Order]:
        """
        Mark an order as cancelled.
        
        Args:
            order_id: Order ID to mark as cancelled
            
        Returns:
            Updated Order object or None if not found
        """
        if order_id not in self.orders:
            logger.warning(f"Order {order_id} not found")
            return None
        
        order = self.orders[order_id]
        order.status = "cancelled"
        
        # Remove from active orders
        if order.side == "buy" and order.price in self.buy_orders:
            del self.buy_orders[order.price]
        elif order.side == "sell" and order.price in self.sell_orders:
            del self.sell_orders[order.price]
        
        logger.info(f"Order cancelled: {order}")
        return order
    
    def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID."""
        return self.orders.get(order_id)
    
    def get_open_orders(self) -> List[Order]:
        """Get all open orders."""
        return [order for order in self.orders.values() if order.status == "open"]
    
    def get_filled_orders(self) -> List[Order]:
        """Get all filled orders."""
        return [order for order in self.orders.values() if order.status == "filled"]
    
    def has_order_at_price(self, price: float, side: str) -> bool:
        """
        Check if there's an active order at a specific price.
        
        Args:
            price: Price level to check
            side: "buy" or "sell"
            
        Returns:
            True if order exists at that price
        """
        if side == "buy":
            return price in self.buy_orders
        else:
            return price in self.sell_orders
    
    def get_order_at_price(self, price: float, side: str) -> Optional[Order]:
        """
        Get order at a specific price level.
        
        Args:
            price: Price level
            side: "buy" or "sell"
            
        Returns:
            Order object or None
        """
        order_id = None
        if side == "buy":
            order_id = self.buy_orders.get(price)
        else:
            order_id = self.sell_orders.get(price)
        
        return self.orders.get(order_id) if order_id else None
    
    def get_buy_order_prices(self) -> List[float]:
        """Get all prices with active buy orders."""
        return sorted(self.buy_orders.keys())
    
    def get_sell_order_prices(self) -> List[float]:
        """Get all prices with active sell orders."""
        return sorted(self.sell_orders.keys())
    
    def clear_all(self):
        """Clear all orders from tracking."""
        self.orders.clear()
        self.buy_orders.clear()
        self.sell_orders.clear()
        logger.info("All orders cleared from tracking")
    
    def get_statistics(self) -> Dict[str, int]:
        """
        Get order statistics.
        
        Returns:
            Dictionary with order counts by status
        """
        stats = {
            "total": len(self.orders),
            "open": len(self.get_open_orders()),
            "filled": len(self.get_filled_orders()),
            "buy_orders": len(self.buy_orders),
            "sell_orders": len(self.sell_orders)
        }
        return stats
    
    def __repr__(self) -> str:
        stats = self.get_statistics()
        return f"OrderManager({self.symbol}, open={stats['open']}, filled={stats['filled']})"
