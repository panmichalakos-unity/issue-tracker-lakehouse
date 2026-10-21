select
    comments.comment_id
    , comments.issue_id
    , comments.author_id
    , comments.author_name
    , comments.created
    , comments.body
    , membership.valid_from as ops_valid_from
    , membership.valid_to as ops_valid_to
    , coalesce(membership.account_id is not null, false) as in_ops_at_comment
from {{ ref('stg_comments') }} as comments
left join {{ ref('int_group_membership_scd2') }} as membership
    on comments.author_id = membership.account_id
    and membership.group_name = '{{ var("ops_group") }}'
    and comments.created >= membership.valid_from
    and (
        membership.valid_to is null
        or comments.created < membership.valid_to
    )
