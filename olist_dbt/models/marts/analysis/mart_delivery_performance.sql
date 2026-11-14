-- Grain: one row per (dimension, group_value), dimension in
-- customer_state | seller_state | lane | purchase_month. Built from mart_delivery_orders.
-- order_count is kept so small groups can be filtered in analysis.
with orders as (
    select * from {{ ref('mart_delivery_orders') }}
),

unpivoted as (
    select 'customer_state' as dimension, customer_state as group_value, * from orders
    union all
    select 'seller_state', seller_state, * from orders
    union all
    select 'lane', lane, * from orders
    union all
    select 'purchase_month', to_char(purchase_month, 'YYYY-MM'), * from orders
)

select
    dimension,
    group_value,
    count(*)                         as order_count,
    count_if(is_late)                as late_count,
    count_if(is_late) / count(*)     as late_rate,
    avg(days_late)                   as avg_days_late,
    count(distance_km)               as orders_with_distance,
    avg(distance_km)                 as avg_distance_km
from unpivoted
group by dimension, group_value
