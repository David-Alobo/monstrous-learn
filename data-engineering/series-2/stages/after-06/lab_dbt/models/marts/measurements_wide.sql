{{ config(materialized='view') }}
-- the star joined once, for dashboards and spreadsheets
select f.result_id, f.plate, f.replicate, f.relation, f.ic50_nm, f.pic50,
       c.compound_id, c.parent_smiles, c.series, c.chemist, c.vendor, c.mw, c.clogp,
       t.target, t.role as target_role,
       d.date_key as run_date, d.project_week as run_week
from {{ ref('fact_measurement') }} as f
join {{ ref('dim_compound') }} as c using (compound_key)
join {{ ref('dim_target') }} as t using (target_key)
join {{ ref('dim_date') }} as d on d.date_key = f.run_date
where f.status <> 'superseded'  -- a corrected reading replaces it
