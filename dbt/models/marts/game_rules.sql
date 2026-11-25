select
    b.season,
    b.run_date,
    b.payload -> 'game_config' -> 'scoring' as scoring,
    b.payload -> 'game_settings' as settings,
    b.payload -> 'chips' as chips,
    (
        select jsonb_agg(
            jsonb_build_object(
                'position', t ->> 'singular_name_short',
                'squad_select', (t ->> 'squad_select')::int,
                'squad_min_play', (t ->> 'squad_min_play')::int,
                'squad_max_play', (t ->> 'squad_max_play')::int
            )
            order by (t ->> 'id')::int
        )
        from jsonb_array_elements(b.payload -> 'element_types') as t
    ) as positions
from {{ ref('base_master_latest') }} as b
