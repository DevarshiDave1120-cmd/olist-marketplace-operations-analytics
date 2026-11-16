-- Grain: one row per (dimension, group_value), dimension in customer_state | product_category.
-- Base: orders in the analysis window, with items, status not canceled/unavailable.
-- Freight share = freight total / (item total + freight total) (docs/analysis_definitions.md "Freight share").
-- Category is item-level, so an order can count in several categories; order_count is distinct orders.
with base_items as (
    select
        i.order_id,
        o.customer_state,
        coalesce(p.category_name_en, 'unknown') as product_category,
        i.price,
        i.freight_value
    from {{ ref('fct_order_items') }} i
    join {{ ref('fct_orders') }} o using (order_id)
    left join {{ ref('dim_products') }} p using (product_id)
    where o.is_in_analysis_window
      and o.order_status not in ('canceled', 'unavailable')
),

unpivoted as (
    select 'customer_state' as dimension, customer_state as group_value, * from base_items
    union all
    select 'product_category', product_category, * from base_items
)

select
    dimension,
    group_value,
    count(distinct order_id)                              as order_count,
    count(*)                                              as item_count,
    sum(price)                                            as item_total,
    sum(freight_value)                                    as freight_total,
    sum(freight_value) / nullif(sum(price) + sum(freight_value), 0) as freight_share
from unpivoted
group by dimension, group_value
