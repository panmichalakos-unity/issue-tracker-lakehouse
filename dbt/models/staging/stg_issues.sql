select
    id
    , project_id
    , issue_key
    , issue_type
    , status
    , summary
    , assignee_id
    , assignee_name
    , sprint_id
    , created
    , updated
    , try_cast(due_date as date) as due_date
    , custom_fields
from {{ source('bronze', 'issues') }}
