
import streamlit as st
import json, random, sqlite3, os, datetime, pandas as pd

APP_DIR = os.path.join(os.path.dirname(__file__))
QUESTIONS_FILE = os.path.join(APP_DIR, "questions.json")
DB_FILE = os.path.join(APP_DIR, "responses.db")

# Load questions
with open(QUESTIONS_FILE, 'r', encoding='utf-8') as f:
    questions = json.load(f)

# Initialize DB
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

st.set_page_config(page_title="Azure Data Engineer Assessment", layout="wide")
st.title("Azure Data Engineer Assessment (Prototype)")

mode = st.sidebar.selectbox("Mode", ["Candidate", "Admin"])

if mode == "Candidate":
    if 'started' not in st.session_state:
        st.session_state.started = False
    if not st.session_state.started:
        st.write("Please enter your details and start the test.")
        name = st.text_input("Full name")
        email = st.text_input("Email")
        question_count = st.number_input("Number of questions (randomized)", min_value=5, max_value=len(questions), value=20, step=1)
        duration_mins = st.number_input("Duration (minutes)", min_value=10, max_value=240, value=60, step=5)
        start = st.button("Start Test")
        if start:
            if not name or not email:
                st.warning("Please enter name and email before starting.")
            else:
                st.session_state.candidate = { "name": name, "email": email }
                st.session_state.qs = random.sample(questions, int(question_count))
                st.session_state.idx = 0
                st.session_state.answers = {}
                st.session_state.started = True
                st.session_state.start_time = datetime.datetime.utcnow().isoformat()
                st.session_state.duration = duration_mins
                st.experimental_rerun()
    else:
        # Timer
        start_time = datetime.datetime.fromisoformat(st.session_state.start_time)
        duration = datetime.timedelta(minutes=int(st.session_state.get('duration', 60)))
        elapsed = datetime.datetime.utcnow() - start_time
        remaining = duration - elapsed
        if remaining.total_seconds() <= 0:
            st.warning("Time is up. Submitting automatically...")
            st.session_state.submit = True

        col1, col2 = st.columns([3,1])
        with col1:
            q = st.session_state.qs[st.session_state.idx]
            st.markdown(f"**Question {st.session_state.idx + 1} of {len(st.session_state.qs)}**")
            st.write(q['text'])
            if q['type'] == 'text':
                ans = st.text_input("Your answer", value=st.session_state.answers.get(str(q['id']), ""), key=f"ans_{q['id']}")
            else:
                ans = st.text_area("Your answer", value=st.session_state.answers.get(str(q['id']), ""), height=200, key=f"ans_{q['id']}")
            st.session_state.answers[str(q['id'])] = ans

            # Navigation
            nav_col1, nav_col2, nav_col3 = st.columns(3)
            with nav_col1:
                if st.button("Previous") and st.session_state.idx > 0:
                    st.session_state.idx -= 1
                    st.experimental_rerun()
            with nav_col2:
                if st.button("Next") and st.session_state.idx < len(st.session_state.qs) - 1:
                    st.session_state.idx += 1
                    st.experimental_rerun()
            with nav_col3:
                if st.button("Submit Test"):
                    st.session_state.submit = True

        with col2:
            st.markdown("### Test Info")
            st.write(f"Candidate: {st.session_state.candidate['name']}")
            st.write(f"Email: {st.session_state.candidate['email']}")
            st.write(f"Question {st.session_state.idx + 1} / {len(st.session_state.qs)}")
            st.write(f"Time remaining: {str(remaining).split('.')[0]} (hh:mm:ss)")
            if st.checkbox("Flag this question for review", key=f"flag_{q['id']}"):
                st.write("Flagged")


        if st.session_state.get('submit', False):
            # Save responses
            submitted_at = datetime.datetime.utcnow().isoformat()
            for q in st.session_state.qs:
                qid = q['id']
                ans = st.session_state.answers.get(str(qid), "")
                c.execute('INSERT INTO responses (candidate_name, candidate_email, started_at, submitted_at, question_id, question_text, answer_text) VALUES (?,?,?,?,?,?,?)',
                          (st.session_state.candidate['name'], st.session_state.candidate['email'], st.session_state.start_time, submitted_at, qid, q['text'], ans))
            conn.commit()
            st.success("Test submitted. Thank you!")
            st.session_state.started = False
            st.session_state.submit = False
            st.experimental_rerun()

if mode == "Admin":
    pwd = st.sidebar.text_input("Admin password", type="password")
    if pwd != "admin123":
        st.warning("Enter admin password to continue.")
    else:
        st.header("Admin Dashboard")
        if st.button("Download all responses as CSV"):
            df = pd.read_sql_query('SELECT * FROM responses', conn)
            csv_file = os.path.join(APP_DIR, f"responses_{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv")
            df.to_csv(csv_file, index=False)
            st.success(f"Saved to {csv_file}")
            with open(csv_file, 'rb') as f:
                st.download_button('Download CSV', f, file_name=os.path.basename(csv_file))

        st.markdown("### Recent submissions")
        df = pd.read_sql_query('SELECT candidate_name, candidate_email, submitted_at, count(*) as q_count FROM responses GROUP BY candidate_email, submitted_at ORDER BY submitted_at DESC LIMIT 20', conn)
        st.dataframe(df)
