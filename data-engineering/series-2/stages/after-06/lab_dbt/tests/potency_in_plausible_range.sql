{{ config(severity='warn') }}
-- measured potencies outside 3 to 10 are possible but rare: a person should look
select result_id, compound_key, target_key, pic50
from {{ ref('fact_measurement') }}
where relation = '=' and (pic50 < 3 or pic50 > 10)
