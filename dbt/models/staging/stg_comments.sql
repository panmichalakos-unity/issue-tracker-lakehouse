select
    comment_id
    , issue_id
    , author_id
    , author_name
    , try_cast(created as timestamp) as created
    , body
from {{ source('bronze', 'comments') }}
