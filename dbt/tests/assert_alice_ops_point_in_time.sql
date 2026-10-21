-- February comment is in ops; April comment is after Alice left.
select comment_id
from {{ ref('fct_comment_with_group_at_time') }}
where comment_id = 1
    and in_ops_at_comment = false

union all

select comment_id
from {{ ref('fct_comment_with_group_at_time') }}
where comment_id = 2
    and in_ops_at_comment = true
