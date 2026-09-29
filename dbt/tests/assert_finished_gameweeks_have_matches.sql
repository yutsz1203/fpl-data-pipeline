select
    g.season,
    g.gameweek_id
from {{ ref('dim_gameweek') }} as g
where g.is_finished
    and g.is_data_checked
    and not exists (
        select 1
        from {{ ref('fct_player_match') }} as f
        where f.gameweek_key = g.gameweek_key
    )
