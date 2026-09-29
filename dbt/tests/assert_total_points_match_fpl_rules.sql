with matches as (

    select
        f.player_match_key,
        p.position_name,
        f.total_points,
        f.minutes,
        f.goals_scored,
        f.assists,
        f.clean_sheets,
        f.goals_conceded,
        f.saves,
        f.penalties_saved,
        f.penalties_missed,
        f.yellow_cards,
        f.red_cards,
        f.own_goals,
        f.bonus,
        f.defcon_points
    from {{ ref('fct_player_match') }} as f
    left join {{ ref('dim_position') }} as p
        on p.position_key = f.position_key

),

scored as (

    select
        player_match_key,
        total_points,
        case when minutes >= 60 then 2 when minutes > 0 then 1 else 0 end
        + goals_scored * case position_name when 'GKP' then 10 when 'DEF' then 6 when 'MID' then 5 else 4 end
        + assists * 3
        + clean_sheets * case when position_name in ('GKP', 'DEF') then 4 when position_name = 'MID' then 1 else 0 end
        - case when position_name in ('GKP', 'DEF') then goals_conceded / 2 else 0 end
        + case when position_name = 'GKP' then saves / 3 else 0 end
        + penalties_saved * 5
        - penalties_missed * 2
        - yellow_cards
        - red_cards * 3
        - own_goals * 2
        + bonus
        + defcon_points as rule_points
    from matches

)

select
    player_match_key,
    total_points,
    rule_points
from scored
where total_points <> rule_points
