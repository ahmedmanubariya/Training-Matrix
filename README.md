# Eaststone TrainingHub

TrainingHub is a full-stack controlled-document and staff-training portal.

## Architecture

```text
Vite + React frontend (port 5173)
        |
        | JSON / session API
        v
Python / Flask backend (port 5000)
        |
        +-- training database
        +-- approved SOP folder synchronisation
        +-- electronic Read & Understood evidence
        +-- audit trail
        +-- compliance calculations
        +-- automated email alerts
```

The React frontend is under `frontend/`. The Python backend remains under `traininghub/` and exposes JSON endpoints under `/api`.

## Current application functionality

- Vite + React eQMS-style portal interface
- responsive Eaststone green/gold/white design
- staff, department manager, QA and administrator permission model
- personal compliance dashboard and pie/donut chart
- searchable controlled-document library
- version-specific Read & Understood electronic acknowledgement
- signature evidence with revision and date/time
- department/team compliance metrics
- below-80% compliance warning and email-alert engine
- controlled SOP revision history
- safe SOP retirement rather than destructive deletion
- role-to-SOP requirements
- automatic training assignment from job role
- automatic reset to `OUTSTANDING` when a new approved revision appears
- approved-folder synchronisation with latest-revision selection
- audit trail

## GitHub Codespaces — easiest way to run the new UI

Rebuild the Codespace after pulling the latest repository changes because the devcontainer now installs Node.js for Vite.

When the Codespace starts it forwards:

- **5173 — TrainingHub React UI**
- **5000 — TrainingHub Python API**

The Codespace installs frontend packages and starts both services automatically. Open the forwarded **5173** port to see the React interface.

If you need to start them manually:

### Terminal 1 — Python backend

```bash
pip install -r requirements.txt
gunicorn --bind 0.0.0.0:5000 --workers 1 app:app
```

### Terminal 2 — React frontend

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0
```

Open `http://127.0.0.1:5173` locally or the Codespaces forwarded 5173 URL.

The Vite development server proxies `/api` and `/controlled-documents` requests to the Python backend on port 5000.

## Development login

On first run, if the database has no users, TrainingHub creates a bootstrap administrator:

```text
Username: admin
Temporary password: ChangeMeNow!2026
```

Change bootstrap credentials before any non-development deployment.

## Approved Eaststone folder synchronisation

The Python backend can monitor a server-accessible Approved SOPs folder using:

```text
APPROVED_DOCS_ROOT=\\eaststone-server\Approved SOPs
APPROVED_DOCS_SYNC_SECONDS=300
```

The deployed backend server must have operating-system/network permission to read that path. GitHub itself does not access the Eaststone drive.

The synchroniser:

1. scans supported approved files;
2. groups retained revisions by document reference;
3. selects the latest approved revision;
4. hashes content to identify actual changes;
5. stores the effective revision as immutable application evidence;
6. supersedes the previous application version;
7. resets current assignees to outstanding for retraining; and
8. records the change in the audit trail.

## Email alerts

Staff whose mandatory training compliance falls below the configured threshold (default **80%**) can receive an automated reminder showing their compliance percentage, outstanding count and overdue count.

Configure SMTP variables in `.env.example` or use your organisation's approved mail integration in production.

## Repository safety

Do **not** commit real employee records, controlled SOP files, passwords, production databases, mail credentials, network-drive credentials or backups to GitHub.

The repository should be made **private** before organisational information or production infrastructure details are introduced.

## Production direction

The intended production topology is:

```text
Users / browsers
      |
    HTTPS
      |
Reverse proxy / load balancer
      |----------------------|
      v                      v
React static frontend    Python API service
                             |
            |----------------|----------------|
            v                v                v
       SQL database     Approved SOPs     Email service
                        file source
```

For organisational deployment, use Microsoft Entra ID/SSO + MFA, PostgreSQL or SQL Server, HTTPS, controlled document storage, scheduled background workers, approved email delivery, central logging, backup/restore testing and the validation/change-control process required for the intended regulated use.
