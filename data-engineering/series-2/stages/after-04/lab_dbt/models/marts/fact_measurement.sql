-- one row per measurement: one compound, one target, one well (replicate) of one plate
select r.result_id,
       c.compound_key,
       t.target_key,
       r.run_date,
       r.plate,
       r.replicate,
       r.relation,
       r.ic50_nm,
       r.pic50,
       r.source_file
from {{ ref('stg_results') }} as r
join {{ ref('dim_compound') }} as c using (compound_id)
join {{ ref('dim_target') }} as t using (target)
