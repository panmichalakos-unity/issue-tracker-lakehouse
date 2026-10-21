select
    issue_id
    , changed_at
    , field
    , from_value
    , to_value
from {{ source('bronze', 'changelog') }}
