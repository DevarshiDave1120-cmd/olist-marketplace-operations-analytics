-- Grain: one row per order in fct_orders (all orders, any status/date; filter with flags).
-- reason_category: first matching rule wins, so every order gets exactly one category.
-- Categories 5-6 are explanations consistent with the data, not proven causes.
with payment_features as (
    select order_id,
           max(payment_installments)                                          as max_installments,
           count_if(payment_type = 'credit_card' and payment_installments > 1) > 0
                                                                              as has_credit_card_installments,
           count_if(payment_type = 'voucher') > 0                             as has_voucher
    from {{ ref('stg_order_payments') }}
    group by order_id
),

orders as (
    select
        o.order_id,
        o.order_status,
        o.is_in_analysis_window,
        o.item_count,
        o.item_total,
        o.freight_total,
        o.item_total + o.freight_total               as items_plus_freight,
        o.payment_count,
        o.payment_total,
        o.payment_total - (o.item_total + o.freight_total) as difference,
        coalesce(pf.has_credit_card_installments, false) as has_credit_card_installments,
        coalesce(pf.has_voucher, false)              as has_voucher,
        pf.max_installments
    from {{ ref('fct_orders') }} o
    left join payment_features pf using (order_id)
)

select
    *,
    case
        when item_count is null and payment_count is null then 'no_items_no_payments'
        when item_count is null                          then 'payment_without_items'
        when payment_count is null                       then 'items_without_payment'
        when abs(difference) <= 0.01                     then 'matches'
        when difference > 0.01 and has_credit_card_installments then 'installment_interest'
        when difference > 0.01 and has_voucher           then 'voucher_overpayment'
        else 'unexplained'
    end as reason_category
from orders
