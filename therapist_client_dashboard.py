# === IMPORTS ===
import streamlit as st
import pandas as pd
import os
import json
from datetime import datetime
from fpdf import FPDF
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive
import shutil
import tempfile

# === STREAMLIT CONFIG ===
st.set_page_config(page_title="RSCT Therapist–Client Rater Dashboard", layout="wide")

# === DARK THEME + FONTS ===
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=Inter:wght@300;400;600&display=swap');
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
    color: #f4f4f4;
}
.stApp {
    background: linear-gradient(135deg, #0a0a0f 0%, #1b1123 40%, #2b0033 80%) fixed;
    min-height: 100vh;
}
section[data-testid="stSidebar"] {
    background: linear-gradient(to bottom, #1a1a2f, #10091c);
    border-right: 1px solid #2e2e40;
    box-shadow: inset -2px 0 10px #ff2d75;
}
h1, h2, h3, h4 {
    font-family: 'DM Serif Display', serif;
    color: #ff2d75;
}
.stTextInput input, .stTextArea textarea, .stSelectbox div[role="combobox"] {
    background-color: #251b2f;
    color: #ffffff;
    border: 1px solid #5a2a5c;
    border-radius: 6px;
}
button[kind="primary"] {
    background-color: #ff2d75 !important;
    color: white !important;
    border-radius: 6px;
    font-weight: 600;
}
.stExpanderHeader { background-color: #201324 !important; color: #fce4f5 !important; }
.stExpanderContent { background-color: #170d1e !important; }
</style>
""", unsafe_allow_html=True)

# === PATHS ===
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
ARC_DIR = os.path.join(DATA_DIR, "arc_files")
os.makedirs(ARC_DIR, exist_ok=True)
PDF_DIR = os.path.join(DATA_DIR, "pdf_exports")
os.makedirs(PDF_DIR, exist_ok=True)

CREDENTIALS_FILE = os.path.join(DATA_DIR, "rater_credentials.json")
ENTRIES_FILE = os.path.join(DATA_DIR, "rater_entries.csv")
ARCS_FILE = os.path.join(DATA_DIR, "arcs.csv")

# === GOOGLE DRIVE AUTH (Streamlit + PyDrive2 with service account) ===
import json
import tempfile

try:
    # ✅ Use secrets on Streamlit Cloud
    service_creds = dict(st.secrets["google_service_account"])
except Exception:
    # ✅ Fallback to local credentials when running in VS Code
    with open("data/service_account_credentials.json", "r") as f:
        service_creds = json.load(f)

# 🔐 Create a temporary credentials file for PyDrive2
with tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w") as tmp:
    json.dump(service_creds, tmp)
    tmp.flush()
    tmp_path = tmp.name

gauth = GoogleAuth()
gauth.settings["client_config_backend"] = "service"
gauth.settings["service_config"] = {
    "client_json_file_path": tmp_path,
    "client_user_email": service_creds["client_email"]
}
gauth.ServiceAuth()
drive = GoogleDrive(gauth)

# === AUTH ===
@st.cache_data(ttl=2)
def load_arc_data():
    if os.path.exists(ARCS_FILE):
        return pd.read_csv(ARCS_FILE)
    return pd.DataFrame(columns=["Arc No", "Batch No", "Domain", "Cluster Files"])

def save_arc_data(df):
    df.to_csv(ARCS_FILE, index=False)

def load_credentials():
    if os.path.exists(CREDENTIALS_FILE):
        with open(CREDENTIALS_FILE, "r") as f:
            return json.load(f)
    default = {
        "komalkaira93@gmail.com": {"name": "Researcher: RSCT Komal", "password": "admin2025", "batches": "all"},
        "agarwal.shreya1003@gmail.com": {"name": "Shreya Agarwal", "password": "shreya123", "batches": ["Batch_1"]}
    }
    with open(CREDENTIALS_FILE, "w") as f:
        json.dump(default, f, indent=2)
    return default

rater_credentials = load_credentials()
arc_data = load_arc_data()

# === LOGIN PANEL ===
authenticated = st.session_state.get("authenticated", False)
user_email = st.sidebar.text_input("Email", placeholder="Enter your email").strip()
password = st.sidebar.text_input("Password", type="password")
email_key = user_email.lower()

if not authenticated:
    if st.sidebar.button("🔓 Login", key="login_btn"):
        if email_key in rater_credentials and password == rater_credentials[email_key]["password"]:
            rater = rater_credentials[email_key]
            st.session_state["authenticated"] = True
            st.session_state["rater_name"] = rater["name"]
            st.session_state["allowed_batches"] = arc_data["Batch No"].unique().tolist() if rater["batches"] == "all" else rater["batches"]
            st.session_state["name_key"] = email_key.split("@")[0]
            st.rerun()
        else:
            st.warning("❌ Invalid credentials.")
    st.stop()
# === ADMIN PANEL ===
is_admin = st.session_state["rater_name"] == "Researcher: RSCT Komal"
if is_admin:
    st.markdown("## 🛠 Admin Panel")

    st.markdown("### 📤 Upload Arc")
    with st.form("upload_arc_form"):
        arc_no = st.text_input("Arc Number")
        batch_no = st.text_input("Batch Number")
        domain = st.text_area("Domain Description")
        cluster_files = st.file_uploader("Upload Cluster Files", accept_multiple_files=True, type=["txt"])
        submit_arc = st.form_submit_button("Upload Arc")

        if submit_arc and arc_no and batch_no and cluster_files:
            saved_files = []
            for file in cluster_files:
                path = os.path.join(ARC_DIR, file.name)
                with open(path, "wb") as f:
                    f.write(file.read())
                saved_files.append(file.name)

            new_row = pd.DataFrame([{
                "Arc No": arc_no,
                "Batch No": batch_no,
                "Domain": domain,
                "Cluster Files": ";".join(saved_files)
            }])
            arc_data = pd.concat([arc_data, new_row], ignore_index=True)
            save_arc_data(arc_data)
            st.success("✅ Arc uploaded.")

    st.markdown("### 📚 Uploaded Arcs")
    if not arc_data.empty:
        for _, row in arc_data.iterrows():
            st.markdown(f"**Arc {row['Arc No']} | Batch {row['Batch No']}**")
            st.markdown(f"🗝 **Domain:** {row['Domain']}")
            for fname in row["Cluster Files"].split(";"):
                with st.expander(f"📄 {fname}"):
                    with open(os.path.join(ARC_DIR, fname), "r") as f:
                        st.text(f.read())
    else:
        st.info("ℹ️ No arcs uploaded.")

# === MANUAL SECTION (Rater Guide) ===
st.markdown("### 📖 Therapist–Client Rater Manual")

with st.expander("📙 CLIENT READINESS TABLE", expanded=False):
    st.markdown("""
| **Example Statement** | **What It Suggests** | **How Open Might They Be** |
|----------------------|----------------------|-----------------------------|
| _This will always go on..._ | Fixed or rigid view of self | **Not Open** |
| _I don’t think things can be different._ | Curious but stuck | **Somewhat Open** |
| _I don’t always have the answers._ | Exploring, not yet acting | **Open to More Insight** |
| _It’s okay to let ourselves be._ | Reflective, still reactive | **Responsive to Deeper Reflections** |
| _I’ve changed... I’m resting._ | Self-regulating | **Highly Open Yet Filtered** |
""", unsafe_allow_html=True)

with st.expander("📕 THERAPIST STANCE TABLE (TF1–TF5)", expanded=False):
    st.markdown("""
| **Code** | **Example** | **Meaning** |
|----------|-------------|-------------|
| TF1 | _You just don’t want to change._ | Expert/Directive |
| TF2 | _Maybe your boss is the problem?_ | Suggestive |
| TF3 | _Can we explore this moment?_ | Collaborative |
| TF4 | _As you mentioned last time..._ | Pattern-based |
| TF5 | _What helped you stay present?_ | Client-led integration |
""", unsafe_allow_html=True)

with st.expander("🧽 INTERVENTION IMPACT SCORING", expanded=False):
    st.markdown("""
| **Score** | **Meaning** |
|-----------|-------------|
| +1 | Supported insight or action |
| 0  | No visible impact |
| -1 | Reinforced older pattern |
""", unsafe_allow_html=True)

with st.expander("🎯 CONFIDENCE SCORE TABLE", expanded=False):
    st.markdown("""
| **Score** | **Meaning** |
|-----------|-------------|
| 1 | Total guess |
| 2 | Tentative/unstable |
| 3 | Middle confidence |
| 4 | Confident |
| 5 | Very clear |
""", unsafe_allow_html=True)

# === RATER VIEW ===
if st.session_state.get("authenticated") and st.session_state.get("rater_name") != "Researcher: RSCT Komal":
    rater_name = st.session_state["rater_name"]
    name_key = st.session_state["name_key"]
    allowed_batches = st.session_state["allowed_batches"]

    st.sidebar.markdown(f"**Logged in as:** {rater_name}")
    batch_no = st.sidebar.selectbox("Batch Number", allowed_batches)
    arc_options = arc_data[arc_data["Batch No"] == batch_no]["Arc No"].astype(str).tolist()

    if arc_options:
        selected_arc = st.selectbox("Select Arc Number", arc_options)
        arc_row = arc_data[
            (arc_data["Arc No"].astype(str) == selected_arc) &
            (arc_data["Batch No"] == batch_no)
        ]

        if not arc_row.empty:
            arc_info = arc_row.iloc[0]
            conversation_file = arc_info["Cluster Files"].split(";")[0]
            full_path = os.path.join(ARC_DIR, conversation_file)

            if os.path.exists(full_path):
                with open(full_path, "r") as f:
                    lines = f.readlines()

                ts_count, cs_count = 0, 0
                client_indices = []
                blocks = []

                for line in lines:
                    text = line.strip()
                    if text.lower().startswith("therapist") or text.startswith("TS"):
                        ts_count += 1
                        tag = f"TS{ts_count}"
                        blocks.append(
                            f"<div style='background:#ffedf4; color:#000000; padding:8px; margin:4px 0; border-left:4px solid #ff2d75; border-radius:6px'>"
                            f"<b style='color:#ff2d75'>{tag}</b>: {text.split(':',1)[-1].strip()}</div>"
                        )
                    elif text.lower().startswith("client") or text.startswith("CS"):
                        cs_count += 1
                        tag = f"CS{cs_count}"
                        client_indices.append(cs_count)
                        blocks.append(
                            f"<div style='background:#eef6ff; color:#000000; padding:8px; margin:4px 0; border-left:4px solid #2b8cd6; border-radius:6px'>"
                            f"<b style='color:#2b8cd6'>{tag}</b>: {text.split(':',1)[-1].strip()}</div>"
                        )

                with st.sidebar:
                    st.markdown("### 📜 ARC Viewer")
                    st.markdown(
                        "<div style='max-height:500px; overflow-y:auto; padding-right:10px'>" +
                        ''.join(blocks) + "</div>",
                        unsafe_allow_html=True
                    )

                st.markdown("### 🗝 Domain")
                st.markdown(f"<div style='background:#1e1626; padding:10px; border-left:4px solid #ff2d75; border-radius:6px'>{arc_info['Domain']}</div>", unsafe_allow_html=True)

                st.markdown("### 🩽 Client Readiness (Before Intervention)")
                readiness_scale = [
                    "Not open", "Somewhat open", "Open to more perspectives and insight",
                    "Responsive to deeper reflections or interventions", "Highly open and filtered"
                ]
                col1, col2 = st.columns(2)
                pre_readiness = col1.selectbox("Rating", readiness_scale, key="pre_ready")
                start_cs = col2.selectbox("From CS#", client_indices, key="start_cs")
                end_cs = col2.selectbox("To CS#", client_indices, index=len(client_indices)-1, key="end_cs")

                if start_cs in client_indices and end_cs in client_indices:
                    if client_indices.index(end_cs) < client_indices.index(start_cs):
                        st.warning("⚠️ 'To' statement must come after 'From' statement.")

                st.markdown("### 🧠 Therapist–Client Coding Table")

                stance_options = {
                    "TF1: Directive and Expert position": 1,
                    "TF2: Suggestive Interpretation": 2,
                    "TF3: Collaborative Exploration": 3,
                    "TF4: Pattern-oriented Reflection": 4,
                    "TF5: Client-led Integration": 5
                }

                impact_options = {
                    "+1 — Supported deeper insight or action": "+1",
                    "0 — No observable impact": "0",
                    "-1 — Disrupted or reinforced older patterns": "-1"
                }

                confidence_options = {
                    "1 — Total guess": 1,
                    "2 — Tentative": 2,
                    "3 — Middle confidence": 3,
                    "4 — Confident": 4,
                    "5 — Very clear": 5
                }

                if "tf_rows" not in st.session_state:
                    st.session_state.tf_rows = 5

                entries = []
                for i in range(st.session_state.tf_rows):
                    with st.expander(f"📝 Entry Row {i+1}", expanded=True):
                        row = {}
                        c1, c2, c3, c4 = st.columns(4)
                        row["TS#"] = c1.selectbox("TS#", list(range(1, 26)), key=f"ts_{i}")
                        row["TF"] = c2.selectbox("Therapist Stance", list(stance_options.keys()), key=f"tf_{i}")
                        row["Impact"] = c3.selectbox("Intervention Impact", list(impact_options.keys()), key=f"impact_{i}")
                        row["Confidence"] = c4.selectbox("Confidence Score", list(confidence_options.keys()), key=f"conf_{i}")
                        row["Notes"] = st.text_area("Optional Notes", key=f"notes_{i}")
                        entries.append(row)

                if st.button("➕ Add More Rows"):
                    st.session_state.tf_rows += 1

                st.markdown("### 🧭 Client Readiness (After Intervention)")
                post_readiness = st.selectbox("Post Rating", readiness_scale, key="post_ready")

                st.markdown("### ✅ Submit Final Ratings")
                if st.button("🚀 Submit Entry"):
                    for i, entry in enumerate(entries):
                        if any(entry[k] in [None, ""] for k in ["TS#", "TF", "Impact", "Confidence"]):
                            st.error(f"🚫 Row {i+1} is incomplete.")
                            st.stop()

                    now = datetime.now()
                    timestamp = now.strftime("%Y-%m-%d %H-%M-%S")
                    rater_id = rater_name.replace(" ", "_")
                    arc_id = arc_info["Arc No"]

                    submission = {
                        "Rater": rater_name,
                        "Arc No": arc_id,
                        "Batch No": batch_no,
                        "Date": now.date().isoformat(),
                        "Time": now.strftime("%H:%M:%S"),
                        "Client Readiness (Before)": pre_readiness,
                        "CS Range Start": start_cs,
                        "CS Range End": end_cs,
                        "Client Readiness (After)": post_readiness
                    }

                    for idx, row in enumerate(entries):
                        submission[f"Row{idx+1}_TS#"] = row["TS#"]
                        submission[f"Row{idx+1}_TF"] = stance_options[row["TF"]]
                        submission[f"Row{idx+1}_Impact"] = impact_options[row["Impact"]]
                        submission[f"Row{idx+1}_Confidence"] = confidence_options[row["Confidence"]]
                        submission[f"Row{idx+1}_Notes"] = row["Notes"]

                    df_submit = pd.DataFrame([submission])
                    filename = f"{rater_id}_{arc_id}_{timestamp}.csv"
                    csv_path = os.path.join(DATA_DIR, filename)
                    df_submit.to_csv(csv_path, index=False)

                    if os.path.exists(ENTRIES_FILE):
                        df_all = pd.read_csv(ENTRIES_FILE)
                        df_all = pd.concat([df_all, df_submit], ignore_index=True)
                    else:
                        df_all = df_submit
                    df_all.to_csv(ENTRIES_FILE, index=False)

                    pdf = FPDF()
                    pdf.add_page()
                    pdf.set_font("Arial", size=12)
                    for key, val in submission.items():
                        pdf.multi_cell(0, 10, txt=f"{key}: {val}", border=0)
                    pdf_path = os.path.join(PDF_DIR, f"{rater_id}_{timestamp}.pdf")
                    pdf.output(pdf_path)

                    PDF_FOLDER_ID = "1DZhaJ_6hNmQFj19BND4pwuLf-AoDUoDa"  # RSCT Rater Submissions

                    try:
                        gfile = drive.CreateFile({
                            'title': os.path.basename(pdf_path),
                            'parents': [{'id': "1DZhaJ_6hNmQFj19BND4pwuLf-AoDUoDa"}]
                        })
                        gfile.SetContentFile(pdf_path)
                        gfile.Upload()
                        print("Uploaded file ID:", gfile['id'])
                        st.success("📄 PDF uploaded to shared Google Drive folder.")
                    except Exception as e:
                        st.warning(f"⚠️ PDF upload failed: {e}")



                    try:
                        gfile_csv = drive.CreateFile({'title': 'rater_entries.csv'})
                        gfile_csv.SetContentFile(ENTRIES_FILE)
                        gfile_csv.Upload()
                        st.success("📄 Master CSV uploaded to Google Drive.")
                    except Exception as e:
                        st.warning(f"⚠️ CSV upload failed: {e}")

                    st.success("✅ Ratings submitted successfully.")
                    st.balloons()
