# === Imports ===
import streamlit as st
import pandas as pd
import os
import json
from datetime import datetime
from fpdf import FPDF
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive
import base64
import shutil

# === Streamlit Config ===
st.set_page_config(page_title="RSCT Therapist–Client Rater Dashboard", layout="wide")

# === Elegant Dark Theme + Fonts ===
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

# === Logo (optional) ===
if os.path.exists("logo.png"):
    st.image("logo.png", width=150)

# === Paths ===
DATA_DIR = "data"
ARC_UPLOAD_DIR = os.path.join(DATA_DIR, "arc_files")
PDF_EXPORT_DIR = os.path.join(DATA_DIR, "pdf_exports")
CREDENTIALS_FILE = os.path.join(DATA_DIR, "rater_credentials.json")
ARCS_FILE = os.path.join(DATA_DIR, "arcs.csv")
ENTRIES_FILE = os.path.join(DATA_DIR, "rater_entries.csv")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(ARC_UPLOAD_DIR, exist_ok=True)
os.makedirs(PDF_EXPORT_DIR, exist_ok=True)
# === Google Drive Auth using Service Account ===
ga = GoogleAuth()
ga.settings['client_config_backend'] = 'service'
ga.settings['service_config'] = {
    "client_json_file_path": "data/service_account_credentials.json",
    "client_user_email": "komalkaira93@gmail.com"
}
ga.ServiceAuth()
drive = GoogleDrive(ga)

# === Load Rater Credentials ===
def load_credentials():
    if os.path.exists(CREDENTIALS_FILE):
        with open(CREDENTIALS_FILE, "r") as f:
            return json.load(f)
    default_creds = {
        "agarwal.shreya1003@gmail.com": {
            "name": "Shreya Agarwal",
            "password": "shreya123",
            "batches": ["Batch_1"]
        },
        "komalkaira93@gmail.com": {
            "name": "Researcher: RSCT Komal",
            "password": "admin2025",
            "batches": "all"
        }
    }
    with open(CREDENTIALS_FILE, "w") as f:
        json.dump(default_creds, f, indent=2)
    return default_creds

def save_credentials(credentials):
    with open(CREDENTIALS_FILE, "w") as f:
        json.dump(credentials, f, indent=2)

rater_credentials = load_credentials()

# === Load Arc Data ===
@st.cache_data(ttl=2, show_spinner=False)
def load_arc_data():
    if os.path.exists(ARCS_FILE):
        return pd.read_csv(ARCS_FILE)
    return pd.DataFrame(columns=["Arc No", "Batch No", "Domain", "Cluster Files"])

def save_arc_data(df):
    df.to_csv(ARCS_FILE, index=False)

arc_data = load_arc_data()
# === Authentication ===
authenticated = st.session_state.get("authenticated", False)

user_email = st.sidebar.text_input("Email", placeholder="Enter your email").strip()
password = st.sidebar.text_input("Password", type="password")
email_key = user_email.lower()

if not authenticated:
    if st.sidebar.button("🔓 Login", key="login_button"):
        if email_key in rater_credentials and password == rater_credentials[email_key]["password"]:
            rater_info = rater_credentials[email_key]
            st.session_state["authenticated"] = True
            st.session_state["rater_name"] = rater_info["name"]
            st.session_state["name_key"] = rater_info["name"].strip().lower()
            st.session_state["allowed_batches"] = (
                sorted(arc_data["Batch No"].dropna().unique().tolist())
                if rater_info["batches"] == "all" else rater_info["batches"]
            )
            st.rerun()
        else:
            st.warning("❌ Invalid email or password.")
    st.stop()

# === Admin Check ===
is_admin = st.session_state.get("rater_name") == "Researcher: RSCT Komal"

