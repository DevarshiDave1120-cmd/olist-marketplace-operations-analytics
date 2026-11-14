-- Grain: one row per (cohort_month, month_number), month_number 1..6.
-- Cohort = month of first purchase; only cohorts Jan 2017..Feb 2018 (full 6-month follow-up).
-- Retained in month N = a qualifying order (in window, not canceled/unavailable)
-- in the calendar month N months after the cohort month.
with customers as (
    select customer_unique_id, first_order_month as cohort_month
    from {{ ref('dim_customers') }}
    where first_order_month between '2017-01-01' and '2018-02-01'
),

qualifying_orders as (
    select customer_unique_id, date_trunc('month', purchased_at)::date as order_month
    from {{ ref('fct_orders') }}
    where is_in_analysis_window
      and order_status not in ('canceled', 'unavailable')
),

activity as (
    select distinct c.customer_unique_id, c.cohort_month,
           datediff(month, c.cohort_month, q.order_month) as month_number
    from customers c
    join qualifying_orders q using (customer_unique_id)
    where datediff(month, c.cohort_month, q.order_month) between 1 and 6
),

grid as (
    select c.cohort_month, m.month_number, count(*) as cohort_size
    from customers c
    cross join (select row_number() over (order by seq4()) as month_number
                from table(generator(rowcount => 6))) m
    group by c.cohort_month, m.month_number
)

select
    g.cohort_month,
    g.month_number,
    g.cohort_size,
    count(a.customer_unique_id)                   as retained_customers,
    count(a.customer_unique_id) / g.cohort_size   as retention_rate
from grid g
left join activity a
    on g.cohort_month = a.cohort_month and g.month_number = a.month_number
group by g.cohort_month, g.month_number, g.cohort_size
