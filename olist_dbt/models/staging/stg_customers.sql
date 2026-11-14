-- One row per customer_id (one per order). The person is customer_unique_id.
select
    customer_id,
    customer_unique_id,
    customer_zip_code_prefix,
    customer_city,
    customer_state
from {{ source('raw', 'customers') }}
