-- Grain: one row per calendar day, 2016-01-01 to 2020-12-31 (covers every date in the data,
-- including shipping_limit_date values out to 2020).
with days as (
    select dateadd(day, row_number() over (order by seq4()) - 1, '2016-01-01'::date) as date_day
    from table(generator(rowcount => 1827))
)

select
    date_day,
    year(date_day)                       as year,
    quarter(date_day)                    as quarter,
    month(date_day)                      as month,
    date_trunc('month', date_day)::date  as month_start,
    dayofweekiso(date_day)               as day_of_week_iso,
    dayname(date_day)                    as day_name,
    dayofweekiso(date_day) in (6, 7)     as is_weekend,
    date_day between '{{ var("analysis_start_date") }}'::date
                 and '{{ var("analysis_end_date") }}'::date as is_in_analysis_window
from days
where date_day <= '2020-12-31'::date