# === ADMIN PANEL ===
if is_admin:
    st.markdown("## 🛠️ Admin Panel — Therapist–Client Rater Dashboard")

    # === Upload New Arc ===
    st.markdown("### 📤 Upload New Arc")
    with st.form("arc_upload_form"):
        arc_no = st.text_input("Arc Number")
        batch_no = st.text_input("Batch Number")
        domain_info = st.text_area("Domain Description (will be shown to rater above arc)")
        cluster_files = st.file_uploader("Upload Cluster Files", accept_multiple_files=True, type=["txt"])
        submitted = st.form_submit_button("Upload")

        if submitted and arc_no and batch_no and cluster_files:
            saved_files = []
            for file in cluster_files:
                save_path = os.path.join(ARC_UPLOAD_DIR, file.name)
                with open(save_path, "wb") as f:
                    f.write(file.read())
                saved_files.append(file.name)

            arc_entry = pd.DataFrame([{
                "Arc No": arc_no,
                "Batch No": batch_no,
                "Domain": domain_info,
                "Cluster Files": ";".join(saved_files)
            }])
            arc_data = pd.concat([arc_data, arc_entry], ignore_index=True)
            save_arc_data(arc_data)
            st.success("✅ Arc uploaded and saved.")

    # === Delete Arc ===
    st.markdown("### 🗑 Delete Arc")
    if not arc_data.empty:
        arc_to_delete = st.selectbox("Select Arc to Delete", arc_data["Arc No"].unique(), key="delete_arc_select")
        if st.button("❌ Confirm Delete", key="delete_arc_button"):
            arc_data = arc_data[arc_data["Arc No"] != arc_to_delete]
            save_arc_data(arc_data)
            for f in os.listdir(ARC_UPLOAD_DIR):
                if arc_to_delete in f:
                    try:
                        os.remove(os.path.join(ARC_UPLOAD_DIR, f))
                    except:
                        pass
            st.success(f"✅ Deleted arc {arc_to_delete} and related files.")
    else:
        st.info("ℹ️ No arcs to delete.")

    # === View Uploaded Arcs ===
    st.markdown("### 📚 View Uploaded Arcs")
    arc_data = load_arc_data()
    search_arc = st.text_input("🔍 Search Arcs", key="admin_arc_search")
    if not arc_data.empty:
        visible_rows = arc_data.copy()
        if search_arc.strip():
            visible_rows = visible_rows[
                visible_rows["Arc No"].str.contains(search_arc, case=False, na=False) |
                visible_rows["Batch No"].str.contains(search_arc, case=False, na=False)
            ]
        for _, row in visible_rows.iterrows():
            st.markdown(f"**🗂 Arc {row['Arc No']} | 📦 Batch {row['Batch No']}**")
            st.markdown(f"🔍 **Domain**: _{row['Domain']}_")
            files = row['Cluster Files'].split(";") if pd.notna(row['Cluster Files']) else []
            for file in files:
                filepath = os.path.join(ARC_UPLOAD_DIR, file)
                if os.path.exists(filepath):
                    with st.expander(f"📄 {file}"):
                        with open(filepath, "r") as f:
                            st.text(f.read())
    else:
        st.info("ℹ️ No arcs uploaded yet.")
