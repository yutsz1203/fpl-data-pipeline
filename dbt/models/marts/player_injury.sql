select
    m.player_key,
    s.run_date,
    s.availability,
    s.injury_type,
    s.expected_return
from {{ ref('stg_bzzoiro_squad_players') }} as s
inner join {{ ref('bzzoiro_player_map') }} as m
    on m.bzzoiro_player_id = s.bzzoiro_player_id
where s.availability <> 'available'
