select
    {{ dbt_utils.generate_surrogate_key(['season', 'player_id']) }} as player_key,
    season,
    player_id,
    player_code,
    web_name,
    first_name || ' ' || second_name as full_name,
    first_name,
    second_name,
    status, 
    current_price, 
    current_selected_pct, 
    penalties_order, 
    direct_freekicks_order,
    corners_and_indirect_freekicks_order
from {{ ref('stg_players') }}