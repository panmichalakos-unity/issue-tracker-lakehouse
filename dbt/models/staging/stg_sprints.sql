select
    id as sprint_id
    , name as sprint_name
    , state
    , project_id
    , try_cast(start_date as timestamp) as start_date
    , try_cast(end_date as timestamp) as end_date
from {{ source('bronze', 'sprints') }}
