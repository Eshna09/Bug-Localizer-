"""
Cart Service
Affected by B001 via checkout_service.calculate_total().
"""
from app.services.checkout_service import calculate_total


def get_cart_total(cart_items: list, coupon_discount: float = 0) -> dict:
    """
    Get cart summary with total and item count.

    Args:
        cart_items: List of dicts with 'name', 'price', 'quantity'
        coupon_discount: Discount percentage from coupon

    Returns:
        dict with subtotal, discount_applied, total, item_count
    """
    subtotal = sum(item["price"] * item["quantity"] for item in cart_items)
    total = calculate_total(cart_items, coupon_discount)

    return {
        "item_count": sum(item["quantity"] for item in cart_items),
        "subtotal": subtotal,
        "discount_applied": coupon_discount,
        "total": total,
    }
