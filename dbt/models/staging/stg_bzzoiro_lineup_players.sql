with sides as (

    select
        l.event_id,
        l.payload ->> 'lineup_status' as lineup_status,
        (l.payload ->> 'updated_at')::timestamptz as lineup_updated_at,
        s.side,
        s.lineup
    from {{ source('raw', 'bzzoiro_lineups') }} as l
    cross join lateral (
        values
            ('home', l.payload -> 'lineups' -> 'home'),
            ('away', l.payload -> 'lineups' -> 'away')
    ) as s (side, lineup)
    where jsonb_typeof(s.lineup) = 'object'

),

players as (

    select
        s.*,
        true as is_starter,
        p.player,
        p.list_order
    from sides as s
    cross join lateral jsonb_array_elements(s.lineup -> 'players') with ordinality as p (player, list_order)

    union all

    select
        s.*,
        false as is_starter,
        p.player,
        p.list_order
    from sides as s
    cross join lateral jsonb_array_elements(s.lineup -> 'substitutes') with ordinality as p (player, list_order)

)

select
    event_id,
    lineup_status,
    lineup_updated_at,
    side,
    (lineup ->> 'team_id')::int as bzzoiro_team_id,
    lineup ->> 'formation' as formation,
    (lineup ->> 'confidence')::numeric as confidence,
    (player ->> 'id')::int as bzzoiro_player_id,
    player ->> 'name' as player_name,
    player ->> 'position' as position_code,
    is_starter,
    list_order::int as list_order,
    coalesce((player ->> 'captain')::boolean, false) as is_captain,
    (player ->> 'ai_score')::numeric as start_score
from players
