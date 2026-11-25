-- one row per reading (superseded ones included, with their status); built incrementally
{{ config(materialized='incremental', unique_key='result_id', on_schema_change='fail') }}
select r.result_id,
       c.compound_key,
       t.target_key,
       r.run_date,
       r.plate,
       r.replicate,
       r.relation,
       r.ic50_nm,
       r.pic50,
       r.status,
       r.source_file,
       r.load_id
from {{ ref('stg_results') }} as r
join {{ ref('dim_compound') }} as c using (compound_id)
join {{ ref('dim_target') }} as t using (target)
{% if is_incremental() %}
-- only the loads that arrived since the last build
where r.load_id > (select max(load_id) from {{ this }})
{% endif %}
