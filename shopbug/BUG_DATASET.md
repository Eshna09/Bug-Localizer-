# ShopBug Ground Truth Dataset

> ⚠️ This file is EXCLUDED from AI localization runs.
> It is only used by the evaluation module AFTER predictions are generated.

## Bug B001

```json
{
  "bug_id": "B001",
  "repo_url": "https://github.com/tanurag-shrivastava/shopbug",
  "issue_description": "When I apply a 20% discount to a ₹1000 order, the final checkout amount is incorrect.",
  "ground_truth_file": "app/services/discount_service.py",
  "ground_truth_function": "calculate_discount",
  "ground_truth_lines": [22, 23],
  "category": "calculation",
  "difficulty": "easy",
  "issue_quality": "specific",
  "root_cause": "calculate_discount() returns discount_amount instead of price - discount_amount",
  "fix": "return price - discount_amount"
}
```
