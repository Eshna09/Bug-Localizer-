"""
Tests for discount_service.
These tests FAIL before the fix and PASS after.
Used by the verification sandbox.
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.discount_service import calculate_discount
from app.services.checkout_service import calculate_total


class TestCalculateDiscount:
    def test_20_percent_discount_on_1000(self):
        """₹1000 with 20% discount should give ₹800, not ₹200."""
        result = calculate_discount(1000, 20)
        assert result == 800.0, f"Expected 800.0, got {result}"

    def test_10_percent_discount(self):
        result = calculate_discount(500, 10)
        assert result == 450.0, f"Expected 450.0, got {result}"

    def test_50_percent_discount(self):
        result = calculate_discount(200, 50)
        assert result == 100.0, f"Expected 100.0, got {result}"

    def test_zero_discount(self):
        result = calculate_discount(1000, 0)
        assert result == 1000.0, f"Expected 1000.0, got {result}"

    def test_result_is_less_than_original(self):
        """Discounted price must always be less than or equal to original."""
        result = calculate_discount(1000, 20)
        assert result <= 1000, f"Discounted price {result} > original 1000"


class TestCheckoutTotal:
    def test_checkout_with_20_percent_discount(self):
        """Cart of ₹1000 with 20% discount should total ₹800."""
        items = [{"price": 1000, "quantity": 1}]
        total = calculate_total(items, 20)
        assert total == 800.0, f"Expected 800.0, got {total}"

    def test_checkout_no_discount(self):
        items = [{"price": 500, "quantity": 2}]
        total = calculate_total(items, 0)
        assert total == 1000.0

    def test_checkout_multiple_items_with_discount(self):
        items = [
            {"price": 400, "quantity": 1},
            {"price": 600, "quantity": 1},
        ]
        total = calculate_total(items, 10)
        assert total == 900.0, f"Expected 900.0, got {total}"
