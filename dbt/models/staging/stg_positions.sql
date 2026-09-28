select
    b.season,
    (et ->> 'id')::int as position_id,
    et ->> 'singular_name_short' as position_name
from {{ ref('base_master_latest') }} as b
cross join lateral jsonb_array_elements(b.payload -> 'element_types') as et