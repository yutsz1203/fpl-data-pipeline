select
    s.run_date,
    s.team_id as bzzoiro_team_id,
    (p ->> 'id')::int as bzzoiro_player_id,
    p ->> 'name' as player_name,
    p ->> 'position' as position_code,
    (p ->> 'date_of_birth')::date as birth_date,
    p ->> 'availability' as availability,
    nullif(p ->> 'injury_type', '') as injury_type,
    (p ->> 'injury_expected_return')::date as expected_return
from {{ source('raw', 'bzzoiro_squads') }} as s
cross join lateral jsonb_array_elements(s.payload -> 'players') as p
where s.run_date = (select max(run_date) from {{ source('raw', 'bzzoiro_squads') }})
