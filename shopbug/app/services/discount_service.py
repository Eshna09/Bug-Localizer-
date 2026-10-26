"""
Discount Service
BUG B001: calculate_discount() returns the discount AMOUNT instead of the discounted PRICE.
"""


def calculate_discount(price: float, discount_percent: float) -> float:
    """
    Calculate the final price after applying a percentage discount.

    Args:
        price: Original price in rupees
        discount_percent: Discount as a percentage (e.g. 20 for 20%)

    Returns:
        Final price after discount

    BUG: Should return (price - discount_amount), but currently returns
         only the discount_amount, so checkout gets the wrong total.
    """
    discount_amount = price * (discount_percent / 100)
    # BUG: should be `return price - discount_amount`
    return discount_amount
