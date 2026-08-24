# Training Matrix / TrainingHub

TrainingHub is a browser-based staff training and SOP compliance application.

## Current application functionality

- staff, department manager and administrator accounts
- forced password change for temporary passwords
- staff records with site, department and job role
- SOP/training catalogue
- controlled SOP revision uploads
- previous revisions retained as superseded history
- safe SOP retirement rather than destructive deletion
- role-to-SOP requirements
- automatic staff training assignment from job role
- automatic reset to `OUTSTANDING` when a new SOP revision is uploaded
- staff self-service training dashboard
- training material read tracking
- electronic acknowledgement requiring typed name and password re-entry
- signature history with revision, date/time and IP address
- personal compliance pie chart
- department manager compliance dashboard
- below-80% alert engine with SMTP support or queued alerts
- administrator audit trail

## Repository safety

Do **not** commit real employee records, controlled SOP documents, database files, passwords, credentials, production exports or backups to this repository. The `.gitignore` is configured to block common local data files and upload folders.

If this repository is going to be used for organisational development, make it **private** before adding any non-public information.

## Local development

Python 3.10+ is required.

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`.

On the first run, if there are no users, TrainingHub creates a bootstrap administrator account. The development defaults are:

```text
Username: admin
Temporary password: ChangeMeNow!2026
```

Change the bootstrap credentials using environment variables before a real deployment. See `.env.example`.

## Docker

```bash
docker build -t traininghub .
docker run --rm -p 5000:5000 -e SECRET_KEY="replace-me" traininghub
```

Then open `http://127.0.0.1:5000`.

## Email alerts

When a compliance check is run, staff below the 80% threshold are added to the alert log. If SMTP variables are configured, TrainingHub attempts to email the employee; otherwise the alert remains queued for testing.

Configure the variables shown in `.env.example`.

## Production direction

The current repository is a working development application. A production organisational deployment should replace development components with Microsoft Entra ID/SSO and MFA, PostgreSQL or SQL Server, protected document storage, HTTPS, scheduled background jobs, approved mail delivery, central logging, automated backups and restore testing.

Where the system will be the authoritative regulated training record, electronic signatures, audit trails, record retention, access control and change control must be validated against your organisation's requirements before release.
