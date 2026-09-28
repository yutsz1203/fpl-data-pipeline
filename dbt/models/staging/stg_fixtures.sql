select
    b.season,
    (f ->> 'id')::int as fixture_id,
    (f ->> 'event')::int as gameweek_id,
    (f ->> 'kickoff_time')::timestamptz as kickoff_time,
    (f ->> 'team_h')::int as home_team_id,
    (f ->> 'team_a')::int as away_team_id,
    (f ->> 'team_h_score')::int as home_team_score,
    (f ->> 'team_a_score')::int as away_team_score,
    (f ->> 'team_h_difficulty')::int as difficulty_for_home_team,
    (f ->> 'team_a_difficulty')::int as difficulty_for_away_team,
    (f ->> 'finished')::boolean as is_finished
from {{ ref('base_fixtures_latest') }} as b
cross join lateral jsonb_array_elements(b.payload) as f