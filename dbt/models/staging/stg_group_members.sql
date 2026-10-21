select
    try_cast(snapshot_date as date) as snapshot_date
    , group_name
    , account_id
    , display_name
from {{ source('bronze', 'group_members') }}
