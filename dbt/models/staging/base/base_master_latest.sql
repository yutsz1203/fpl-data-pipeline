select distinct on (s.season)
    s.season,
    m.run_date,
    m.payload
from {{ source('raw', 'master') }} as m
join {{ ref('base_snapshot_seasons') }} as s using (run_date)
order by s.season, m.run_date desc
