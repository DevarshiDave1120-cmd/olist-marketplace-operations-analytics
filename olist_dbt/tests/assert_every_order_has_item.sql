-- Every order in fct_orders should have at least one row in fct_order_items.
-- Set to warn: the raw profile found 775 orders with payments but no items (Step 5 investigates).
{{ config(severity='warn') }}

select o.order_id, o.order_status
from {{ ref('fct_orders') }} o
left join {{ ref('fct_order_items') }} i using (order_id)
where i.order_id is null
