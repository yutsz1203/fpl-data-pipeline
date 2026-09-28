select
    b.season,
    (e ->> 'id')::int as player_id,
    (e ->> 'code')::int as player_code,
    e ->> 'web_name' as web_name,
    e ->> 'first_name' as first_name,
    e ->> 'second_name' as second_name,
    (e ->> 'element_type')::int as position_id,
    (e ->> 'team')::int as team_id,
    e ->> 'status' as status,
    ((e ->> 'now_cost')::numeric/10)::numeric(4,1) as current_price,
    (e ->> 'selected_by_percent')::numeric(4,1) as current_selected_pct,
    (e ->> 'penalties_order')::int as penalties_order,
    (e ->> 'direct_freekicks_order')::int as direct_freekicks_order,
    (e ->> 'corners_and_indirect_freekicks_order')::int as corners_and_indirect_freekicks_order
from {{ ref('base_master_latest') }} as b
cross join lateral jsonb_array_elements(b.payload -> 'elements') as e
