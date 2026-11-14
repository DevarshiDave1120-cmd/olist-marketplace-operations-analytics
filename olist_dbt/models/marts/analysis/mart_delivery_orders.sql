-- Grain: one row per order in the delivery-metrics base (CLAUDE.md "Delivery metrics use"):
-- in analysis window, delivered with a date, no impossible timestamps.
-- Seller = primary seller (largest price + freight in the order; ties -> lowest order_item_id).
with base as (
    select *
    from {{ ref('fct_orders') }}
    where is_in_analysis_window
      and is_delivered_with_date
      and not has_impossible_timestamps
),

seller_value as (
    select order_id, seller_id,
           sum(price + freight_value) as seller_value,
           min(order_item_id)         as first_item_id
    from {{ ref('fct_order_items') }}
    group by order_id, seller_id
),

primary_seller as (
    select order_id, seller_id,
           count(*) over (partition by order_id) as seller_count
    from seller_value
    qualify row_number() over (partition by order_id
                               order by seller_value desc, first_item_id) = 1
),

geo as (
    select zip_code_prefix, latitude, longitude
    from {{ ref('stg_geolocation') }}
)

select
    b.order_id,
    b.customer_unique_id,
    b.purchase_date,
    date_trunc('month', b.purchase_date)::date      as purchase_month,
    b.customer_state,
    b.customer_zip_code_prefix,
    ps.seller_id,
    s.seller_state,
    s.seller_zip_code_prefix,
    s.seller_state || '→' || b.customer_state       as lane,
    coalesce(ps.seller_count > 1, false)            as is_multi_seller,
    b.estimated_delivery_date,
    b.delivered_date,
    b.days_late,
    b.is_late,
    haversine(s.seller_latitude, s.seller_longitude, cg.latitude, cg.longitude)
                                                    as distance_km  -- null if either point missing
from base b
left join primary_seller ps on b.order_id = ps.order_id
left join {{ ref('dim_sellers') }} s on ps.seller_id = s.seller_id
left join geo cg on b.customer_zip_code_prefix = cg.zip_code_prefix
