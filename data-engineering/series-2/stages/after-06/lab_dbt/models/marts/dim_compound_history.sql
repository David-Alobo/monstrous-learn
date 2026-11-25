-- every version of every compound (SCD type 2), dated by the lab's own exports
with versions as (
    select compound_id,
           split_part(smiles, '.', 1)  as parent_smiles,
           coalesce(salt, '')          as salt,
           chemist,
           vendor,
           registered_on::date         as registered_on,
           regexp_extract(file_name, '\d{4}-\d{2}-\d{2}')::date as valid_from,
           dbt_valid_to is null        as is_current,
           dbt_valid_from              as snapshot_from
    from {{ ref('registry_history') }}
)
select row_number() over (order by compound_id, snapshot_from) as compound_version_key,
       compound_id,
       row_number() over (partition by compound_id order by snapshot_from) as version,
       parent_smiles, salt, chemist, vendor, registered_on,
       valid_from,
       lead(valid_from) over (partition by compound_id order by snapshot_from) as valid_to,
       is_current
from versions
