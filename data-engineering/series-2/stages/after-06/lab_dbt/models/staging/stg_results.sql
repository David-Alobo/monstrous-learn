-- one row per result, every reading kept with its status; every value in nanomolar
{%- set columns = adapter.get_columns_in_relation(source('raw', 'assay'))
    | map(attribute='name') | list %}
with typed as (
    select result_id, compound_id, target, plate,
           replicate::integer      as replicate,
           relation,
           value::double           as value,
           -- 'units' was renamed 'unit' in week 5
           {% if 'unit' in columns %}coalesce(unit, units){% else %}units{% endif %}
                                   as unit,
           -- 'status' arrived in week 8: superseded, corrected or final
           {% if 'status' in columns %}coalesce(status, 'final'){% else %}'final'{% endif %}
                                   as status,
           run_date::date          as run_date,
           file_name,
           _dlt_load_id            as load_id
    from {{ source('raw', 'assay') }}
)
select typed.* exclude (file_name),
       value * u.factor              as ic50_nm,
       9 - log10(value * u.factor)   as pic50,
       relation = '='                as is_measured,  -- a value, not a bound
       file_name                     as source_file
from typed
left join {{ ref('unit_to_nm') }} as u using (unit)
