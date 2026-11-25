with fpl_players as (

    select
        p.player_key,
        t.team_code,
        p.birth_date,
        p.current_selected_pct,
        lower(unaccent(p.full_name)) as full_name,
        lower(unaccent(p.first_name || ' ' || p.second_name)) as first_second_name,
        lower(unaccent(p.web_name)) as web_name
    from {{ ref('dim_player') }} as p
    inner join {{ ref('dim_team') }} as t
        on t.team_key = p.team_key
    where p.season = (select max(season) from {{ ref('dim_player') }})

),

squad as (

    select
        s.bzzoiro_player_id,
        m.team_code,
        s.birth_date,
        lower(unaccent(s.player_name)) as player_name
    from {{ ref('stg_bzzoiro_squad_players') }} as s
    inner join {{ ref('stg_bzzoiro_teams') }} as m
        on m.bzzoiro_team_id = s.bzzoiro_team_id

),

candidates as (

    select
        s.bzzoiro_player_id,
        f.player_key,
        f.current_selected_pct,
        (s.birth_date = f.birth_date)::int * 2
            + (s.player_name in (f.full_name, f.first_second_name, f.web_name))::int as score
    from squad as s
    inner join fpl_players as f
        on f.team_code = s.team_code
        and (
            s.birth_date = f.birth_date
            or s.player_name in (f.full_name, f.first_second_name, f.web_name)
        )

),

best_per_bzzoiro as (

    select distinct on (bzzoiro_player_id)
        bzzoiro_player_id,
        player_key,
        score
    from candidates
    order by bzzoiro_player_id, score desc, current_selected_pct desc, player_key

)

select distinct on (player_key)
    player_key,
    bzzoiro_player_id,
    score as match_score
from best_per_bzzoiro
order by player_key, score desc, bzzoiro_player_id
