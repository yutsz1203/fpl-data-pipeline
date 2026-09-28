select
    {{ dbt_utils.generate_surrogate_key(['season', 'team_id']) }} as team_key,
    season,
    team_id,
    team_code,
    team_name,
    team_short_name,
    difficulty_as_host,
    difficulty_as_visitor
from {{ ref('stg_teams') }}