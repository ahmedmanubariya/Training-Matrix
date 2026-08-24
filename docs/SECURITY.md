# Security notes

TrainingHub currently uses local application accounts for development and demonstration.

## Do not commit

- real staff records or training exports
- controlled SOP files
- database files
- passwords, SMTP credentials, tokens or client secrets
- production backups

## Production controls to implement

- Microsoft Entra ID / SSO with MFA
- least-privilege role mapping for staff, manager and administrator
- HTTPS only
- server-side session protection
- protected object/document storage
- SQL Server or PostgreSQL
- scheduled access reviews
- backup and restore testing
- central logging and alerting
- append-only or otherwise protected audit records
- formal validation/change control where required by the organisation

Electronic acknowledgement functionality in the development application must not be treated as a validated regulated electronic-signature system until organisational requirements have been defined, tested and approved.
