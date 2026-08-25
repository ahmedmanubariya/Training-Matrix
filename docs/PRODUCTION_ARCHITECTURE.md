# TrainingHub production architecture

TrainingHub is being developed as an eQMS-style controlled-document and training portal. The GitHub repository contains source code only; employee records, controlled SOP files, credentials and production databases must remain outside GitHub.

## User permission model

| Permission level | Controlled documents | Own Read & Understood | Department progress | Document control | All staff | Permissions | Audit trail | System configuration |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| User | Yes | Yes | No | No | No | No | No | No |
| Department manager | Yes | Yes | Own department | No | Own department | Limited staff account management | No | No |
| QA | Yes | Yes | All | Yes | Yes | Yes | Yes | Approved-folder sync / quality configuration |
| Admin | Yes | Yes | All | Yes | Yes | Yes | Yes | Full |

QA accounts are represented internally using the compatibility access level `admin` plus the effective `permission_role=qa`. This keeps older route protections working while allowing the UI to distinguish QA from full system administrators.

## Training evidence model

A valid Read & Understood completion contains:

- authenticated user ID
- linked employee ID
- SOP / controlled-document ID
- exact document-version ID and revision
- electronic signature name
- acknowledgement statement
- date and timestamp
- request IP address
- audit-trail event

A new effective document revision never overwrites the old signature. Existing evidence remains historical and the new revision resets active assignees to `OUTSTANDING` until they read and acknowledge the new version.

## Approved Eaststone folder synchronisation

The application server reads the folder configured in `APPROVED_DOCS_ROOT`, for example a Windows UNC share such as:

```text
\\eaststone-server\Approved SOPs
```

The server account running TrainingHub must have read-only access to that approved source folder.

The sync service:

1. recursively scans supported controlled files;
2. groups retained revisions by parsed document reference;
3. selects the latest revision deterministically;
4. hashes the current file so unchanged documents are not duplicated;
5. copies new effective versions into protected application storage;
6. supersedes the previous effective version without deleting it;
7. updates the SOP current revision;
8. resets current assignees to `OUTSTANDING` for retraining;
9. creates an audit-trail entry.

The approved source should be treated as read-only by TrainingHub. TrainingHub does not modify or delete files on the quality drive.

## Recommended premium production stack

### Front end

Responsive HTML/CSS/JavaScript portal served over HTTPS. The current UI is server-rendered by Flask; it can later be split into a React/Next.js front end if required without changing the training evidence model.

### Back end

- Python web application behind Gunicorn / production WSGI hosting
- PostgreSQL or Microsoft SQL Server production database
- protected controlled-document object/file storage
- scheduled maintenance worker for document sync, status refresh and email alerts
- Microsoft Entra ID / SSO + MFA for production identity
- Microsoft Graph or approved organisational SMTP relay for notification delivery

### Hosting

Preferred options depend on Eaststone network connectivity:

- **Azure App Service Premium + Azure SQL/PostgreSQL** when the approved document source is reachable through SharePoint/Graph or a secured network integration;
- **Azure VM / Windows Server** connected to the Eaststone network when direct access to an on-premises mapped/UNC Approved SOPs folder is required;
- equivalent premium private-cloud/on-prem server where HTTPS, backups, monitoring and network access are centrally managed.

If the Approved SOPs folder is an on-premises Windows network share, the hosting environment must have a secure route to that network share (for example private network/VPN/ExpressRoute or an on-prem application server). A public GitHub Codespace cannot be used as the production server for this purpose.

## Scheduled maintenance

Run:

```bash
python jobs/run_maintenance.py
```

from the production scheduler. A typical cadence is every 15 minutes for approved-document detection and at least daily for training compliance alerts. The alert log de-duplicates user reminders for 24 hours.

## 80% compliance rule

TrainingHub calculates each employee's mandatory compliance percentage from active assigned training. When a staff member falls below the configured threshold (default `80`), the notification service generates an alert and, when mail credentials are configured, sends an automated email showing their compliance percentage plus outstanding and overdue counts.

## Regulated-system controls still required before authoritative use

Before TrainingHub becomes the official GxP/eQMS training record, Eaststone should formally approve and validate at minimum:

- user identity, SSO/MFA and account lifecycle;
- electronic-signature meaning and re-authentication requirements;
- role/permission matrix and periodic access review;
- controlled-document approval/release source and naming convention;
- audit-trail protection and review;
- database backup, restore and retention;
- document retention and immutable historical versions;
- business continuity / disaster recovery;
- software change control and release approval;
- validation test scripts and traceability to user requirements;
- data-integrity controls appropriate to the regulated process.
