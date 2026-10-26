"""
Checkout Service
Calls discount_service.calculate_discount() to compute cart total.
Affected by B001 — receives wrong discounted price from discount_service.
"""
from app.services.discount_service import calculate_discount


def calculate_total(cart_items: list, discount_percent: float = 0) -> float:
    """
    Calculate the checkout total for a list of cart items.

    Args:
        cart_items: List of dicts with 'price' and 'quantity'
        discount_percent: Optional discount percentage to apply

    Returns:
        Final checkout total
    """
    subtotal = sum(item["price"] * item["quantity"] for item in cart_items)

    if discount_percent > 0:
        # BUG: calculate_discount returns discount_amount, not discounted_price
        # so `total` ends up being just the discount value, not the final price
        total = calculate_discount(subtotal, discount_percent)
    else:
        total = subtotal

    return total


def apply_coupon(price: float, coupon_code: str) -> float:
    """Apply a coupon code and return the discounted price."""
    coupon_discounts = {
        "SAVE10": 10,
        "SAVE20": 20,
        "SAVE50": 50,
    }
    discount = coupon_discounts.get(coupon_code.upper(), 0)
    if discount:
        return calculate_discount(price, discount)
    return price
