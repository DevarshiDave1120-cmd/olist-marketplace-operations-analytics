-- Grain: one row per customer's first order (one per customer_unique_id; docs/analysis_definitions.md "First order").
-- All customers kept; filter with the flags:
--   has_full_followup   -> first purchase 2017-01-01..2018-02-28 (full 180-day follow-up);
--                          review-impact comparisons use only these rows.
--   is_in_delivery_base -> is_late is meaningful; has_review -> review_score is meaningful.
-- repeat_within_180d = a later order, not canceled/unavailable, purchased within 180 days
-- of the first purchase date (docs/analysis_definitions.md "Repeat purchase").
with orders as (
    select o.*,
           row_number() over (partition by customer_unique_id
                              order by purchased_at, order_id) as order_seq
    from {{ ref('fct_orders') }} o
),

first_orders as (
    select * from orders where order_seq = 1
),

repeaters as (
    select distinct o.customer_unique_id
    from orders o
    join first_orders f on o.customer_unique_id = f.customer_unique_id
    where o.order_seq > 1
      and o.order_status not in ('canceled', 'unavailable')
      and o.purchase_date <= dateadd(day, 180, f.purchase_date)
)

select
    f.customer_unique_id,
    f.order_id                                     as first_order_id,
    f.purchase_date                                as first_purchase_date,
    date_trunc('month', f.purchase_date)::date     as first_purchase_month,
    f.order_status,
    f.customer_state,
    f.is_in_analysis_window,
    f.purchase_date between '2017-01-01'::date and '2018-02-28'::date
                                                   as has_full_followup,
    (f.is_in_analysis_window and f.is_delivered_with_date and not f.has_impossible_timestamps)
                                                   as is_in_delivery_base,
    f.is_late,
    f.days_late,
    f.has_review,
    f.review_score,
    r.customer_unique_id is not null               as repeat_within_180d
from first_orders f
left join repeaters r on f.customer_unique_id = r.customer_unique_id
