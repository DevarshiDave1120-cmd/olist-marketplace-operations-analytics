-- Grain: one row per seller_id. Coordinates from the seller zip's median point.
select
    s.seller_id,
    s.seller_zip_code_prefix,
    s.seller_city,
    s.seller_state,
    g.latitude  as seller_latitude,
    g.longitude as seller_longitude
from {{ ref('stg_sellers') }} s
left join {{ ref('stg_geolocation') }} g
    on s.seller_zip_code_prefix = g.zip_code_prefix
