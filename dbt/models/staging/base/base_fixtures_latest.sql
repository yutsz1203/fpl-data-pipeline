select distinct on (s.season)
    s.season,
    f.run_date,
    f.payload
from {{ source('raw', 'fixtures') }} as f
join {{ ref('base_snapshot_seasons') }} as s using (run_date)
order by s.season, f.run_date desc
