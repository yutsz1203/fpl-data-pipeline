with dim_counts as (

    select
        season,
        count(*) as dim_players
    from {{ ref('dim_player') }}
    group by season

),

fact_counts as (

    select
        season,
        count(distinct player_key) as fact_players
    from {{ ref('fct_player_match') }}
    group by season

),

played_seasons as (

    select distinct season
    from {{ ref('dim_gameweek') }}
    where is_finished and is_data_checked

)

select
    d.season,
    d.dim_players,
    coalesce(f.fact_players, 0) as fact_players
from dim_counts as d
join played_seasons as s using (season)
left join fact_counts as f using (season)
where coalesce(f.fact_players, 0) < 0.9 * d.dim_players
