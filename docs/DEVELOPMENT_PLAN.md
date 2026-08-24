# TrainingHub development plan

This branch develops the TrainingHub application from the initial foundation into a usable staff-training system.

## Scope

- staff, manager and administrator authentication
- employee and department management
- SOP catalogue with controlled revisions
- role-based training assignment
- staff self-service training
- electronic acknowledgement with password re-authentication
- personal compliance dashboard
- manager team dashboard
- below-80% compliance alerts
- audit trail
- safe SOP retirement rather than destructive deletion

## Production hardening still required

- Microsoft Entra ID / SSO + MFA
- SQL Server/PostgreSQL
- protected document storage
- Microsoft Graph / approved mail relay
- background scheduler
- automated backups and restore testing
- HTTPS and deployment secrets
- formal regulated-system validation where required
