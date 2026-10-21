# Security policy

## Supported version

Security fixes target the latest commit on `main`. Older snapshots are not maintained.

## Reporting a vulnerability

Please report suspected vulnerabilities privately through [GitHub's private vulnerability reporting form](https://github.com/panmichalakos-unity/issue-tracker-lakehouse/security/advisories/new).

Include the affected commit, a minimal reproduction, the potential impact and any suggested mitigation. Do not include credentials, personal information or employer-confidential data. Please avoid posting exploit details in a public issue while the report is being assessed.

This is a personal portfolio project using invented fixtures. No response or remediation time is guaranteed.

## Contributing safely

- Keep fixtures synthetic and credentials out of code, logs and commits.
- Use supported Python versions and install dependencies from `requirements.txt` with its accompanying constraints.
- Dependency updates and workflow changes must pass the repository's checks before merging. Updates are reviewed; they are not automatically merged.
