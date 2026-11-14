-- Every order in fct_orders appears in mart_payment_reconciliation, and nothing else does.
-- With unique(order_id) + not_null/accepted_values(reason_category), this proves every order
-- lands in exactly one reconciliation category.
select coalesce(f.order_id, r.order_id) as order_id,
       f.order_id is null as only_in_reconciliation,
       r.order_id is null as missing_from_reconciliation
from {{ ref('fct_orders') }} f
full outer join {{ ref('mart_payment_reconciliation') }} r using (order_id)
where f.order_id is null or r.order_id is null
