with

status_changes as (

    select
        issue_id
        , changed_at
        , to_value as status
    from {{ ref('stg_changelog') }}
    where field = 'status'

)

, first_change as (

    select
        c.issue_id
        , i.created as changed_at
        , c.from_value as status
    from {{ ref('stg_changelog') }} as c
    inner join {{ ref('stg_issues') }} as i
        on c.issue_id = i.id
    where c.field = 'status'
    qualify row_number() over (
        partition by c.issue_id
        order by c.changed_at
    ) = 1

)

, events as (

    select * from status_changes
    union all
    select * from first_change

)

, ordered as (

    select
        issue_id
        , status
        , changed_at as valid_from
        , lead(changed_at) over (
            partition by issue_id
            order by changed_at
        ) as valid_to
    from events

)

select * from ordered
