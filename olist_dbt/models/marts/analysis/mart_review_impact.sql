-- Grain: one row per customer's first order (one per customer_unique_id; CLAUDE.md "First order").
-- All customers kept; filter with the flags:
--   is_in_delivery_base -> is_late is meaningful; has_review -> review_score is meaningful.
-- made_repeat_purchase = any later order in the window that is not canceled/unavailable.
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
    select distinct customer_unique_id
    from orders
    where order_seq > 1
      and is_in_analysis_window
      and order_status not in ('canceled', 'unavailable')
)

select
    f.customer_unique_id,
    f.order_id                                     as first_order_id,
    f.purchase_date                                as first_purchase_date,
    date_trunc('month', f.purchase_date)::date     as first_purchase_month,
    f.order_status,
    f.customer_state,
    f.is_in_analysis_window,
    (f.is_in_analysis_window and f.is_delivered_with_date and not f.has_impossible_timestamps)
                                                   as is_in_delivery_base,
    f.is_late,
    f.days_late,
    f.has_review,
    f.review_score,
    r.customer_unique_id is not null               as made_repeat_purchase
from first_orders f
left join repeaters r on f.customer_unique_id = r.customer_unique_id
