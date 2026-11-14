-- One row per raw review row; key is (review_id, order_id) because review_id repeats
-- across orders. Flag picks one review per order (CLAUDE.md "Review for an order").
with renamed as (
    select
        review_id,
        order_id,
        review_score,
        review_comment_title,
        review_comment_message,
        review_creation_date    as review_created_at,
        review_answer_timestamp as review_answered_at
    from {{ source('raw', 'order_reviews') }}
)

select
    *,
    row_number() over (
        partition by order_id
        order by review_answered_at desc nulls last,
                 review_created_at desc nulls last,
                 review_id desc  -- final tie-break only for determinism
    ) = 1 as is_latest_review_for_order
from renamed
