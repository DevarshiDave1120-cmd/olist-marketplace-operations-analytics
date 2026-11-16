# Analysis definitions

Written down before any modeling (Step 3). Each change is made in a new, explained commit.

- **Analysis window:** orders purchased 2017-01-01 to 2018-08-31. Excludes the thin months
  2016-09 to 2016-12 and 2018-09 to 2018-10. Jan 2017 is kept despite being small (800 orders).
- **Customer:** `customer_unique_id`, never `customer_id`.
- **Delivered order (`is_delivered_with_date`):** `order_status = 'delivered'` and
  `order_delivered_customer_date` is not null.
- **Impossible timestamps (`has_impossible_timestamps`):** any of approved before purchase,
  carrier pickup before purchase, customer delivery before carrier pickup, customer delivery
  before purchase. These orders are excluded from delivery metrics only, and the count excluded
  is reported.
- **Delivery metrics use:** delivered orders in the window without impossible timestamps.
- **Late:** delivered on a later date than `order_estimated_delivery_date`, comparing dates not
  timestamps, since the estimate is always midnight.
- **Days late:** days from estimated delivery date to actual delivery date; negative means early.
- **Review for an order (`is_latest_review_for_order`):** the review with the latest
  `review_answer_timestamp`, ties broken by `review_creation_date` then `review_id`. Orders with
  no review are excluded from review analysis only.
- **First order:** a customer's earliest order by purchase time.
- **Repeat purchase (`repeat_within_180d`):** a qualifying order (not canceled or unavailable)
  placed after the customer's first order and within 180 days of it (purchase date ≤ first
  purchase date + 180 days).
- **Review-impact comparisons (`has_full_followup`):** only first orders purchased 2017-01-01 to
  2018-02-28, so every customer has a full 180-day follow-up inside the analysis window.
  *(Changed 2026-11-14, before any analysis: replaces "any later order in the window", which
  gave later first orders less time to repeat.)*
- **Cohort retention:** cohort is the month of first purchase. A customer is retained in month N
  if they place a qualifying order N months later, N = 1 to 6. Only cohorts with a full 6 months
  of follow-up are reported: first purchase Jan 2017 to Feb 2018.
- **Payment match:** absolute difference between payment total and item price plus freight is
  0.01 BRL or less.
- **Freight share:** freight total / (item total + freight total).
- **Geolocation point:** median lat/long per zip prefix, after dropping points outside Brazil
  (lat -34 to 5.5, lng -74 to -34).
- **Minimum volume for rankings:** lanes, states and categories are ranked only when they have at
  least 100 orders.
