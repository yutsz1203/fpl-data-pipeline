select distinct on (s.season, p.player_id)
    s.season,
    p.player_id,
    p.run_date,
    p.payload
from {{ source('raw', 'player_summary') }} as p
join {{ ref('base_snapshot_seasons') }} as s using (run_date)
order by s.season, p.player_id, p.run_date desc
