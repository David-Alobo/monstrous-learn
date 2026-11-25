-- one row per result: the unit columns joined back together, every value in nanomolar
with typed as (
    select result_id, compound_id, target, plate,
           replicate::integer      as replicate,
           relation,
           value::double           as value,
           coalesce(unit, units)   as unit,  -- 'units' was renamed 'unit' in week 5
           run_date::date          as run_date,
           file_name
    from {{ source('raw', 'assay') }}
)
select typed.* exclude (file_name),
       value * u.factor              as ic50_nm,
       9 - log10(value * u.factor)   as pic50,
       relation = '='                as is_measured,  -- a value, not a bound
       file_name                     as source_file
from typed
left join {{ ref('unit_to_nm') }} as u using (unit)
