{% set recent_games = 5 %}
{% set prior_nineties = 3 %}

with games as (

    select
        f.player_key,
        f.minutes,
        f.starts,
        case
            when d.player_key is null then f.minutes = 0
            else d.status in ('i', 's', 'u', 'n') or coalesce(d.chance_of_playing_next_round, 100) = 0
        end as was_unavailable,
        x.kickoff_time
    from {{ ref('fct_player_match') }} as f
    inner join {{ ref('dim_fixture') }} as x
        on x.fixture_key = f.fixture_key
    left join {{ ref('fct_player_daily') }} as d
        on d.player_key = f.player_key
        and d.run_date <= (x.kickoff_time at time zone 'UTC')::date
        and (d.next_run_date is null or d.next_run_date > (x.kickoff_time at time zone 'UTC')::date)

),

available_games as (

    select
        player_key,
        minutes,
        starts,
        row_number() over (partition by player_key order by kickoff_time desc) as recency
    from games
    where not was_unavailable

),

recent as (

    select
        player_key,
        count(*) as games,
        count(*) filter (where minutes > 0) as appearances,
        sum(starts) as starts,
        sum(minutes) as minutes,
        count(*) filter (where minutes >= 60) as games_60
    from available_games
    where recency <= {{ recent_games }}
    group by player_key

),

season_totals as (

    select
        player_key,
        count(*) filter (where minutes > 0) as appearances,
        sum(minutes) as minutes,
        sum(expected_goals) as xg,
        sum(expected_assists) as xa,
        sum(expected_goals_conceded) as xgc,
        sum(saves) as saves,
        sum(bonus) as bonus,
        sum(yellow_cards) as yellow_cards,
        count(*) filter (where defcon_points > 0) as defcon_hits
    from {{ ref('fct_player_match') }}
    group by player_key

),

team_scale as (

    select
        team_key,
        sum(expected_goals) / count(distinct fixture_key) as team_xg_per_game
    from {{ ref('fct_player_match') }}
    group by team_key

),

position_rates as (

    select
        season,
        position_key,
        sum(expected_goals) * 90 / nullif(sum(minutes), 0) as xg_per_90,
        sum(expected_assists) * 90 / nullif(sum(minutes), 0) as xa_per_90,
        sum(bonus) * 90.0 / nullif(sum(minutes), 0) as bonus_per_90,
        sum(yellow_cards) * 90.0 / nullif(sum(minutes), 0) as yellow_cards_per_90,
        sum(saves) / nullif(sum(expected_goals_conceded), 0) as saves_per_xgc,
        count(*) filter (where defcon_points > 0)::numeric / nullif(count(*) filter (where minutes > 0), 0) as defcon_hit_rate
    from {{ ref('fct_player_match') }}
    group by season, position_key

),

rates as (

    select
        p.player_key,
        p.season,
        p.team_key,
        p.position_key,
        case
            when p.chance_of_playing_next_round is not null then p.chance_of_playing_next_round / 100.0
            when p.status = 'a' then 1
            when p.status = 'd' then 0.5
            else 0
        end as availability,
        coalesce(r.games, 0) as recent_games,
        coalesce(r.appearances, 0) as recent_appearances,
        coalesce(r.starts, 0) as recent_starts,
        coalesce(r.minutes, 0) as recent_minutes,
        coalesce(r.games_60, 0) as recent_games_60,
        coalesce(s.minutes, 0) as season_minutes,
        t.team_xg_per_game,
        (coalesce(s.xg, 0) + pr.xg_per_90 * {{ prior_nineties }}) / (coalesce(s.minutes, 0) / 90.0 + {{ prior_nineties }}) as xg_per_90,
        (coalesce(s.xa, 0) + pr.xa_per_90 * {{ prior_nineties }}) / (coalesce(s.minutes, 0) / 90.0 + {{ prior_nineties }}) as xa_per_90,
        (coalesce(s.bonus, 0) + pr.bonus_per_90 * {{ prior_nineties }}) / (coalesce(s.minutes, 0) / 90.0 + {{ prior_nineties }}) as bonus_per_90,
        (coalesce(s.yellow_cards, 0) + pr.yellow_cards_per_90 * {{ prior_nineties }}) / (coalesce(s.minutes, 0) / 90.0 + {{ prior_nineties }}) as yellow_cards_per_90,
        (coalesce(s.saves, 0) + coalesce(pr.saves_per_xgc, 0) * {{ prior_nineties }}) / (coalesce(s.xgc, 0) + {{ prior_nineties }}) as saves_per_xgc,
        (coalesce(s.defcon_hits, 0) + pr.defcon_hit_rate * {{ prior_nineties }}) / (coalesce(s.appearances, 0) + {{ prior_nineties }}) as defcon_hit_rate
    from {{ ref('dim_player') }} as p
    left join recent as r
        on r.player_key = p.player_key
    left join season_totals as s
        on s.player_key = p.player_key
    left join team_scale as t
        on t.team_key = p.team_key
    left join position_rates as pr
        on pr.season = p.season and pr.position_key = p.position_key

)

select
    player_key,
    season,
    team_key,
    position_key,
    availability::numeric(3,2) as availability,
    recent_games,
    recent_appearances,
    recent_starts,
    recent_minutes,
    season_minutes,
    round(recent_starts::numeric / nullif(recent_games, 0), 2) as start_rate,
    round(recent_minutes::numeric / nullif(recent_games, 0), 1) as minutes_per_game,
    round(recent_appearances::numeric / nullif(recent_games, 0), 2) as play_rate,
    round(recent_games_60::numeric / nullif(recent_games, 0), 2) as sixty_rate,
    round(availability * recent_minutes / nullif(recent_games, 0), 0)::int as expected_minutes,
    round(xg_per_90, 3) as xg_per_90,
    round(xa_per_90, 3) as xa_per_90,
    round(xg_per_90 / nullif(team_xg_per_game, 0), 3) as xg_share,
    round(xa_per_90 / nullif(team_xg_per_game, 0), 3) as xa_share,
    round(bonus_per_90, 3) as bonus_per_90,
    round(yellow_cards_per_90, 3) as yellow_cards_per_90,
    round(saves_per_xgc, 3) as saves_per_xgc,
    round(defcon_hit_rate, 3) as defcon_hit_rate
from rates
