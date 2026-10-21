with

epics as (

    select *
    from {{ ref('int_issues_current') }}
    where issue_type = 'Epic'

)

, as_of as (

    select try_cast('{{ var("as_of_date") }}' as date) as as_of_date

)

, no_due_date as (

    select
        issue_key || '|EPIC_NO_DUE_DATE' as violation_key
        , issue_key as epic_key
        , 'EPIC_NO_DUE_DATE' as rule_code
        , 'HIGH' as severity
        , 'missing due date' as message
        , as_of.as_of_date as detected_on
    from epics
    cross join as_of
    where due_date is null

)

, unassigned as (

    select
        issue_key || '|EPIC_UNASSIGNED' as violation_key
        , issue_key as epic_key
        , 'EPIC_UNASSIGNED' as rule_code
        , 'HIGH' as severity
        , 'epic has no assignee' as message
        , as_of.as_of_date as detected_on
    from epics
    cross join as_of
    where assignee_id is null

)

, stale as (

    select
        epics.issue_key || '|EPIC_STALE_IN_PROGRESS' as violation_key
        , epics.issue_key as epic_key
        , 'EPIC_STALE_IN_PROGRESS' as rule_code
        , 'CRITICAL' as severity
        , 'in progress longer than '
        || '{{ var("stale_after_days") }}'
        || ' days' as message
        , as_of.as_of_date as detected_on
    from epics
    cross join as_of
    where epics.status = 'In Progress'
        and epics.updated::date
        < as_of.as_of_date - {{ var("stale_after_days") }}

)

select * from no_due_date
union all
select * from unassigned
union all
select * from stale
