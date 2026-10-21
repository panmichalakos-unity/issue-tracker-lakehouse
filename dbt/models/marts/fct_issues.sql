select
    issue_id
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
from {{ ref('int_issues_current') }}
