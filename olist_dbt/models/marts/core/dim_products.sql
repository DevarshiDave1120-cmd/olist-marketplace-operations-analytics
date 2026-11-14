-- Grain: one row per product_id.
select
    product_id,
    category_name_en,
    category_name_pt,
    has_category,
    is_category_translated,
    product_name_length,
    product_description_length,
    product_photos_qty,
    product_weight_g,
    product_length_cm,
    product_height_cm,
    product_width_cm
from {{ ref('stg_products') }}
