import os
import sys
import shutil
import zipfile
import requests
import importlib.util
from flask import Flask, request, render_template_string, jsonify, redirect
from packaging import version

PACKAGE = "math_module"
LOCAL_STORE = "packages"
BUCKET = "kraft-packages"

app = Flask(__name__)


# -----------------------------------------------------
# FORCE RELOAD
# -----------------------------------------------------
def force_reload():
    for m in list(sys.modules.keys()):
        if m == PACKAGE or m.startswith(PACKAGE + "."):
            del sys.modules[m]

    base = f"{LOCAL_STORE}/{PACKAGE}"
    sys.path = [p for p in sys.path if base not in p]


# -----------------------------------------------------
# LOAD MODULE
# -----------------------------------------------------
def load_module(ver):
    force_reload()

    pkg_root = f"{LOCAL_STORE}/{PACKAGE}/{ver}/{PACKAGE}"
    module_path = os.path.join(pkg_root, "__init__.py")

    sys.path.insert(0, f"{LOCAL_STORE}/{PACKAGE}/{ver}")

    spec = importlib.util.spec_from_file_location(PACKAGE, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# -----------------------------------------------------
# LIST ONLINE VERSIONS
# -----------------------------------------------------
def list_versions_online():
    try:
        url = f"https://storage.googleapis.com/storage/v1/b/{BUCKET}/o?prefix={PACKAGE}/&delimiter=/"
        r = requests.get(url).json()

        versions = []
        for prefix in r.get("prefixes", []):
            versions.append(prefix.split("/")[1])

        return sorted(versions, key=version.parse)

    except:
        return []


# -----------------------------------------------------
# INSTALLED VERSION
# -----------------------------------------------------
def get_installed_version():
    base = f"{LOCAL_STORE}/{PACKAGE}"
    if not os.path.exists(base): return None

    versions = []
    for d in os.listdir(base):
        if os.path.isdir(os.path.join(base, d)):
            try:
                version.parse(d)
                versions.append(d)
            except:
                pass

    return sorted(versions, key=version.parse)[-1] if versions else None


# -----------------------------------------------------
# PREVIOUS VERSION
# -----------------------------------------------------
def get_previous_version():
    base = f"{LOCAL_STORE}/{PACKAGE}"
    if not os.path.exists(base): return None

    versions = []
    for d in os.listdir(base):
        if os.path.isdir(os.path.join(base, d)):
            try:
                version.parse(d)
                versions.append(d)
            except:
                pass

    versions = sorted(versions, key=version.parse)
    return versions[-2] if len(versions) >= 2 else None


# -----------------------------------------------------
# DOWNLOAD ZIP
# -----------------------------------------------------
def download_zip(ver):
    url = f"https://storage.googleapis.com/{BUCKET}/{PACKAGE}/{ver}/{PACKAGE}-{ver}.zip"

    local_zip = f"{LOCAL_STORE}/{PACKAGE}/{ver}.zip"
    os.makedirs(os.path.dirname(local_zip), exist_ok=True)

    data = requests.get(url).content

    with open(local_zip, "wb") as f:
        f.write(data)

    return local_zip


# -----------------------------------------------------
# EXTRACT ZIP
# -----------------------------------------------------
def extract_zip(zip_path, ver):
    extract_dir = f"{LOCAL_STORE}/{PACKAGE}/{ver}"

    if os.path.exists(extract_dir):
        shutil.rmtree(extract_dir)

    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(extract_dir)

    return extract_dir


# -----------------------------------------------------
# SERVE README
# -----------------------------------------------------
@app.route("/readme/<ver>")
def readme(ver):
    # Correct GCS path for separate README upload
    url = f"https://storage.googleapis.com/{BUCKET}/{PACKAGE}/{ver}/README.md"

    r = requests.get(url)

    if r.status_code != 200:
        return "README not found.", 404

    text = (
        r.text.replace("\\u2714", "✔")
              .replace("\\r\\n", "\n")
              .replace("\\n", "\n")
    )

    return text



# -----------------------------------------------------
# UPDATE CHECK (CRITICAL FIXED VERSION)
# -----------------------------------------------------
@app.route("/check_update")
def check_update():
    try:
        installed = get_installed_version()
        online = list_versions_online()

        if not online:
            return jsonify({
                "installed": installed,
                "latest": None,
                "previous": None,
                "update_available": False,
                "rollback_available": False
            })

        latest = online[-1]
        previous = get_previous_version()

        return jsonify({
            "installed": installed,
            "latest": latest,
            "previous": previous,
            "update_available": (
                installed is None or version.parse(latest) > version.parse(installed)
            ),
            "rollback_available": previous is not None
        })

    except Exception as e:
        print("ERROR:", e)
        return jsonify({
            "installed": None,
            "latest": None,
            "previous": None,
            "update_available": False,
            "rollback_available": False
        })


# -----------------------------------------------------
# MAIN PAGE
# -----------------------------------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    result = sub_result = mul_result = None
    a_val = b_val = ""  # store input values

    if request.method == "POST":
        a_val = request.form.get("a", "")
        b_val = request.form.get("b", "")

        installed = get_installed_version()
        mod = load_module(installed)

        if "add" in request.form:
            result = mod.add(float(a_val), float(b_val))

        if "subtract" in request.form:
            sub_result = mod.subtract(float(a_val), float(b_val))

        if "multiply" in request.form:
            mul_result = mod.multiply(float(a_val), float(b_val))

        if "update" in request.form:
            latest = list_versions_online()[-1]
            zip_path = download_zip(latest)
            extract_zip(zip_path, latest)
            load_module(latest)
            return redirect("/")

        if "rollback" in request.form:
            installed = get_installed_version()
            previous = get_previous_version()

            if previous:
                shutil.rmtree(f"{LOCAL_STORE}/{PACKAGE}/{installed}")
                load_module(previous)

            return redirect("/")

    # -----------------------------------------------------
    # HTML TEMPLATE (SAFE & TESTED)
    # -----------------------------------------------------
    html = """
    <h1>Math Module</h1>

    <div id="update-box" style="padding:15px;background:#eef;border-radius:8px;">
        Checking...
    </div>

    <hr>

    <h2>Add / Subtract / Multiply</h2>

    <form method="POST">
        <input name="a" value="{{a_val}}" placeholder="A" required>
        <input name="b" value="{{b_val}}" placeholder="B" required>

        <button name="add">Add</button>
        <button name="subtract">Subtract</button>
        <button name="multiply">Multiply</button>
    </form>

    {% if result is not none %}
        <h3>Add Result: {{ result }}</h3>
    {% endif %}

    {% if sub_result is not none %}
        <h3>Subtract Result: {{ sub_result }}</h3>
    {% endif %}

    {% if mul_result is not none %}
        <h3>Multiply Result: {{ mul_result }}</h3>
    {% endif %}


    <!-- README MODAL -->
    <div id="readmeModal" style="
        display:none; position:fixed; top:0; left:0;
        width:100%; height:100%; background:rgba(0,0,0,0.7); padding-top:50px;
    ">
        <div style="
            background:white; max-width:60%; margin:auto; padding:20px;
            border-radius:10px;
        ">
            <h2>README / CHANGELOG</h2>
            <pre id="readmeContent" style="white-space: pre-wrap;"></pre>
            <button onclick="closeReadme()">Close</button>
        </div>
    </div>

    <script>
    async function poll() {
        try {
            const r = await fetch("/check_update");
            const d = await r.json();

            const box = document.getElementById("update-box");

            if (d.update_available) {
                box.innerHTML = `
                    Installed: ${d.installed}<br>
                    Latest: ${d.latest}<br><br>

                    <form method="POST">
                        <button name="update">Update to ${d.latest}</button>
                    </form>

                    <button onclick="openReadme('${d.latest}')">View README</button>
                `;
            }
            else {
                box.innerHTML = `
                    Installed: ${d.installed}<br>
                    Latest: ${d.latest}<br>
                `;

                if (d.rollback_available) {
                    box.innerHTML += `
                        <br><form method="POST"><button name="rollback">Rollback to ${d.previous}</button></form>
                    `;
                }
            }

        } catch (e) {
            console.log("Poll error:", e);
        }
    }

    poll();
    setInterval(poll, 3000);

    async function openReadme(ver) {
        const r = await fetch("/readme/" + ver);
        const t = await r.text();
        document.getElementById("readmeContent").textContent = t;
        document.getElementById("readmeModal").style.display = "block";
    }

    function closeReadme() {
        document.getElementById("readmeModal").style.display = "none";
    }
    </script>
    """

    return render_template_string(
        html,
        result=result,
        sub_result=sub_result,
        mul_result=mul_result,
        a_val=a_val,
        b_val=b_val
    )


if __name__ == "__main__":
    app.run(debug=True)
