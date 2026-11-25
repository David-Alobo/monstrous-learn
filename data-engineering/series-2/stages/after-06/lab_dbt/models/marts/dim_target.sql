-- one row per kinase; the primary target gets key 1
select row_number() over (order by role desc, target) as target_key,
       target, chembl_id, role
from {{ ref('targets') }}
