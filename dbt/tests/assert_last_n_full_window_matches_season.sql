select
    l.player_key
from {{ ref('player_scouting_last_n') }} as l
join {{ ref('player_scouting') }} as s
    on s.player_key = l.player_key
where l.last_n = l.games_played
    and (l.minutes, l.total_points, l.points_per_million, l.xgi, l.gi, l.xgc, l.goals_conceded, l.defcon, l.defcon_hits, l.defcon_hit_rate, l.clean_sheets, l.saves)
        is distinct from
        (s.minutes, s.total_points, s.points_per_million, s.xgi, s.gi, s.xgc, s.goals_conceded, s.defcon, s.defcon_hits, s.defcon_hit_rate, s.clean_sheets, s.saves)
