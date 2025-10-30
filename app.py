import streamlit as st, json, random, sqlite3, os, datetime, pandas as pd, requests, time

st.set_page_config(page_title="🧠 DataProctor Pro – Azure Data Engineer Assessment", layout="wide")

APP_DIR = os.path.dirname(os.path.abspath(__file__))
QUESTIONS_FILE = os.path.join(APP_DIR, "questions_90.json")
DB_FILE = os.path.join(APP_DIR, "responses.db")
#WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbwYBR-ilPyQotp_aP-eittB4OVhGkafi-qEfs1JMpWcpjQdEuUFn6S2qA1qq57gadQilA/exec"
WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbw_ICFeCjBqVFlHzi7Taq_t85st13KfPVjCa6azWL3y0LbTY382UIpwrS7oetojPojYrg/exec"
# ---- Load or init questions ----
if not os.path.exists(QUESTIONS_FILE):
    json.dump([], open(QUESTIONS_FILE,"w"))

with open(QUESTIONS_FILE) as f: questions = json.load(f)

# ---- Init DB ----
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS responses(
id INTEGER PRIMARY KEY AUTOINCREMENT,
candidate_name TEXT,candidate_email TEXT,submitted_at TEXT,
question_id INT,question_text TEXT,answer_text TEXT)''')
conn.commit()

# ---- Mode ----
mode = st.sidebar.selectbox("Mode", ["Candidate","Admin"])

# ============ Candidate ============
if mode=="Candidate":
    if "started" not in st.session_state: st.session_state.started=False
    if not st.session_state.started:
        name=st.text_input("Name"); email=st.text_input("Email")
        num_q=min(len(questions),st.number_input("Questions",1,50,5))
        start=st.button("🚀 Start Test")
        if start and name and email:
            st.session_state.started=True
            st.session_state.name=name; st.session_state.email=email
            st.session_state.qs=random.sample(questions,int(num_q))
            st.session_state.idx=0; st.session_state.answers={}
            st.session_state.start=datetime.datetime.utcnow().isoformat()
            st.session_state.duration=30
            st.rerun()
    else:
        start_time=datetime.datetime.fromisoformat(st.session_state.start)
        remain=datetime.timedelta(minutes=st.session_state.duration)-(datetime.datetime.utcnow()-start_time)
        if remain.total_seconds()<=0: st.session_state.submit=True
        h,rem=divmod(int(remain.total_seconds()),3600); m,s=divmod(rem,60)
        st.info(f"⏱ {h:02}:{m:02}:{s:02} left")

        q=st.session_state.qs[st.session_state.idx]
        st.subheader(f"Q{st.session_state.idx+1}: {q.get('text')}")
        typ=q.get("type","text")
        if typ=="mcq": ans=st.radio("Select:",q.get("options",[]),key=f"a{q['id']}")
        else: ans=st.text_area("Answer:",st.session_state.answers.get(str(q['id']),""),key=f"a{q['id']}")
        st.session_state.answers[str(q['id'])]=ans

        c1,c2,c3=st.columns(3)
        if c1.button("⬅️ Prev") and st.session_state.idx>0: st.session_state.idx-=1; st.rerun()
        if c2.button("➡️ Next") and st.session_state.idx<len(st.session_state.qs)-1: st.session_state.idx+=1; st.rerun()
        if c3.button("✅ Submit"): st.session_state.submit=True

        if st.session_state.get("submit",False):
            sub=datetime.datetime.utcnow().isoformat()
            for q in st.session_state.qs:
                ans=st.session_state.answers.get(str(q['id']),"")
                c.execute("INSERT INTO responses(candidate_name,candidate_email,submitted_at,question_id,question_text,answer_text) VALUES (?,?,?,?,?,?)",
                    (st.session_state.name,st.session_state.email,sub,q["id"],q["text"],ans))
                try: requests.post(WEBHOOK_URL,json={"name":st.session_state.name,"email":st.session_state.email,"question_id":q["id"],"question_text":q["text"],"answer":ans})
                except: pass
            conn.commit()
            st.success("✅ Submitted successfully and synced to Google Sheet.")
            st.balloons(); st.session_state.clear()

# ============ Admin ============
if mode=="Admin":
    if st.sidebar.text_input("Password",type="password")!="admin123":
        st.warning("Enter admin123"); st.stop()
    st.header("🧩 Admin Dashboard")

    with st.expander("➕ Add Question"):
        with st.form("addq",clear_on_submit=True):
            t=st.text_area("Question text"); typ=st.selectbox("Type",["text","mcq","code"])
            opts=[]; correct=""
            if typ=="mcq":
                opts=st.text_area("Options (comma separated)").split(",")
                correct=st.text_input("Correct answer")
            cat=st.text_input("Category","General")
            if st.form_submit_button("Add") and t:
                qid=max([q["id"] for q in questions],default=0)+1
                q={"id":qid,"text":t,"type":typ,"category":cat}
                if typ=="mcq": q["options"]=opts; q["answer"]=correct
                questions.append(q); json.dump(questions,open(QUESTIONS_FILE,"w"),indent=2)
                st.success(f"Added Q{qid}")

    st.subheader("Questions"); st.dataframe(pd.DataFrame(questions))
    st.subheader("Responses"); df=pd.read_sql_query("select * from responses order by id desc",conn)
    st.dataframe(df)
    csv=df.to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV",csv,"responses.csv","text/csv")
