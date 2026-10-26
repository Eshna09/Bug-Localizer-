# ShopBug — Intentionally Buggy E-Commerce App

A controlled Python repository with intentionally introduced bugs for AI bug localization research.

## Research Purpose

This repository is the **Phase 1 evaluation dataset** for the AI Bug Localizer project.
It contains known bugs with documented ground truth for measuring localization accuracy.

## Known Bugs

### B001 — Discount Calculation Error
| Field | Value |
|-------|-------|
| **File** | `app/services/discount_service.py` |
| **Function** | `calculate_discount()` |
| **Lines** | 22–23 |
| **Category** | Calculation |
| **Difficulty** | Easy |
| **Issue Quality** | Specific |

**Issue description:**
> "When I apply a 20% discount to a ₹1000 order, the final checkout amount is incorrect."

**The bug:**
`calculate_discount()` returns `discount_amount` instead of `price - discount_amount`.
So applying 20% to ₹1000 returns ₹200 (the discount value) instead of ₹800 (the final price).

**Affected files:**
- `app/services/checkout_service.py` — calls `calculate_discount()`
- `app/services/cart_service.py` — calls `calculate_total()`
- `app/services/order_service.py` — calls `calculate_total()`

## Run Tests

```bash
pip install pytest
pytest tests/ -v
```

Tests will **FAIL** (demonstrating the bug) until the fix is applied.

## Structure

```
app/
  services/
    discount_service.py    ← BUG IS HERE (B001)
    checkout_service.py    ← Affected
    cart_service.py        ← Affected
    order_service.py       ← Affected
tests/
  test_discount.py         ← Failing tests
```
