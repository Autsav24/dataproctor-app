import streamlit as st
import json, random, sqlite3, os, datetime, pandas as pd

# -----------------------------
# ✅ SETUP & FILE PATHS
# -----------------------------
APP_DIR = os.path.dirname(os.path.abspath(__file__))
QUESTIONS_FILE = os.path.join(APP_DIR, "questions_90.json")
ACTIVE_FILE = os.path.join(APP_DIR, "active_questions.json")
DB_FILE = os.path.join(APP_DIR, "responses.db")

# -----------------------------
# ✅ LOAD QUESTIONS
# -----------------------------
if not os.path.exists(QUESTIONS_FILE):
    st.error("❌ questions_90.json not found. Please upload it in the same folder as app.py.")
    st.stop()

try:
    with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
        questions = json.load(f)
    if not isinstance(questions, list) or len(questions) == 0:
        st.error("⚠️ questions_90.json is empty or invalid.")
        st.stop()
except Exception as e:
    st.error(f"❌ Error loading questions.json: {e}")
    st.stop()

# -----------------------------
# ✅ DB INIT
# -----------------------------
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_name TEXT,
    candidate_email TEXT,
    started_at TEXT,
    submitted_at TEXT,
    question_id INTEGER,
    question_text TEXT,
    answer_text TEXT
)''')
conn.commit()

# -----------------------------
# 🌐 PAGE CONFIG
# -----------------------------
st.set_page_config(page_title="DataProctor - Azure Data Engineer Assessment", layout="wide")
st.title("🧠 DataProctor - Azure Data Engineer Assessment")

mode = st.sidebar.selectbox("Select Mode", ["Candidate", "Admin"])

# -----------------------------
# 👩‍💻 CANDIDATE MODE
# -----------------------------
if mode == "Candidate":
    if 'started' not in st.session_state:
        st.session_state.started = False

    # Load active question list
    active_ids = []
    if os.path.exists(ACTIVE_FILE):
        with open(ACTIVE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            active_ids = data.get("active_ids", [])

    # Filter questions
    active_questions = [q for q in questions if q["id"] in active_ids] if active_ids else questions

    if not st.session_state.started:
        st.write("### Enter your details to start the assessment")
        name = st.text_input("Full Name")
        email = st.text_input("Email")
        max_questions = len(active_questions)
        question_count = st.number_input("Number of Questions", 1, max_questions, min(10, max_questions))
        duration = st.number_input("Duration (minutes)", 10, 180, 60)
        start = st.button("🚀 Start Test")

        if start:
            if not name or not email:
                st.warning("Please enter both name and email.")
            else:
                st.session_state.started = True
                st.session_state.name = name
                st.session_state.email = email
                st.session_state.qs = random.sample(active_questions, int(question_count))
                st.session_state.idx = 0
                st.session_state.answers = {}
                st.session_state.start_time = datetime.datetime.utcnow().isoformat()
                st.session_state.duration = duration
                st.experimental_rerun()

    else:
        # Timer
        start_time = datetime.datetime.fromisoformat(st.session_state.start_time)
        duration_td = datetime.timedelta(minutes=st.session_state.duration)
        remaining = duration_td - (datetime.datetime.utcnow() - start_time)
        if remaining.total_seconds() <= 0:
            st.warning("⏰ Time’s up! Auto-submitting.")
            st.session_state.submit = True

        q = st.session_state.qs[st.session_state.idx]
        st.markdown(f"### Q{st.session_state.idx + 1}: {q['text']}")
        ans = st.text_area("Your Answer", value=st.session_state.answers.get(str(q["id"]), ""), height=150)
        st.session_state.answers[str(q["id"])] = ans

        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("⬅️ Previous") and st.session_state.idx > 0:
                st.session_state.idx -= 1
                st.experimental_rerun()
        with col2:
            if st.button("➡️ Next") and st.session_state.idx < len(st.session_state.qs) - 1:
                st.session_state.idx += 1
                st.experimental_rerun()
        with col3:
            if st.button("✅ Submit Test"):
                st.session_state.submit = True

        st.sidebar.info(f"Time remaining: {str(remaining).split('.')[0]}")

        if st.session_state.get("submit", False):
            submitted_at = datetime.datetime.utcnow().isoformat()
            for q in st.session_state.qs:
                ans = st.session_state.answers.get(str(q["id"]), "")
                c.execute('INSERT INTO responses (candidate_name, candidate_email, started_at, submitted_at, question_id, question_text, answer_text) VALUES (?,?,?,?,?,?,?)',
                          (st.session_state.name, st.session_state.email, st.session_state.start_time, submitted_at, q["id"], q["text"], ans))
            conn.commit()
            st.success("✅ Your test has been submitted successfully!")
            st.session_state.clear()
            st.experimental_rerun()

# -----------------------------
# 👨‍💼 ADMIN MODE
# -----------------------------
if mode == "Admin":
    pwd = st.sidebar.text_input("Admin Password", type="password")
    if pwd != "admin123":
        st.warning("Enter correct admin password.")
    else:
        st.header("🧩 Admin Dashboard")

        # Load or initialize active IDs
        if os.path.exists(ACTIVE_FILE):
            with open(ACTIVE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                active_ids = data.get("active_ids", [])
        else:
            active_ids = []

        # Add new question
        with st.expander("➕ Add New Question"):
            with st.form("add_question_form", clear_on_submit=True):
                new_text = st.text_area("Enter Question Text", height=100)
                new_type = st.selectbox("Question Type", ["text", "longtext"])
                submit_q = st.form_submit_button("Add Question")
                if submit_q and new_text:
                    new_id = max([q["id"] for q in questions]) + 1
                    questions.append({"id": new_id, "text": new_text, "type": new_type})
                    with open(QUESTIONS_FILE, "w", encoding="utf-8") as f:
                        json.dump(questions, f, indent=2, ensure_ascii=False)
                    st.success(f"✅ Added Question #{new_id}")

        # Select active questions
        st.subheader("📘 Question Bank")
        selected_ids = st.multiselect(
            "Select active questions for candidate test",
            [q["id"] for q in questions],
            default=active_ids,
            format_func=lambda x: f"Q{x}: {next((q['text'] for q in questions if q['id'] == x), '')[:60]}..."
        )
        if st.button("💾 Save Active Selection"):
            with open(ACTIVE_FILE, "w", encoding="utf-8") as f:
                json.dump({"active_ids": selected_ids}, f, indent=2)
            st.success(f"Saved {len(selected_ids)} active questions.")

        # Show all questions
        df_q = pd.DataFrame(questions)
        st.dataframe(df_q)

        st.subheader("📊 Recent Submissions")
        df_resp = pd.read_sql_query(
            'SELECT candidate_name, candidate_email, submitted_at, COUNT(*) as q_count FROM responses GROUP BY candidate_email, submitted_at ORDER BY submitted_at DESC LIMIT 20',
            conn
        )
        st.dataframe(df_resp)

        if st.button("📥 Download All Responses"):
            df_all = pd.read_sql_query('SELECT * FROM responses', conn)
            csv = df_all.to_csv(index=False).encode('utf-8')
            st.download_button("Download CSV", csv, file_name="responses_export.csv")
