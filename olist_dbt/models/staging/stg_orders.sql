-- One row per order. All raw rows kept; flags follow docs/analysis_definitions.md "Analysis definitions".
with source as (
    select * from {{ source('raw', 'orders') }}
),

renamed as (
    select
        order_id,
        customer_id,
        order_status,
        order_purchase_timestamp            as purchased_at,
        order_approved_at                   as approved_at,
        order_delivered_carrier_date        as delivered_to_carrier_at,
        order_delivered_customer_date       as delivered_to_customer_at,
        order_estimated_delivery_date::date as estimated_delivery_date
    from source
)

select
    *,

    purchased_at::date between '{{ var("analysis_start_date") }}'::date
                           and '{{ var("analysis_end_date") }}'::date
        as is_in_analysis_window,

    (order_status = 'delivered' and delivered_to_customer_at is not null)
        as is_delivered_with_date,

    -- Comparisons with a null timestamp evaluate to null -> coalesced to false.
    coalesce(approved_at < purchased_at, false)
        or coalesce(delivered_to_carrier_at < purchased_at, false)
        or coalesce(delivered_to_customer_at < delivered_to_carrier_at, false)
        or coalesce(delivered_to_customer_at < purchased_at, false)
        as has_impossible_timestamps

from renamed
