---
name: find-doordash-deals
description: "Live DoorDash deal discovery and cart optimization for fixed meal credits or spending caps. Use when finding tonight's best DoorDash offer, maximizing servings or leftovers under a budget such as a $25 employer meal allowance, comparing BOGO and promo carts after fees, or preparing a winning delivery or pickup cart for review."
---

# DoorDash Deal Finder

Find account-eligible offers, verify realistic carts, and rank them by usable food rather than headline discount. Default to a $25 all-in company credit, $0 personal cash, prepared dinner delivery, and conservative meal servings unless the user says otherwise.

## 1. Resolve the run

Use the current date, requested meal time, and the saved DoorDash delivery address. Keep the street address private in the handoff. Reuse stated dietary restrictions, hard dislikes, fulfillment preference, DashPass status, and tip policy from the conversation.

Treat the following as hard constraints only when the user or DoorDash supplies them:

- allergies and dietary exclusions;
- delivery versus pickup;
- the charges covered by the company benefit;
- a personal-cash allowance;
- arrival deadline.

If the benefit's coverage is unclear and DoorDash does not show an exact applied-credit or personal-balance line, finish useful deal discovery first, then ask one concise question before final ranking. Keep the same reasonable tip amount or user-supplied tip policy across delivery candidates; do not create savings by lowering it.

This step is complete when the budget, personal-cash limit, fulfillment mode, location, meal time, and hard food constraints are known or explicitly defaulted.

## 2. Reach DoorDash

Query available tools for a DoorDash connector first. Use it when it exposes the signed-in account's live offers, menus, cart, and checkout totals. Otherwise load the available browser-control skill and use a signed-in, automation-capable browser at `https://www.doordash.com/`. Prefer the browser over general web search because eligibility, prices, availability, fees, and promotions depend on the account, address, and time.

If authentication is required, ask the user to sign in in that same browser and resume in the same tab. Never request credentials in chat or inspect cookies, storage, passwords, or session data.

This step is complete when the account-specific storefront and saved delivery area are visible.

## 3. Build a broad shortlist

Inspect the account's visible Offers or Deals surfaces and nearby merchant cards. Search semantically when needed instead of relying on fixed UI labels. Collect at least eight promising items or bundles across at least five merchants before checkout, unless the live storefront contains fewer eligible choices.

Prioritize deal shapes that can increase complete-meal quantity:

- BOGO full entrees or pizzas;
- family meals, multi-entree bundles, and large-format dishes;
- percentage or flat discounts whose minimum subtotal fits the budget;
- DashPass or merchant offers that remove delivery fees;
- filling, reheatable sides that use otherwise stranded credit.

Record each offer's eligible items, required quantity, minimum subtotal, maximum discount, fulfillment restriction, DashPass requirement, and visible expiry. Use only offers shown as eligible for the active account and address. Treat sponsored placement as advertising, not evidence of value.

Default to prepared restaurant food. Include grocery, convenience, beverages, desserts, subscriptions, or new-user promotions only when the user requests or permits that category. Do not use multi-account, referral, or promotion-abuse tactics.

This step is complete when the shortlist covers the strongest distinct offer shapes available tonight, not merely the first visible restaurants.

## 4. Design food-maximizing carts

Create one or more cart compositions for each strong offer. Satisfy the promotion with the fewest low-value extras, then test a useful filler only when the remaining all-in budget can buy more edible food without invalidating the deal.

Estimate `servings_low` and `servings_high` conservatively from explicit counts, stated sizes, menu descriptions, and standard meal structure. Prefer the lower bound when uncertain. Record `quantity_confidence` as `low`, `medium`, or `high` and a short basis for the estimate. Set `leftover_score` to `0` for food that keeps poorly, `1` for acceptable leftovers, or `2` for food that refrigerates, reheats, or freezes well. Never invent weights or calories. Do not inflate quantity with sauces, utensils, condiments, or a raw item count; drinks count only when the user values them.

Use `menu_value` only as a tie-breaker. It is the sum of the merchant's displayed pre-discount prices for the actual quantities in the cart, not a claim about intrinsic value.

This step is complete when at least four materially different carts are ready for checkout verification, unless fewer offers survived the constraints.

## 5. Verify the real totals

Inspect the current cart before changing it. If it contains unrelated user items, preserve it and ask before accepting any DoorDash action that would replace or clear it.

Verify up to five leading carts at the last reviewable checkout screen, one at a time. Use the same fulfillment mode and tip policy within a leaderboard. If comparing both delivery and pickup, build separate leaderboards. For every cart, capture:

- exact items and quantities, including every free BOGO item;
- promotion actually applied and discount shown;
- item subtotal, taxes, delivery fee, service fee, small-order fee, and tip;
- `checkout_total` after the promotion and all included charges;
- exact `personal_cash` after the company credit when DoorDash shows it;
- rating, ETA, merchant link, and any substitution or availability risk.

Set `verified` to `true` only when the required quantities are present, the expected promotion is visibly applied, and the relevant checkout total is visible. If the benefit is known to cover every charge up to the budget but DoorDash does not show a post-credit amount, omit `personal_cash` and let the ranker compute it. Recheck the winner last because carts and offers can change during the run.

This step is complete when every ranked cart has a current, like-for-like checkout total and confirmed promotion eligibility.

## 6. Rank conservatively

Save the observations as JSON and run:

```bash
python3 <skill-directory>/scripts/rank_carts.py <candidates.json>
```

Use this shape:

```json
{
  "budget": 25,
  "max_personal_cash": 0,
  "candidates": [
    {
      "restaurant": "Example Pizza",
      "cart": "2 x large cheese pizza (BOGO)",
      "checkout_total": 24.62,
      "personal_cash": 0,
      "menu_value": 38,
      "servings_low": 4,
      "servings_high": 6,
      "quantity_confidence": "high",
      "leftover_score": 2,
      "rating": 4.7,
      "eta_minutes": 35,
      "verified": true,
      "benefit_eligible": true,
      "diet_ok": true,
      "availability_ok": true,
      "promo": "BOGO",
      "url": "https://www.doordash.com/store/example"
    }
  ]
}
```

The ranker treats verification, benefit eligibility, food constraints, availability, and the personal-cash limit as gates. Among feasible carts it ranks conservative servings first, then estimate confidence, midpoint servings, leftover quality, personal cash, menu value, rating, ETA, and all-in total. Keep this ordering when ranking manually.

This step is complete when every feasible candidate is ranked and every excluded candidate has a concrete reason.

## 7. Hand off the winner

Report the observation time and a privacy-preserving delivery area. Show the top three in a compact table with merchant and link, exact cart, verified promotion, conservative servings, all-in total, personal cash, leftover quality, and ETA. Name one winner and explain the decisive comparison in one sentence. Separate delivery and pickup winners when both were evaluated.

State every material uncertainty, including benefit-coverage assumptions and low-confidence serving estimates. Mention attractive offers that failed at checkout when that prevents the user from repeating wasted work. Treat every run as perishable; never reuse an earlier winner without rechecking it live.

Leave the winning cart assembled only when the user asks. Otherwise provide the exact item list and merchant link. Stop at the final review screen and never click or activate `Place Order`, `Submit Order`, a subscription trial, or any equivalent purchase action without a new, explicit user instruction.

This step is complete when the user can review the best verified cart and understand its quantity, true cost, and tradeoffs without any order being placed.
