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

# === GOOGLE DRIVE AUTH ===
service_creds = dict(st.secrets["google_service_account"])
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
# === LOGIN ===
st.markdown("## 🔐 Therapist–Client Rater Dashboard")
email = st.text_input("Email", key="login_email")
password = st.text_input("Password", type="password", key="login_password")

if email in rater_credentials and password == rater_credentials[email]["password"]:
    st.success(f"✅ Logged in as {rater_credentials[email]['name']}")
    is_admin = email == "komalkaira93@gmail.com"
else:
    st.stop()

# === EMBEDDED MANUAL ===
st.markdown("## 📘 TC Rater Manual Viewer")
try:
    with open("RSCT_TC_Rater_Manual.pdf", "rb") as file:
        base64_pdf = base64.b64encode(file.read()).decode("utf-8")
    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="600px" type="application/pdf"></iframe>'
    st.markdown(pdf_display, unsafe_allow_html=True)
except FileNotFoundError:
    st.warning("⚠️ Manual file not found. Please ensure `RSCT_TC_Rater_Manual.pdf` is in the main folder.")

# === SIDEBAR ARC SELECTOR ===
st.sidebar.header("🗂 Select Arc")
batch_list = sorted(arc_data["Batch No"].unique()) if not arc_data.empty else []
batch_no = st.sidebar.selectbox("Choose Batch", batch_list)
arc_list = sorted(arc_data[arc_data["Batch No"] == batch_no]["Arc No"]) if batch_no else []
selected_arc = st.sidebar.selectbox("Choose Arc", arc_list)
arc_row = arc_data[(arc_data["Arc No"] == selected_arc) & (arc_data["Batch No"] == batch_no)]

# === SIDEBAR ARC VIEWER ===
if not arc_row.empty:
    st.sidebar.markdown("### 📜 ARC Viewer")
    cluster_files = arc_row.iloc[0]["Cluster Files"].split(";")
    combined_text = ""
    for fname in cluster_files:
        fpath = os.path.join(ARC_DIR, fname.strip())
        if os.path.exists(fpath):
            with open(fpath, "r") as f:
                content = f.read()
            combined_text += f"\n\n--- {fname.strip()} ---\n{content.strip()}"
        else:
            combined_text += f"\n\n--- {fname.strip()} ---\n⚠️ File not found."

    st.sidebar.text_area("🧠 Full Arc", value=combined_text.strip(), height=600, key="arc_viewer", disabled=True)

# === ADMIN: ARC UPLOAD PANEL ===
if is_admin:
    st.markdown("## 🛠 Admin Panel: Upload Arc")
    st.info("Upload new therapist–client arc for rating. It will be available in the selected batch for viewing.")

    arc_no = st.text_input("New Arc Number")
    batch_no_input = st.text_input("Assign to Batch")
    domain = st.text_area("Domain / Focus of Arc")
    uploaded_files = st.file_uploader("Upload Cluster Files (.txt)", accept_multiple_files=True, type=["txt"])

    if st.button("Upload Arc"):
        if arc_no and batch_no_input and uploaded_files:
            file_names = []
            for file in uploaded_files:
                fname = file.name
                with open(os.path.join(ARC_DIR, fname), "wb") as f:
                    f.write(file.read())
                file_names.append(fname)
            new_row = pd.DataFrame([{
                "Arc No": arc_no,
                "Batch No": batch_no_input,
                "Domain": domain,
                "Cluster Files": ";".join(file_names)
            }])
            arc_data_updated = pd.concat([arc_data, new_row], ignore_index=True)
            save_arc_data(arc_data_updated)
            st.success(f"✅ Arc {arc_no} uploaded to {batch_no_input}")
        else:
            st.warning("⚠️ Fill Arc No, Batch, and upload at least one file.")
# === DOMAIN DISPLAY ===
if not arc_row.empty:
    st.markdown("## 🧭 Domain")
    st.markdown(f"""
    <div style='background-color:#e8f0fe; padding: 1rem; border-radius: 8px; font-size: 1rem'>
    {arc_row.iloc[0]['Domain']}
    </div>
    """, unsafe_allow_html=True)

# === CLIENT READINESS BEFORE INTERVENTION ===
st.markdown("## 🧶 Client Readiness (Before Intervention)")
client_statements = [line for line in combined_text.split('\n') if line.strip().startswith("Client Statement")]
client_indices = [line.split(":")[0].strip() for line in client_statements]

