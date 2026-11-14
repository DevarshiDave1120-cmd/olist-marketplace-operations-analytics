-- Grain: one row per order item (order_id, order_item_id).
select
    i.order_id || '-' || i.order_item_id as order_item_key,
    i.order_id,
    i.order_item_id,
    i.product_id,
    i.seller_id,
    o.purchased_at::date                 as purchase_date,
    i.shipping_limit_at,
    i.price,
    i.freight_value
from {{ ref('stg_order_items') }} i
join {{ ref('stg_orders') }} o using (order_id)
