with

members as (

    select
        snapshot_date
        , group_name
        , account_id
        , display_name
    from {{ ref('stg_group_members') }}

)

, people as (

    select distinct
        group_name
        , account_id
        , display_name
    from members

)

, dates as (

    select distinct snapshot_date
    from members

)

, grid as (

    select
        people.account_id
        , people.display_name
        , people.group_name
        , dates.snapshot_date
        , case
            when members.account_id is not null then 1
            else 0
        end as is_member
    from people
    cross join dates
    left join members
        on members.account_id = people.account_id
        and members.group_name = people.group_name
        and members.snapshot_date = dates.snapshot_date

)

, marked as (

    select
        account_id
        , display_name
        , group_name
        , snapshot_date
        , is_member
        , lag(is_member) over (
            partition by account_id, group_name
            order by snapshot_date
        ) as prev_member
    from grid

)

, starts as (

    select *
    from marked
    where is_member = 1
        and (prev_member is null or prev_member = 0)

)

select
    starts.account_id
    , starts.display_name
    , starts.group_name
    , starts.snapshot_date as valid_from
    , (
        select min(grid.snapshot_date)
        from grid
        where grid.account_id = starts.account_id
            and grid.group_name = starts.group_name
            and grid.snapshot_date > starts.snapshot_date
            and grid.is_member = 0
    ) as valid_to
from starts