start_cs = st.selectbox("From (Client Statement)", client_indices, key="start_cs")
end_cs = st.selectbox("To (Client Statement)", client_indices, key="end_cs")

if start_cs in client_indices and end_cs in client_indices:
    if client_indices.index(end_cs) < client_indices.index(start_cs):
        st.warning("⚠️ 'To' statement must come after 'From' statement.")

readiness_scale = [
    "Not open",
    "Somewhat open",
    "Open to more perspectives and insight",
    "Responsive to deeper reflections or interventions",
    "Highly open and filtered"
]
readiness_before = st.selectbox("Client Readiness BEFORE Therapist Interventions", readiness_scale, key="readiness_before")

# === THERAPIST STATEMENT CODING TABLE ===
st.markdown("## 💬 Therapist Intervention Coding")
therapist_statements = [line for line in combined_text.split('\n') if line.strip().startswith("Therapist Statement")]
therapist_indices = [line.split(":")[0].strip() for line in therapist_statements]

tf_codes = {
    "TF1: Tentative / Reflective": "TF1",
    "TF2: Directive / Structuring": "TF2",
    "TF3: Clarifying / Summarizing": "TF3",
    "TF4: Empathic / Affirming": "TF4",
    "TF5: Challenging / Reframing": "TF5"
}
impact_codes = {"+1": "+1 (Expanded PF)", "0": "0 (Neutral / No Change)", "-1": "-1 (Closed PF)"}

therapist_coding = []
for ts in therapist_indices:
    with st.expander(f"🧠 Code {ts}"):
        stance = st.selectbox(f"{ts} – Therapist Stance", list(tf_codes.keys()), key=f"{ts}_stance")
        impact = st.selectbox(f"{ts} – Impact on Client PF", list(impact_codes.values()), key=f"{ts}_impact")
        confidence = st.slider(f"{ts} – Confidence Rating (1–5)", 1, 5, 3, key=f"{ts}_confidence")
        notes = st.text_area(f"{ts} – Notes (optional)", key=f"{ts}_notes")
        therapist_coding.append({
            "Statement": ts,
            "Stance": tf_codes[stance],
            "Impact": impact.split(" ")[0],
            "Confidence": confidence,
            "Notes": notes
        })
# === GENERATE PDF AND UPLOAD TO GOOGLE DRIVE ONLY ===
from fpdf import FPDF

pdf = FPDF()
pdf.add_page()
pdf.set_font("Arial", size=12)
pdf.cell(200, 10, txt="Therapist–Client Arc Rating Summary", ln=True, align='C')
pdf.ln(10)

for key, value in submission.items():
    if key == "Therapist Coding":
        pdf.set_font("Arial", "B", size=12)
        pdf.cell(200, 10, txt="Therapist Coding:", ln=True)
        pdf.set_font("Arial", size=11)
        for item in value:
            pdf.multi_cell(0, 8, txt=f"{item['Statement']}:\n  Stance: {item['Stance']} | Impact: {item['Impact']} | Confidence: {item['Confidence']}\n  Notes: {item['Notes']}")
            pdf.ln(2)
    else:
        pdf.set_font("Arial", "B", size=12)
        pdf.cell(200, 8, txt=f"{key}:", ln=True)
        pdf.set_font("Arial", size=11)
        pdf.multi_cell(0, 8, txt=str(value))
        pdf.ln(2)

# === SAVE PDF LOCALLY FOR DRIVE UPLOAD ===
pdf_path = os.path.join(output_dir, filename.replace(".json", ".pdf"))
try:
    pdf.output(pdf_path)

    # === UPLOAD TO GOOGLE DRIVE: rsct/RSCT Data/Client Data/TC Rater/ ===
    gfile = drive.CreateFile({
        'title': os.path.basename(pdf_path),
        'parents': [{"id": "1zhNzAI3fRiwWZnsLgUPR2iU9_7A5xy5d"}]  # ✅ Correct folder ID for TC Rater in Client Data
    })
    gfile.SetContentFile(pdf_path)
    gfile.Upload()

    st.success("✅ PDF uploaded to Google Drive.")
except Exception as e:
    st.error(f"⚠️ PDF upload failed: {str(e)}")

# === FINAL SUCCESS MESSAGE ===
st.success("✅ Entry submitted and saved.")
