-- Grain: one row per order_id (all orders kept; filter with the flags).
-- Items, payments and reviews are aggregated to order level BEFORE joining to avoid fan-out.
with orders as (
    select * from {{ ref('stg_orders') }}
),

customers as (
    select * from {{ ref('stg_customers') }}
),

items as (
    select order_id,
           count(*)           as item_count,
           sum(price)         as item_total,
           sum(freight_value) as freight_total
    from {{ ref('stg_order_items') }}
    group by order_id
),

payments as (
    select order_id,
           count(*)           as payment_count,
           sum(payment_value) as payment_total
    from {{ ref('stg_order_payments') }}
    group by order_id
),

reviews as (
    select order_id, review_id, review_score
    from {{ ref('stg_order_reviews') }}
    where is_latest_review_for_order
)

select
    o.order_id,
    o.customer_id,
    c.customer_unique_id,
    c.customer_zip_code_prefix,
    c.customer_state,
    o.order_status,

    o.purchased_at,
    o.purchased_at::date               as purchase_date,
    o.approved_at,
    o.delivered_to_carrier_at          as shipped_at,
    o.delivered_to_customer_at         as delivered_at,
    o.delivered_to_customer_at::date   as delivered_date,
    o.estimated_delivery_date,

    -- docs/analysis_definitions.md: Days late / Late compare dates, only for delivered orders with a date.
    iff(o.is_delivered_with_date,
        datediff(day, o.estimated_delivery_date, o.delivered_to_customer_at::date), null)
        as days_late,
    iff(o.is_delivered_with_date,
        o.delivered_to_customer_at::date > o.estimated_delivery_date, null)
        as is_late,

    i.item_count,
    i.item_total,
    i.freight_total,
    p.payment_count,
    p.payment_total,

    r.review_id,
    r.review_score,
    r.review_id is not null            as has_review,

    o.is_in_analysis_window,
    o.is_delivered_with_date,
    o.has_impossible_timestamps
from orders o
left join customers c using (customer_id)
left join items     i using (order_id)
left join payments  p using (order_id)
left join reviews   r using (order_id)
