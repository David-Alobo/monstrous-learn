-- the current registry: one row per compound, the salt split from the parent that was tested
select compound_id,
       smiles                      as smiles_as_registered,
       split_part(smiles, '.', 1)  as parent_smiles,
       coalesce(salt, '')          as salt,
       batch::integer              as batch,
       chemist,
       vendor,
       registered_on::date         as registered_on
from {{ source('raw', 'registry') }}
