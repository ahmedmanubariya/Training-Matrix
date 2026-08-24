# Training Matrix / TrainingHub

A staff training and SOP compliance application.

## Planned and implemented capabilities

- Staff, department manager and administrator access
- SOP/training document catalogue and revision history
- job-role training requirements and assignments
- electronic training acknowledgements
- personal and department compliance dashboards
- alerts when compliance is below 80%
- audit trail and safe SOP retirement

## Security

Do **not** commit real employee records, controlled SOP documents, passwords, database files, or production exports to this repository.

## Local development

Python 3.10+:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`.

## Production direction

Use SSO/MFA, PostgreSQL or SQL Server, protected document storage, HTTPS, scheduled jobs, backups, central logging, and formal validation/change control where required.
