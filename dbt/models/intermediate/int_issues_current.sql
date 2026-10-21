select
    id as issue_id
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
    , due_date
    , custom_fields
from {{ ref('stg_issues') }}
