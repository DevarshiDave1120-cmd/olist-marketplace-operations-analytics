-- One row per product. Typos in source column names fixed; category translated to English.
-- Untranslated categories fall back to the Portuguese name and are flagged.
with products as (
    select * from {{ source('raw', 'products') }}
),

translation as (
    select * from {{ ref('stg_product_category_translation') }}
)

select
    p.product_id,
    p.product_category_name                         as category_name_pt,
    coalesce(t.category_name_en, p.product_category_name) as category_name_en,
    p.product_name_lenght                           as product_name_length,
    p.product_description_lenght                    as product_description_length,
    p.product_photos_qty,
    p.product_weight_g,
    p.product_length_cm,
    p.product_height_cm,
    p.product_width_cm,
    p.product_category_name is not null             as has_category,
    t.category_name_en is not null                  as is_category_translated
from products p
left join translation t
    on p.product_category_name = t.category_name_pt
