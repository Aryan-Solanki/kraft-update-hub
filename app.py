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
    <style>
    /* Mobile layout up to 600px */
    @media (max-width: 600px) {

        /* Header resizing */
        h1 {
            font-size: 28px !important;
        }

        /* Update box full width */
        #update-box {
            width: 100% !important;
        }

        /* Stack form inputs vertically */
        form {
            flex-direction: column !important;
            align-items: stretch !important;
        }

        form input {
            width: 100% !important;
        }

        form button {
            width: 100% !important;
            margin-top: 8px !important;
        }

        /* Modal width on mobile */
        #readmeModal > div {
            max-width: 90% !important;
        }
    }

    /* Tablet responsiveness */
    @media (min-width: 601px) and (max-width: 900px) {
        #update-box {
            width: 70% !important;
        }

        form input {
            width: 45% !important;
        }

        #readmeModal > div {
            max-width: 75% !important;
        }
    }
</style>
<body style="background:#f4f6fc; margin:0; padding:0;">
<div style="padding-left:30px; padding-right:30px;">

    <div style="
    background: #e9edff;
    padding:30px;
    padding-left:20px;
    border-radius:10px;
    box-shadow:0 2px 6px rgba(0,0,0,0.1);
    margin-bottom:25px;
    ">
    
    <h1 style="
        margin: 0;
        font-size: 40px;
        color: #22225c;
        letter-spacing: 2px;
        font-family: Arial, sans-serif;
    ">
  Math Module
  </h1>
</div>
    <div id="update-box" style="
    background:#ffffff;
    padding:20px;
    border-radius:10px;
    box-shadow:0 1px 4px rgba(0,0,0,0.1);
    width:350px;
    margin-bottom:25px;
    font-family:Arial, sans-serif;
    font-size:16px;">
        Checking...
    </div>

    <hr style="margin:25px 0;">

    <h2 style="
    font-family:Arial, sans-serif;
    font-size:26px;
    margin-bottom:15px;
    color:#333;
    ">
        Calculate
    </h2>

    <form method="POST" style="
    display:flex;
    gap:10px;
    flex-wrap:wrap;
    align-items:flex-start;
    margin-left:0;
    font-family:Arial, sans-serif;
">
        <input name="a" value="{{a_val}}" placeholder="A" required style="
        padding:10px;
        width:140px;
        border-radius:6px;
        border:1px solid #ccc;
        font-size:16px;
        box-shadow:inset 0 1px 3px rgba(0,0,0,0.15);
    ">
        <input name="b" value="{{b_val}}" placeholder="B" required style="
        padding:10px;
        width:140px;
        border-radius:6px;
        border:1px solid #ccc;
        font-size:16px;
        box-shadow:inset 0 1px 3px rgba(0,0,0,0.15);
    ">

        <button name="add" style="
        padding:10px 20px;
        background:#3e8e41;
        border:none;
        color:white;
        border-radius:6px;
        cursor:pointer;
        font-size:15px;
        box-shadow:0 1px 4px rgba(0,0,0,0.2);
    ">Add</button>
        <button name="subtract" style="
        padding:10px 20px;
        background:#d98a00;
        border:none;
        color:white;
        border-radius:6px;
        cursor:pointer;
        font-size:15px;
        box-shadow:0 1px 4px rgba(0,0,0,0.2);
    ">Subtract</button>
        <button name="multiply" style="
        padding:10px 20px;
        background:#0074d9;
        border:none;
        color:white;
        border-radius:6px;
        cursor:pointer;
        font-size:15px;
        box-shadow:0 1px 4px rgba(0,0,0,0.2);">Multiply</button>
    </form>

    {% if result is not none %}
        <h3 style="font-family:Arial; color:#3e8e41; margin-top:20px;">Add Result: {{ result }}</h3>
    {% endif %}

    {% if sub_result is not none %}
        <h3 style="font-family:Arial; color:#d98a00; margin-top:10px;">Subtract Result: {{ sub_result }}</h3>
    {% endif %}

    {% if mul_result is not none %}
        <h3 style="font-family:Arial; color:#0074d9; margin-top:10px;">Multiply Result: {{ mul_result }}</h3>
    {% endif %}


    <!-- README MODAL -->
    <div id="readmeModal" style="
        display:none;
        position:fixed;
        top:0; left:0;
        width:100%; height:100%;
        background:rgba(0,0,0,0.7);
        padding-top:50px;
        z-index:1000;
        ">
        <div style="
            background:white;
            max-width:60%;
            margin:auto;
            padding:20px;
            border-radius:10px;
            box-shadow:0 2px 10px rgba(0,0,0,0.3);
            font-family:Arial, sans-serif;
        ">
            <h2 style="margin-top:0; color:#2b2b7c;">README / CHANGELOG</h2>
            <pre id="readmeContent" style="
            white-space:pre-wrap;
            font-size:15px;
            background:#f4f4f4;
            padding:10px;
            border-radius:6px;
            max-height:60vh;
            overflow-y:auto;
            "></pre>
            <button onclick="closeReadme()" style="
            margin-top:15px;
            padding:10px 20px;
            background:#444;
            color:white;
            border:none;
            border-radius:6px;
            cursor:pointer;
            ">
            Close
            </button>
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
                <div style="font-family: Arial; font-size: 16px; color: #22225c;">
                    <strong>Installed:</strong> ${d.installed}<br>
                    <strong>Latest:</strong> ${d.latest}<br><br>
                    

                    <form method="POST">
                        <button name="update" style="
                            padding: 8px 15px;
                            background: #4b5bd1;
                            color: white;
                            border: none;
                            border-radius: 6px;
                            font-size: 14px;
                            cursor: pointer;
                            box-shadow: 0 1px 4px rgba(0,0,0,0.2);
                            margin-bottom: 10px;
                        ">
                        Update to ${d.latest}
                        </button>
                    </form>

                    <button onclick="openReadme('${d.latest}')" style="
                        padding: 8px 15px;
                        background: #444;
                        color: white;
                        border: none;
                        border-radius: 6px;
                        font-size: 14px;
                        cursor: pointer;
                        box-shadow: 0 1px 4px rgba(0,0,0,0.2);
                    ">View README</button>
                    </div>
                `;
            }
            else {
                box.innerHTML = `
                    <div style="font-family: Arial; font-size: 16px;">
                    <strong>Installed:</strong> ${d.installed}<br>
                    <strong>Latest:</strong> ${d.latest}<br>
                </div>
                `;

                if (d.rollback_available) {
                    box.innerHTML += `
                        <br>
                        <form method="POST">
                        <button name="rollback"
                        style="
                            padding: 8px 15px;
                            background: #d9534f;
                            color: white;
                            border: none;
                            border-radius: 6px;
                            font-size: 14px;
                            cursor: pointer;
                            box-shadow: 0 1px 4px rgba(0,0,0,0.2);
                        ">
                        Rollback to ${d.previous}
                        </button>
                        </form>
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
    </div>
    </body>
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
