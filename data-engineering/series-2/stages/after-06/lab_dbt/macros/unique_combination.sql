{% test unique_combination(model, columns) %}
-- every combination of the columns appears once: the rows returned are the ones that repeat
select {{ columns | join(', ') }}, count(*) as copies
from {{ model }}
group by {{ columns | join(', ') }}
having count(*) > 1
{% endtest %}
