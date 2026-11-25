with next_fixture as (

    select
        team,
        min(kickoff_time) as kickoff_time
    from {{ ref('fct_lineup') }}
    where lineup_status = 'predicted'
        and season = (select max(season) from {{ ref('fct_lineup') }})
    group by team

)

select
    l.player_key,
    l.fixture_key,
    l.gameweek,
    l.kickoff_time,
    l.is_starter,
    l.confidence,
    l.start_score
from {{ ref('fct_lineup') }} as l
inner join next_fixture as n
    on n.team = l.team and n.kickoff_time = l.kickoff_time
where l.lineup_status = 'predicted'
    and l.player_key is not null
