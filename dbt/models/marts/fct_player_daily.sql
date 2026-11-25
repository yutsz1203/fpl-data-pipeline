select
    {{ dbt_utils.generate_surrogate_key(['season', 'player_id', 'run_date']) }} as player_daily_key,
    season,
    {{ dbt_utils.generate_surrogate_key(['season', 'player_id']) }} as player_key,
    run_date,
    lead(run_date) over previous_day as next_run_date,
    status,
    chance_of_playing_next_round,
    news,
    price,
    price - lag(price) over previous_day as price_change,
    selected_pct,
    transfers_in_gameweek,
    transfers_out_gameweek,
    lag(run_date) over previous_day is not null and (
        status is distinct from lag(status) over previous_day
        or chance_of_playing_next_round is distinct from lag(chance_of_playing_next_round) over previous_day
        or news is distinct from lag(news) over previous_day
    ) as availability_changed
from {{ ref('stg_player_snapshots') }}
window previous_day as (partition by season, player_id order by run_date)
