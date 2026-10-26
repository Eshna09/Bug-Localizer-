"""
Order Service
Places orders using the (buggy) checkout total.
"""
from app.services.checkout_service import calculate_total
import uuid
from datetime import datetime


def place_order(cart_items: list, discount_percent: float = 0, user_id: str = "") -> dict:
    """
    Place an order and return the order details.

    Args:
        cart_items: List of cart items
        discount_percent: Discount percentage to apply
        user_id: ID of the user placing the order

    Returns:
        Order dict with id, total, status, created_at
    """
    total = calculate_total(cart_items, discount_percent)

    return {
        "order_id": str(uuid.uuid4()),
        "user_id": user_id,
        "items": cart_items,
        "discount_percent": discount_percent,
        "total": total,   # BUG: total is wrong when discount_percent > 0
        "status": "confirmed",
        "created_at": datetime.utcnow().isoformat(),
    }
