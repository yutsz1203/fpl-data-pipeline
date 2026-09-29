{% test rows_per_season(model, expected) %}

select
    season,
    count(*) as n_rows
from {{ model }}
group by season
having count(*) <> {{ expected }}

{% endtest %}
