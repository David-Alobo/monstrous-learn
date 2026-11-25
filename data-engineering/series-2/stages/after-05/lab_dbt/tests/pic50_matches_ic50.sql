-- every pIC50 is 9 - log10 of its IC50 in nanomolar
select result_id, ic50_nm, pic50
from {{ ref('fact_measurement') }}
where abs(pic50 - (9 - log10(ic50_nm))) > 1e-9
