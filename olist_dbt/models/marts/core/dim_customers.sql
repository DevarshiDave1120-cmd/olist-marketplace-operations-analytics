-- Grain: one row per customer_unique_id (the person; CLAUDE.md "Customer").
-- Location attributes are taken from the customer's first order.
with orders as (
    select o.order_id, o.purchased_at, o.is_in_analysis_window,
           c.customer_unique_id, c.customer_zip_code_prefix, c.customer_city, c.customer_state
    from {{ ref('stg_orders') }} o
    join {{ ref('stg_customers') }} c using (customer_id)
),

ranked as (
    select *,
           row_number() over (partition by customer_unique_id
                              order by purchased_at, order_id) as order_seq
    from orders
)

select
    customer_unique_id,
    max(iff(order_seq = 1, order_id, null))                 as first_order_id,
    min(purchased_at)                                       as first_order_at,
    min(purchased_at)::date                                 as first_order_date,
    date_trunc('month', min(purchased_at))::date            as first_order_month,
    max(iff(order_seq = 1, customer_state, null))           as customer_state,
    max(iff(order_seq = 1, customer_city, null))            as customer_city,
    max(iff(order_seq = 1, customer_zip_code_prefix, null)) as customer_zip_code_prefix,
    count(*)                                                as order_count,
    count_if(is_in_analysis_window)                         as order_count_in_window
from ranked
group by customer_unique_id
