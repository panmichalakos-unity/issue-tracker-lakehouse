select
    left_row.account_id
    , left_row.group_name
from {{ ref('int_group_membership_scd2') }} as left_row
inner join {{ ref('int_group_membership_scd2') }} as right_row
    on left_row.account_id = right_row.account_id
    and left_row.group_name = right_row.group_name
    and left_row.valid_from < right_row.valid_from
    and (
        left_row.valid_to is null
        or left_row.valid_to > right_row.valid_from
    )
