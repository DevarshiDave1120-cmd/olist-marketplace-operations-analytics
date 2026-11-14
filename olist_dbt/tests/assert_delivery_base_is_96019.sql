-- Delivery-metrics base (window, delivered with date, no impossible timestamps) must be
-- 96,019 orders, as computed in Step 3 (docs/staging_counts.md).
select count(*) as delivery_base_orders
from {{ ref('mart_delivery_orders') }}
having count(*) <> 96019
