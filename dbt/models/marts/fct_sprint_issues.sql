select
    issues.issue_id
    , issues.issue_key
    , issues.status
    , sprints.sprint_id
    , sprints.sprint_name
    , sprints.state as sprint_state
    , sprints.start_date
    , sprints.end_date
from {{ ref('int_issues_current') }} as issues
inner join {{ ref('stg_sprints') }} as sprints
    on issues.sprint_id = sprints.sprint_id
