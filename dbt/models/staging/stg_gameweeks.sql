select
    b.season,
    (e ->> 'id')::int as gameweek_id,
    e ->> 'name' as gameweek_name,
    (e ->> 'deadline_time')::timestamptz as deadline_time,
    (e ->> 'finished')::boolean as is_finished,
    (e ->> 'data_checked')::boolean as is_data_checked,
    (e ->> 'is_previous')::boolean as is_previous,
    (e ->> 'is_current')::boolean as is_current,
    (e ->> 'is_next')::boolean as is_next,
    (e ->> 'ranked_count')::int as ranked_count
from {{ ref('base_master_latest') }} as b
cross join lateral jsonb_array_elements(b.payload -> 'events') as e