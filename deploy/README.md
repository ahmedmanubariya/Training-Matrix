# Production deployment

TrainingHub should run on a managed/premium server, not on GitHub Codespaces. GitHub remains the source-code repository.

## Recommended service layout

1. HTTPS reverse proxy / platform ingress
2. Gunicorn web service running `app:app`
3. production SQL database (PostgreSQL or Microsoft SQL Server target)
4. protected application document store
5. scheduled maintenance job running `python jobs/run_maintenance.py`
6. approved Eaststone source folder mounted read-only at the path configured by `APPROVED_DOCS_ROOT`
7. approved email service / Microsoft 365 relay
8. central logs, backups and monitoring

## Web process

```bash
gunicorn -c deploy/gunicorn.conf.py app:app
```

## Maintenance process

Run from the server scheduler at an agreed cadence, for example every 15 minutes:

```bash
python jobs/run_maintenance.py
```

This job checks the Approved SOPs folder, refreshes training statuses and generates/sends below-80% alerts.

## Approved network drive

If the Eaststone Approved SOPs location is a Windows UNC share, the production server must be joined/connected to the appropriate network and the service identity must have read permission. On Linux this normally means mounting the SMB/CIFS share to a protected local mount point and configuring `APPROVED_DOCS_ROOT` to that mounted path. On Windows Server the UNC path can be used directly if the service account has access.

TrainingHub treats the approved source as read-only. It copies effective revisions into its own protected version store and never edits the quality-drive source file.

## Important

The current repository still uses SQLite for development. Before a multi-user live deployment, the data layer should be migrated to PostgreSQL or SQL Server and validated backups/restores should be established. Microsoft Entra ID/SSO + MFA is also recommended before production release.
