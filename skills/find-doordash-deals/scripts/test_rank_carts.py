#!/usr/bin/env python3

import unittest
from decimal import Decimal

from rank_carts import rank_document


def candidate(name: str, **overrides):
    base = {
        "restaurant": name,
        "cart": "example cart",
        "checkout_total": 24,
        "menu_value": 30,
        "servings_low": 2,
        "servings_high": 3,
        "quantity_confidence": "medium",
        "leftover_score": 1,
        "verified": True,
        "benefit_eligible": True,
    }
    base.update(overrides)
    return base


class RankCartsTests(unittest.TestCase):
    def test_more_conservative_servings_wins(self):
        result = rank_document(
            {
                "budget": 25,
                "candidates": [
                    candidate("Rice Bowl", servings_low=2, servings_high=2),
                    candidate(
                        "BOGO Pizza",
                        servings_low=4,
                        servings_high=6,
                        quantity_confidence="high",
                    ),
                ],
            }
        )
        self.assertEqual(result["winner"].restaurant, "BOGO Pizza")

    def test_unverified_cart_is_excluded_even_when_larger(self):
        result = rank_document(
            {
                "candidates": [
                    candidate("Verified", servings_low=2),
                    candidate(
                        "Rumor", servings_low=20, servings_high=20, verified=False
                    ),
                ]
            }
        )
        self.assertEqual(result["winner"].restaurant, "Verified")
        self.assertEqual([item.restaurant for item in result["excluded"]], ["Rumor"])

    def test_personal_cash_defaults_to_amount_above_budget(self):
        result = rank_document(
            {
                "budget": 25,
                "max_personal_cash": 0,
                "candidates": [candidate("Over", checkout_total=25.01)],
            }
        )
        self.assertIsNone(result["winner"])
        self.assertEqual(result["excluded"][0].personal_cash, Decimal("0.01"))

    def test_exact_personal_cash_overrides_budget_calculation(self):
        result = rank_document(
            {
                "budget": 25,
                "max_personal_cash": 0,
                "candidates": [
                    candidate("Partial Coverage", checkout_total=24, personal_cash=2)
                ],
            }
        )
        self.assertIsNone(result["winner"])
        self.assertEqual(result["excluded"][0].personal_cash, Decimal(2))

    def test_benefit_eligibility_fails_closed(self):
        raw = candidate("Unknown Benefit")
        del raw["benefit_eligible"]
        result = rank_document({"candidates": [raw]})
        self.assertIsNone(result["winner"])
        self.assertIn(
            "not eligible for the company benefit",
            result["excluded"][0].exclusion_reasons(Decimal(0)),
        )

    def test_confidence_breaks_equal_lower_bound(self):
        result = rank_document(
            {
                "candidates": [
                    candidate(
                        "Vague Family Meal",
                        servings_low=3,
                        servings_high=7,
                        quantity_confidence="low",
                    ),
                    candidate(
                        "Counted Entrees",
                        servings_low=3,
                        servings_high=4,
                        quantity_confidence="high",
                    ),
                ]
            }
        )
        self.assertEqual(result["winner"].restaurant, "Counted Entrees")

    def test_invalid_serving_range_fails(self):
        with self.assertRaisesRegex(ValueError, "servings_high"):
            rank_document(
                {"candidates": [candidate("Broken", servings_low=4, servings_high=3)]}
            )


if __name__ == "__main__":
    unittest.main()
