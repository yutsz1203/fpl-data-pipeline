select
    b.season,
    b.player_id,
    b.run_date,
    (h ->> 'element')::int as element
from {{ ref('base_player_summary_latest') }} as b
cross join lateral jsonb_array_elements(b.payload -> 'history') as h
where (h ->> 'element')::int <> b.player_id
