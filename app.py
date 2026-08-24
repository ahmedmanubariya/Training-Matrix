import os
from flask import Flask, jsonify, render_template_string

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "development-only-change-me")

HOME = """
<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>TrainingHub</title>
<style>
body{font-family:system-ui;margin:0;background:#f4f6f8;color:#17202a}
header{background:#17202a;color:#fff;padding:18px 28px;font-weight:800}
main{max-width:1100px;margin:40px auto;padding:0 20px}.card{background:#fff;border:1px solid #dde4eb;border-radius:12px;padding:24px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;margin-top:20px}.tile{border:1px solid #dde4eb;border-radius:10px;padding:18px}
</style></head><body><header>TrainingHub</header><main><div class="card">
<h1>Training Matrix Software</h1><p>The GitHub-hosted application foundation is running.</p>
<div class="grid"><div class="tile"><strong>SOP Management</strong><p>Create, revise and retire training documents.</p></div>
<div class="tile"><strong>Staff Training</strong><p>Assignments, reading and electronic acknowledgements.</p></div>
<div class="tile"><strong>Compliance</strong><p>Personal and department progress with an 80% alert threshold.</p></div>
<div class="tile"><strong>Audit Trail</strong><p>Preserve historical training and document revisions.</p></div></div>
</div></main></body></html>
"""

@app.get("/")
def home():
    return render_template_string(HOME)

@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "application": "TrainingHub"})

if __name__ == "__main__":
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "5000")), debug=os.environ.get("FLASK_DEBUG", "0") == "1")
