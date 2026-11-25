-- one row per day of the project, with each way the lab groups days
with days as (
    select day::date as date_key
    from generate_series(date '{{ var("project_start") }}', date '{{ var("project_end") }}',
                         interval 1 day) as t(day)
)
select date_key,
       (datediff('day', date '{{ var("project_start") }}', date_key) // 7) + 1 as project_week,
       isodow(date_key) > 5   as weekend,
       dayname(date_key)      as weekday,
       monthname(date_key)    as month
from days
