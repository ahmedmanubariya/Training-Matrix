# Eaststone Approved Documents Integration

TrainingHub is designed so the React frontend never reads the company drive directly. The Python backend/server is given **read-only** access to the approved Eaststone document location and publishes the current approved records through the API.

## Eaststone source of truth

The approved document share remains the master source. TrainingHub must not rename, edit or delete files in that location.

Recommended production source configuration:

```text
APPROVED_DOCS_ROOT=\\eaststone-file-server\Approved SOPs
APPROVED_DOCS_SYNC_SECONDS=300
```

Use the actual UNC/network path in production. Avoid relying on a mapped drive letter such as `N:` for a Windows service because mapped drive letters are normally user-session specific.

The configured root is scanned recursively, so subfolders containing SOPs, forms and other supported controlled documents can all be discovered from one approved root.

## Eaststone filename convention

TrainingHub understands the supplied convention:

```text
ES.SOP.001.V10 - Writing of Standard Operating Procedures & Forms.pdf
ES.SOP.003.V07 - Eaststone Site Induction.pdf
```

These become:

```text
Reference: ES.SOP.001
Revision: V10
Title: Writing of Standard Operating Procedures & Forms

Reference: ES.SOP.003
Revision: V07
Title: Eaststone Site Induction
```

The parser also accepts a form segment such as:

```text
ES.SOP.001.F01.V03 - SOP Template.pdf
```

which is stored with the stable reference `ES.SOP.001.F01` and revision `V03`.

## Revision behaviour

If both of these exist in the approved folder:

```text
ES.SOP.001.V10 - Writing of Standard Operating Procedures & Forms.pdf
ES.SOP.001.V11 - Writing of Standard Operating Procedures & Forms.pdf
```

TrainingHub selects `V11` as current, keeps the previously imported revision as superseded history, records the source file/hash, and resets current assignees for that document to `OUTSTANDING` retraining.

## Production server permissions

The service account running the Python backend should have:

```text
Read folder/list contents    YES
Read approved PDFs/files     YES
Write to Approved SOPs       NO
Delete from Approved SOPs    NO
Rename Approved SOP files    NO
```

TrainingHub keeps its own application copy/version evidence in protected application storage while the approved share remains the source of truth.

## Codespaces limitation

GitHub Codespaces runs in GitHub's cloud and cannot see a local Eaststone `N:` drive. Codespaces is therefore for application development/testing only.

For live synchronisation, run the Python backend on an Eaststone-accessible server or managed host with secure network connectivity to the approved file share. The React frontend can then be hosted separately or behind the same HTTPS portal.
