select
    s.season,
    m.run_date,
    (e ->> 'id')::int as player_id,
    e ->> 'status' as status,
    (e ->> 'chance_of_playing_next_round')::int as chance_of_playing_next_round,
    nullif(e ->> 'news', '') as news,
    ((e ->> 'now_cost')::numeric/10)::numeric(4,1) as price,
    (e ->> 'selected_by_percent')::numeric(4,1) as selected_pct,
    (e ->> 'transfers_in_event')::int as transfers_in_gameweek,
    (e ->> 'transfers_out_event')::int as transfers_out_gameweek
from {{ source('raw', 'master') }} as m
join {{ ref('base_snapshot_seasons') }} as s using (run_date)
cross join lateral jsonb_array_elements(m.payload -> 'elements') as e
