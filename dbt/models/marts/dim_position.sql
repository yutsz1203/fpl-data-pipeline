select
    {{ dbt_utils.generate_surrogate_key(['season', 'position_id']) }} as position_key,
    season, 
    position_id, 
    position_name
from {{ ref('stg_positions') }}