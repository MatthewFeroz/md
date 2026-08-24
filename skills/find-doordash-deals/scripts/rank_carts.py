#!/usr/bin/env python3
"""Rank verified DoorDash carts by conservative usable-food quantity."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Any

CENT = Decimal("0.01")
CONFIDENCE = {"low": 0, "medium": 1, "high": 2}


def as_decimal(value: Any, field: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ValueError(f"{field} must be a number")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field} must be a number") from exc
    if not result.is_finite():
        raise ValueError(f"{field} must be finite")
    return result


def optional_decimal(value: Any, field: str) -> Decimal | None:
    return None if value is None else as_decimal(value, field)


def as_bool(value: Any, field: str, default: bool) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        raise TypeError(f"{field} must be true or false")
    return value


def money(value: Decimal) -> str:
    return f"${value.quantize(CENT, rounding=ROUND_HALF_UP):,.2f}"


def quantity(value: Decimal) -> str:
    normalized = value.normalize()
    return format(normalized, "f")


def markdown_escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


@dataclass(frozen=True)
class Candidate:
    restaurant: str
    cart: str
    checkout_total: Decimal
    personal_cash: Decimal
    menu_value: Decimal | None
    servings_low: Decimal
    servings_high: Decimal
    quantity_confidence: str
    leftover_score: Decimal
    rating: Decimal | None
    eta_minutes: Decimal | None
    verified: bool
    benefit_eligible: bool
    diet_ok: bool
    availability_ok: bool
    promo: str
    url: str
    notes: tuple[str, ...]

    @property
    def servings_midpoint(self) -> Decimal:
        return (self.servings_low + self.servings_high) / Decimal(2)

    @property
    def all_in_per_low_serving(self) -> Decimal | None:
        if self.servings_low == 0:
            return None
        return self.checkout_total / self.servings_low

    def exclusion_reasons(self, max_personal_cash: Decimal) -> list[str]:
        reasons: list[str] = []
        if not self.verified:
            reasons.append("checkout or promotion is not verified")
        if not self.benefit_eligible:
            reasons.append("not eligible for the company benefit")
        if not self.diet_ok:
            reasons.append("violates a food constraint")
        if not self.availability_ok:
            reasons.append("unavailable for the requested time")
        if self.personal_cash > max_personal_cash:
            reasons.append(
                f"personal cash {money(self.personal_cash)} exceeds "
                f"the {money(max_personal_cash)} limit"
            )
        return reasons


def candidate_from_dict(raw: dict[str, Any], budget: Decimal, index: int) -> Candidate:
    prefix = f"candidates[{index}]"
    restaurant = raw.get("restaurant")
    if not isinstance(restaurant, str) or not restaurant.strip():
        raise ValueError(f"{prefix}.restaurant must be a non-empty string")

    cart = raw.get("cart")
    if not isinstance(cart, str) or not cart.strip():
        raise ValueError(f"{prefix}.cart must be a non-empty string")

    checkout_total = as_decimal(raw.get("checkout_total"), f"{prefix}.checkout_total")
    if checkout_total < 0:
        raise ValueError(f"{prefix}.checkout_total cannot be negative")

    personal_cash = optional_decimal(
        raw.get("personal_cash"), f"{prefix}.personal_cash"
    )
    if personal_cash is None:
        personal_cash = max(Decimal(0), checkout_total - budget)
    if personal_cash < 0:
        raise ValueError(f"{prefix}.personal_cash cannot be negative")
    if personal_cash > checkout_total:
        raise ValueError(f"{prefix}.personal_cash cannot exceed checkout_total")

    servings_low = as_decimal(raw.get("servings_low"), f"{prefix}.servings_low")
    servings_high = as_decimal(raw.get("servings_high"), f"{prefix}.servings_high")
    if servings_low < 0 or servings_high < 0:
        raise ValueError(f"{prefix} serving estimates cannot be negative")
    if servings_high < servings_low:
        raise ValueError(f"{prefix}.servings_high cannot be below servings_low")

    confidence = raw.get("quantity_confidence", "low")
    if confidence not in CONFIDENCE:
        allowed = ", ".join(CONFIDENCE)
        raise ValueError(f"{prefix}.quantity_confidence must be one of: {allowed}")

    leftover_score = as_decimal(
        raw.get("leftover_score", 0), f"{prefix}.leftover_score"
    )
    if leftover_score < 0 or leftover_score > 2:
        raise ValueError(f"{prefix}.leftover_score must be between 0 and 2")

    menu_value = optional_decimal(raw.get("menu_value"), f"{prefix}.menu_value")
    if menu_value is not None and menu_value < 0:
        raise ValueError(f"{prefix}.menu_value cannot be negative")

    rating = optional_decimal(raw.get("rating"), f"{prefix}.rating")
    if rating is not None and (rating < 0 or rating > 5):
        raise ValueError(f"{prefix}.rating must be between 0 and 5")

    eta_minutes = optional_decimal(raw.get("eta_minutes"), f"{prefix}.eta_minutes")
    if eta_minutes is not None and eta_minutes < 0:
        raise ValueError(f"{prefix}.eta_minutes cannot be negative")

    notes = raw.get("notes", [])
    if not isinstance(notes, list) or any(not isinstance(note, str) for note in notes):
        raise ValueError(f"{prefix}.notes must be an array of strings")

    promo = raw.get("promo", "")
    url = raw.get("url", "")
    if not isinstance(promo, str) or not isinstance(url, str):
        raise TypeError(f"{prefix}.promo and {prefix}.url must be strings")

    return Candidate(
        restaurant=restaurant.strip(),
        cart=cart.strip(),
        checkout_total=checkout_total,
        personal_cash=personal_cash,
        menu_value=menu_value,
        servings_low=servings_low,
        servings_high=servings_high,
        quantity_confidence=confidence,
        leftover_score=leftover_score,
        rating=rating,
        eta_minutes=eta_minutes,
        verified=as_bool(raw.get("verified"), f"{prefix}.verified", False),
        benefit_eligible=as_bool(
            raw.get("benefit_eligible"), f"{prefix}.benefit_eligible", False
        ),
        diet_ok=as_bool(raw.get("diet_ok"), f"{prefix}.diet_ok", True),
        availability_ok=as_bool(
            raw.get("availability_ok"), f"{prefix}.availability_ok", True
        ),
        promo=promo.strip(),
        url=url.strip(),
        notes=tuple(notes),
    )


def feasible_sort_key(candidate: Candidate) -> tuple[Any, ...]:
    menu_value = (
        candidate.menu_value if candidate.menu_value is not None else Decimal(-1)
    )
    rating = candidate.rating if candidate.rating is not None else Decimal(-1)
    eta = (
        candidate.eta_minutes
        if candidate.eta_minutes is not None
        else Decimal("Infinity")
    )
    return (
        -candidate.servings_low,
        -CONFIDENCE[candidate.quantity_confidence],
        -candidate.servings_midpoint,
        -candidate.leftover_score,
        candidate.personal_cash,
        -menu_value,
        -rating,
        eta,
        candidate.checkout_total,
        candidate.restaurant.casefold(),
        candidate.cart.casefold(),
    )


def excluded_sort_key(
    candidate: Candidate, max_personal_cash: Decimal
) -> tuple[Any, ...]:
    gate_failures = sum(
        (
            not candidate.verified,
            not candidate.benefit_eligible,
            not candidate.diet_ok,
            not candidate.availability_ok,
        )
    )
    overage = max(Decimal(0), candidate.personal_cash - max_personal_cash)
    return (
        gate_failures,
        overage,
        -candidate.servings_low,
        -CONFIDENCE[candidate.quantity_confidence],
        candidate.checkout_total,
        candidate.restaurant.casefold(),
    )


def rank_document(
    document: dict[str, Any],
    budget_override: Decimal | None = None,
    max_personal_cash_override: Decimal | None = None,
) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise TypeError("input must be a JSON object")

    budget = (
        budget_override
        if budget_override is not None
        else as_decimal(document.get("budget", 25), "budget")
    )
    max_personal_cash = max_personal_cash_override
    if max_personal_cash is None:
        max_personal_cash = as_decimal(
            document.get("max_personal_cash", 0), "max_personal_cash"
        )
    if budget <= 0:
        raise ValueError("budget must be greater than zero")
    if max_personal_cash < 0:
        raise ValueError("max_personal_cash cannot be negative")

    raw_candidates = document.get("candidates")
    if not isinstance(raw_candidates, list) or not raw_candidates:
        raise ValueError("candidates must be a non-empty array")
    if any(not isinstance(raw, dict) for raw in raw_candidates):
        raise ValueError("each candidate must be a JSON object")

    candidates = [
        candidate_from_dict(raw, budget, index)
        for index, raw in enumerate(raw_candidates)
    ]
    feasible = sorted(
        (
            candidate
            for candidate in candidates
            if not candidate.exclusion_reasons(max_personal_cash)
        ),
        key=feasible_sort_key,
    )
    excluded = sorted(
        (
            candidate
            for candidate in candidates
            if candidate.exclusion_reasons(max_personal_cash)
        ),
        key=lambda candidate: excluded_sort_key(candidate, max_personal_cash),
    )
    return {
        "budget": budget,
        "max_personal_cash": max_personal_cash,
        "winner": feasible[0] if feasible else None,
        "ranked": feasible,
        "excluded": excluded,
    }


def candidate_to_json(
    candidate: Candidate, reasons: Iterable[str] = ()
) -> dict[str, Any]:
    return {
        "restaurant": candidate.restaurant,
        "cart": candidate.cart,
        "checkout_total": str(candidate.checkout_total.quantize(CENT)),
        "personal_cash": str(candidate.personal_cash.quantize(CENT)),
        "menu_value": (
            str(candidate.menu_value.quantize(CENT))
            if candidate.menu_value is not None
            else None
        ),
        "servings_low": quantity(candidate.servings_low),
        "servings_high": quantity(candidate.servings_high),
        "quantity_confidence": candidate.quantity_confidence,
        "leftover_score": quantity(candidate.leftover_score),
        "rating": quantity(candidate.rating) if candidate.rating is not None else None,
        "eta_minutes": (
            quantity(candidate.eta_minutes)
            if candidate.eta_minutes is not None
            else None
        ),
        "promo": candidate.promo,
        "url": candidate.url,
        "notes": list(candidate.notes),
        "reasons": list(reasons),
    }


def render_json(result: dict[str, Any]) -> str:
    max_personal_cash = result["max_personal_cash"]
    payload = {
        "budget": str(result["budget"].quantize(CENT)),
        "max_personal_cash": str(max_personal_cash.quantize(CENT)),
        "winner": (
            candidate_to_json(result["winner"])
            if result["winner"] is not None
            else None
        ),
        "ranked": [candidate_to_json(candidate) for candidate in result["ranked"]],
        "excluded": [
            candidate_to_json(candidate, candidate.exclusion_reasons(max_personal_cash))
            for candidate in result["excluded"]
        ],
    }
    return json.dumps(payload, indent=2)


def linked_name(candidate: Candidate) -> str:
    name = markdown_escape(candidate.restaurant)
    return f"[{name}]({candidate.url})" if candidate.url else name


def render_markdown(result: dict[str, Any]) -> str:
    budget = result["budget"]
    max_personal_cash = result["max_personal_cash"]
    lines = [
        f"Budget: {money(budget)} | Max personal cash: {money(max_personal_cash)}",
        "",
    ]
    ranked: list[Candidate] = result["ranked"]
    if ranked:
        lines.extend(
            [
                "| Rank | Merchant and cart | Servings | Confidence | All-in | Personal | $/low serving | Promo |",
                "|---:|---|---:|---|---:|---:|---:|---|",
            ]
        )
        for rank, candidate in enumerate(ranked, start=1):
            per_serving = candidate.all_in_per_low_serving
            servings = (
                quantity(candidate.servings_low)
                if candidate.servings_low == candidate.servings_high
                else f"{quantity(candidate.servings_low)}-{quantity(candidate.servings_high)}"
            )
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(rank),
                        f"{linked_name(candidate)} — {markdown_escape(candidate.cart)}",
                        servings,
                        candidate.quantity_confidence,
                        money(candidate.checkout_total),
                        money(candidate.personal_cash),
                        money(per_serving) if per_serving is not None else "—",
                        markdown_escape(candidate.promo) or "—",
                    ]
                )
                + " |"
            )
        winner = ranked[0]
        winner_servings = (
            quantity(winner.servings_low)
            if winner.servings_low == winner.servings_high
            else f"{quantity(winner.servings_low)}-{quantity(winner.servings_high)}"
        )
        lines.extend(
            [
                "",
                (
                    f"Winner: {winner.restaurant} — {winner_servings} conservative servings "
                    f"for {money(winner.checkout_total)} all-in "
                    f"({money(winner.personal_cash)} personal)."
                ),
            ]
        )
    else:
        lines.append("No verified cart meets every constraint.")

    excluded: list[Candidate] = result["excluded"]
    if excluded:
        lines.extend(["", "Excluded or unverified:"])
        for candidate in excluded:
            reasons = "; ".join(candidate.exclusion_reasons(max_personal_cash))
            lines.append(f"- {candidate.restaurant} — {candidate.cart}: {reasons}.")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rank DoorDash carts by verified conservative servings."
    )
    parser.add_argument("input", help="candidate JSON file, or - for standard input")
    parser.add_argument("--budget", help="override the company-credit budget")
    parser.add_argument(
        "--max-personal-cash", help="override the maximum personal cash allowed"
    )
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    return parser.parse_args()


def load_input(path: str) -> dict[str, Any]:
    if path == "-":
        return json.load(sys.stdin)
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def main() -> int:
    args = parse_args()
    try:
        document = load_input(args.input)
        budget_override = (
            as_decimal(args.budget, "--budget") if args.budget is not None else None
        )
        personal_override = (
            as_decimal(args.max_personal_cash, "--max-personal-cash")
            if args.max_personal_cash is not None
            else None
        )
        result = rank_document(document, budget_override, personal_override)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    output = render_json(result) if args.format == "json" else render_markdown(result)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
