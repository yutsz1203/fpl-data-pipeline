select
    {{ dbt_utils.generate_surrogate_key(['season', 'gameweek_id']) }} as gameweek_key,
    season,
    gameweek_id,
    gameweek_name,
    deadline_time,
    is_finished,
    is_data_checked,
    is_previous,
    is_current,
    is_next,
    ranked_count
from {{ ref('stg_gameweeks') }}