# === RATER VIEW ===
if st.session_state.get("authenticated") and not is_admin:
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
            # === Instructions ===
            st.markdown("### 📘 Instructions: ARC-BASED CODING")
            st.info("Kindly read through each arc before beginning coding. Each arc represents a different Therapist Stance and client conversation about a specific topic or concern. Your task is to rate Therapist Stance (TF), client response impact (+1/0/-1), and confidence. Use the manual actively while rating.")

            # === Manual Viewer ===
            st.markdown("### 📕 Rater Manual (Scroll View)")
            pdf_embed_code = """
            <iframe
              src="https://mozilla.github.io/pdf.js/web/viewer.html?file=https://github.com/KomalKaira/rater_dashboard/raw/main/data/RSCT_Rater_manual.pdf"
              width="100%" height="800px"
              style="border: 1px solid #ccc; border-radius: 6px;"
              allowfullscreen
            ></iframe>
            """
            st.components.v1.html(pdf_embed_code, height=850, scrolling=True)

                       # === Conversation Viewer ===
            st.markdown("### 🩹 Therapist–Client Conversation (Scrollable)")
            conversation_file = arc_row.iloc[0]["Cluster Files"].split(";")[0].strip()
            conv_path = os.path.join(ARC_UPLOAD_DIR, conversation_file)

            if os.path.exists(conv_path):
                with open(conv_path, "r") as f:
                    lines = f.readlines()

                ts_count = 0
                cs_count = 0
                formatted_lines = []
                client_indices = []

                for idx, line in enumerate(lines):
                    stripped = line.strip()
                    if stripped.lower().startswith("therapist stance") or stripped.lower().startswith("therapist:"):
                        ts_count += 1
                        tag = f"<b style='color:#ff85b3'>TS{ts_count}</b>"
                        text = stripped.split(":", 1)[-1].strip()
                        formatted_lines.append(
                            f"<div style='margin-bottom:10px; padding:12px; background-color:#ffedf4; "
                            f"border-left:5px solid #ff2d75; border-radius:6px;'>"
                            f"<span style='color:#330015;'>{tag} 🧵 Therapist: {text}</span></div>"
                        )
                    elif stripped.lower().startswith("client i.") or stripped.lower().startswith("client:"):
                        cs_count += 1
                        client_indices.append(cs_count)
                        tag = f"<b style='color:#007acc'>CS{cs_count}</b>"
                        text = stripped.split(":", 1)[-1].strip()
                        formatted_lines.append(
                            f"<div style='margin-bottom:10px; padding:12px; background-color:#eef6ff; "
                            f"border-left:5px solid #007acc; border-radius:6px;'>"
                            f"<span style='color:#002233;'>{tag} 🩵 Client: {text}</span></div>"
                        )

                scroll_box = f"""
                <div style='height: 400px; overflow-y: auto; padding-right:10px;'>
                    {''.join(formatted_lines)}
                </div>
                """
                with st.sidebar:
                    st.markdown("### 📜 ARC Viewer")
                    st.markdown(scroll_box, unsafe_allow_html=True)
            else:
                st.warning("⚠️ Conversation file not found.")




            # === Domain ===
            st.markdown("### 🗝 Domain")
            st.markdown(
                f"<div style='background-color:#211b2a; padding:10px; border-left:4px solid #ff2d75; border-radius:6px;'>"
                f"<span style='color:#eaeaea'>{arc_row.iloc[0]['Domain']}</span></div>",
                unsafe_allow_html=True
            )

            # === Client Readiness Before Therapist Intervention ===
            st.markdown("### 🩽 Client Readiness Before Therapist Intervention")
            readiness_scale = [
                "Not open",
                "Somewhat open",
                "Open to more perspectives and insight",
                "Responsive to deeper reflections or interventions",
                "Highly open and filtered"
            ]

            col_r1, col_r2 = st.columns(2)
            readiness_rating = col_r1.selectbox("Readiness Rating", readiness_scale, key="pre_readiness")

            start_idx = None
            end_idx = None

            if client_indices:
                start_idx = col_r2.selectbox("From CS#", client_indices, key="cs_start")
                end_idx = col_r2.selectbox("To CS#", client_indices, index=len(client_indices)-1, key="cs_end")

                if start_idx is not None and end_idx is not None:
                    if client_indices.index(end_idx) < client_indices.index(start_idx):
                        st.warning("\u26a0\ufe0f 'To' statement should come after 'From' statement.")
            else:
                st.warning("\u26a0\ufe0f No client statements found. Please check the conversation file.")

            pre_readiness_data = {
                "Client Readiness (Before Intervention)": readiness_rating,
                "Range Start CS#": start_idx,
                "Range End CS#": end_idx
            }

            # === Therapist–Client Coding Table ===
            st.markdown("### 🧠 Therapist–Client Interaction Coding")

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
                    col1, col2, col3, col4 = st.columns(4)
                    row["Therapist Statement #"] = col1.selectbox("TS#", list(range(1, 26)), key=f"ts_{i}")
                    row["TF Stance"] = col2.selectbox("Stance", list(stance_options.keys()), key=f"tf_{i}")
                    row["Impact"] = col3.selectbox("Impact", list(impact_options.keys()), key=f"impact_{i}")
                    row["Confidence"] = col4.selectbox("Confidence", list(confidence_options.keys()), key=f"conf_{i}")
                    row["Notes"] = st.text_area("Notes", key=f"notes_{i}")
                    entries.append(row)

            if st.button("➕ Add Row"):
                st.session_state.tf_rows += 1

            # === Client Readiness After Intervention ===
            st.markdown("### 🧭 Client Readiness After Therapist Intervention")
            post_readiness_rating = st.selectbox("Readiness After", readiness_scale, key="post_readiness")

            # === Submit Ratings ===
            st.markdown("### ✅ Submit Your Ratings")
            if st.button("🚀 Submit Final Entry"):
                for i, entry in enumerate(entries):
                    if any(entry[k] in [None, ""] for k in ["Therapist Statement #", "TF Stance", "Impact", "Confidence"]):
                        st.error(f"🚫 Row {i+1} is incomplete.")
                        st.stop()

                submission_data = {
                    "Rater Name": rater_name,
                    "Date": str(datetime.now().date()),
                    "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Arc No": selected_arc,
                    "Batch No": batch_no,
                    "Client Readiness (Before)": pre_readiness_data["Client Readiness (Before Intervention)"],
                    "Range Start CS#": pre_readiness_data["Range Start CS#"],
                    "Range End CS#": pre_readiness_data["Range End CS#"],
                    "Client Readiness (After)": post_readiness_rating
                }

                for idx, entry in enumerate(entries):
                    submission_data[f"Row_{idx+1}_TS#"] = entry["Therapist Statement #"]
                    submission_data[f"Row_{idx+1}_TF"] = stance_options[entry["TF Stance"]]
                    submission_data[f"Row_{idx+1}_Impact"] = impact_options[entry["Impact"]]
                    submission_data[f"Row_{idx+1}_Confidence"] = confidence_options[entry["Confidence"]]
                    submission_data[f"Row_{idx+1}_Notes"] = entry["Notes"]

                df_entry = pd.DataFrame([submission_data])
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                safe_rater = rater_name.replace(" ", "_").replace("/", "-")
                filename = f"{safe_rater}_{selected_arc}_{timestamp}.csv"
                csv_path = os.path.join(DATA_DIR, filename)
                df_entry.to_csv(csv_path, index=False)

                if os.path.exists(ENTRIES_FILE):
                    df_all = pd.read_csv(ENTRIES_FILE)
                    df_all = pd.concat([df_all, df_entry], ignore_index=True)
                else:
                    df_all = df_entry
                df_all.to_csv(ENTRIES_FILE, index=False)

                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", size=12)
                for key, val in submission_data.items():
                    pdf.multi_cell(0, 10, txt=f"{key}: {val}", border=0)
                pdf_path = os.path.join(PDF_EXPORT_DIR, f"{safe_rater}_{timestamp}.pdf")
                pdf.output(pdf_path)

                try:
                    gfile = drive.CreateFile({'title': os.path.basename(pdf_path)})
                    gfile.SetContentFile(pdf_path)
                    gfile.Upload()
                    st.success("📄 PDF uploaded to Google Drive.")
                except Exception as e:
                    st.warning(f"⚠️ PDF upload failed: {e}")

                try:
                    gfile_csv = drive.CreateFile({'title': 'rater_entries.csv'})
                    gfile_csv.SetContentFile(ENTRIES_FILE)
                    gfile_csv.Upload()
                    st.success("📄 Master CSV uploaded to Google Drive.")
                except Exception as e:
                    st.warning(f"⚠️ CSV upload failed: {e}")

                st.success("✅ Entry submitted successfully.")
                st.balloons()
