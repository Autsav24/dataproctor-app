import streamlit as st
import json, random, sqlite3, os, datetime, pandas as pd

# -----------------------------
# ✅ SAFE FILE PATHS
# -----------------------------
APP_DIR = os.path.dirname(os.path.abspath(__file__))
QUESTIONS_FILE = os.path.join(APP_DIR, "questions.json")
DB_FILE = os.path.join(APP_DIR, "responses.db")

# -----------------------------
# ✅ FILE SAFETY CHECKS
# -----------------------------
# Auto-create questions.json if missing
if not os.path.exists(QUESTIONS_FILE):
    with open(QUESTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump([], f)

# Auto-create database if missing
if not os.path.exists(DB_FILE):
    conn = sqlite3.connect(DB_FILE)
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
    conn.close()

# -----------------------------
# ✅ LOAD QUESTIONS SAFELY
# -----------------------------
with open(QUESTIONS_FILE, 'r', encoding='utf-8') as f:
    try:
        questions = json.load(f)
        if not isinstance(questions, list):
            questions = []
    except json.JSONDecodeError:
        st.error("❌ Error loading questions.json — file corrupted or invalid JSON.")
        questions = []

# -----------------------------
# ✅ DB CONNECTION
# -----------------------------
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
c = conn.cursor()

# -----------------------------
# ✅ PAGE SETUP
# -----------------------------
st.set_page_config(page_title="DataProctor - Azure Data Engineer Assessment", layout="wide")
st.title("🧠 DataProctor: Azure Data Engineer Assessment")

mode = st.sidebar.selectbox("Mode", ["Candidate", "Admin"])

# -----------------------------
# 🎯 CANDIDATE MODE
# -----------------------------
if mode == "Candidate":
    if 'started' not in st.session_state:
        st.session_state.started = False

    if not st.session_state.started:
        st.write("Please enter your details to start the test.")
        name = st.text_input("Full Name")
        email = st.text_input("Email")
        question_count = st.number_input(
            "Number of questions (randomized)", 
            min_value=5, 
            max_value=max(5, len(questions)), 
            value=10, 
            step=1
        )
        duration_mins = st.number_input("Duration (minutes)", min_value=10, max_value=240, value=30, step=5)
        start = st.button("🚀 Start Test")

        if start:
            if not name or not email:
                st.warning("Please fill both Name and Email to begin.")
            elif not questions:
                st.error("⚠️ No questions available. Please ask admin to add questions.")
            else:
                st.session_state.candidate = {"name": name, "email": email}
                st.session_state.qs = random.sample(questions, min(len(questions), int(question_count)))
                st.session_state.idx = 0
                st.session_state.answers = {}
                st.session_state.started = True
                st.session_state.start_time = datetime.datetime.utcnow().isoformat()
                st.session_state.duration = duration_mins
                st.experimental_rerun()

    else:
        # Timer calculation
        start_time = datetime.datetime.fromisoformat(st.session_state.start_time)
        duration = datetime.timedelta(minutes=int(st.session_state.get('duration', 30)))
        elapsed = datetime.datetime.utcnow() - start_time
        remaining = duration - elapsed
        if remaining.total_seconds() <= 0:
            st.warning("⏰ Time is up! Submitting automatically...")
            st.session_state.submit = True

        col1, col2 = st.columns([3, 1])
        with col1:
            q = st.session_state.qs[st.session_state.idx]
            st.markdown(f"### Question {st.session_state.idx + 1} of {len(st.session_state.qs)}")
            st.write(q['text'])

            if q.get('type', 'text') == 'text':
                ans = st.text_input("Your Answer", value=st.session_state.answers.get(str(q['id']), ""), key=f"ans_{q['id']}")
            else:
                ans = st.text_area("Your Answer", value=st.session_state.answers.get(str(q['id']), ""), height=200, key=f"ans_{q['id']}")

            st.session_state.answers[str(q['id'])] = ans

            # Navigation
            nav1, nav2, nav3 = st.columns(3)
            with nav1:
                if st.button("⬅️ Previous") and st.session_state.idx > 0:
                    st.session_state.idx -= 1
                    st.experimental_rerun()
            with nav2:
                if st.button("➡️ Next") and st.session_state.idx < len(st.session_state.qs) - 1:
                    st.session_state.idx += 1
                    st.experimental_rerun()
            with nav3:
                if st.button("✅ Submit Test"):
                    st.session_state.submit = True

        with col2:
            st.markdown("### Test Info")
            st.info(f"Candidate: {st.session_state.candidate['name']}")
            st.write(f"Email: {st.session_state.candidate['email']}")
            st.write(f"Question: {st.session_state.idx + 1}/{len(st.session_state.qs)}")
            st.warning(f"⏱️ Time Remaining: {str(remaining).split('.')[0]}")

        # Submit responses
        if st.session_state.get('submit', False):
            submitted_at = datetime.datetime.utcnow().isoformat()
            for q in st.session_state.qs:
                qid = q['id']
                ans = st.session_state.answers.get(str(qid), "")
                c.execute(
                    '''INSERT INTO responses 
                    (candidate_name, candidate_email, started_at, submitted_at, question_id, question_text, answer_text) 
                    VALUES (?,?,?,?,?,?,?)''',
                    (
                        st.session_state.candidate['name'],
                        st.session_state.candidate['email'],
                        st.session_state.start_time,
                        submitted_at,
                        qid,
                        q['text'],
                        ans
                    )
                )
            conn.commit()
            st.success("🎉 Test submitted successfully! Thank you.")
            st.session_state.started = False
            st.session_state.submit = False
            st.experimental_rerun()

# -----------------------------
# 👨‍💼 ADMIN MODE
# -----------------------------
if mode == "Admin":
    pwd = st.sidebar.text_input("Admin password", type="password")
    if pwd != "admin123":
        st.warning("Please enter correct admin password.")
    else:
        st.header("Admin Dashboard")
        st.markdown("#### 🧩 Manage Questions")

        # Add Question Form
        with st.expander("➕ Add New Question"):
            with st.form("add_q_form", clear_on_submit=True):
                new_q_text = st.text_area("Enter Question Text", height=120)
                new_q_type = st.selectbox("Question Type", ["text", "longtext"])
                submitted = st.form_submit_button("Add Question")
                if submitted and new_q_text:
                    new_id = max([q.get('id', 0) for q in questions], default=0) + 1
                    questions.append({"id": new_id, "text": new_q_text, "type": new_q_type})
                    with open(QUESTIONS_FILE, "w", encoding="utf-8") as f:
                        json.dump(questions, f, indent=2, ensure_ascii=False)
                    st.success(f"✅ Added question #{new_id}")

        st.markdown("#### 📘 Question Bank")
        if questions:
            df_q = pd.DataFrame(questions)
            st.dataframe(df_q)
        else:
            st.info("No questions available yet.")

        st.markdown("#### 📊 Recent Submissions")
        df = pd.read_sql_query(
            'SELECT candidate_name, candidate_email, submitted_at, count(*) as q_count FROM responses GROUP BY candidate_email, submitted_at ORDER BY submitted_at DESC LIMIT 20',
            conn
        )
        st.dataframe(df)

        if st.button("📥 Download All Responses"):
            df_all = pd.read_sql_query('SELECT * FROM responses', conn)
            csv_file = os.path.join(APP_DIR, f"responses_{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv")
            df_all.to_csv(csv_file, index=False)
            with open(csv_file, "rb") as f:
                st.download_button("Download CSV", f, file_name=os.path.basename(csv_file))
