select
    {{ dbt_utils.generate_surrogate_key(['f.season', 'f.fixture_id']) }} as fixture_key,
     f.season, 
     fixture_id, 
     gameweek_id, 
     kickoff_time, 
     h.team_short_name || ' v ' || a.team_short_name as fixture_name,
     h.team_name as home_team_name, 
     a.team_name as away_team_name,
     home_team_score,
     away_team_score,
     difficulty_for_home_team,
     difficulty_for_away_team,
     is_finished
from {{ ref('stg_fixtures') }} as f
left join {{ ref('stg_teams') }} as h
     on h.team_id = f.home_team_id and h.season = f.season
left join {{ ref('stg_teams') }} as a
     on a.team_id = f.away_team_id and a.season = f.season