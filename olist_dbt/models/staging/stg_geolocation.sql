{{ config(materialized='table') }}

-- One row per zip prefix (grain change from ~1M raw rows).
-- Point = median lat / median lng of the zip's points inside Brazil's bounding box
-- (lat -34 to 5.5, lng -74 to -34); see docs/analysis_definitions.md "Geolocation point".
-- Zips whose points are all outside the box keep a row with null coordinates.
with source as (
    select
        geolocation_zip_code_prefix as zip_code_prefix,
        geolocation_lat,
        geolocation_lng,
        geolocation_city,
        geolocation_state,
        geolocation_lat between -34 and 5.5
            and geolocation_lng between -74 and -34 as is_inside_brazil
    from {{ source('raw', 'geolocation') }}
)

select
    zip_code_prefix,
    median(iff(is_inside_brazil, geolocation_lat, null)) as latitude,
    median(iff(is_inside_brazil, geolocation_lng, null)) as longitude,
    mode(geolocation_state)                               as state,
    mode(geolocation_city)                                as city,
    count(*)                                              as raw_point_count,
    count_if(is_inside_brazil)                            as valid_point_count,
    count_if(is_inside_brazil) > 0                        as has_valid_point
from source
group by zip_code_prefix
