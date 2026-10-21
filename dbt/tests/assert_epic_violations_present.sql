-- ALP-4 fires unassigned + no due date. ALP-5 fires stale in-progress.
select 1 as missing
where (
    select count(*)
    from {{ ref('fct_epic_health_violations') }}
    where epic_key = 'ALP-4'
) < 2

union all

select 1 as missing
where not exists (
    select 1
    from {{ ref('fct_epic_health_violations') }}
    where epic_key = 'ALP-5'
        and rule_code = 'EPIC_STALE_IN_PROGRESS'
)
