select
    b.season,
    (t ->> 'id')::int as team_id,
    (t ->> 'code')::int as team_code,
    t ->> 'name' as team_name,
    t ->> 'short_name' as team_short_name,
    (t ->> 'strength_overall_home')::int as difficulty_as_visitor,
    (t ->> 'strength_overall_away')::int as difficulty_as_host
from {{ ref('base_master_latest') }} as b
cross join lateral jsonb_array_elements(b.payload -> 'teams') as t