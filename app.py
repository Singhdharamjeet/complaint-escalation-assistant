import csv
from pathlib import Path

import pandas as pd
import streamlit as st

from escalation import EscalationWorkflow, TicketStore
from escalation import config as C
from escalation.workflow import InvalidTransition

ROOT = Path(__file__).parent
DB = ROOT / "crm.db"
SAMPLE = ROOT / "data" / "complaints.csv"
LEVEL_COLORS = {"CRITICAL": "#a50808", "HIGH": "#9e6817", "MEDIUM": "#d7e20d9a", "LOW": "#1dde1d"}

st.set_page_config(page_title="Complaint Escalation Assistant", page_icon="🚨", layout="wide")

@st.cache_resource
def get_workflow():
    return EscalationWorkflow(TicketStore(str(DB)))


wf = get_workflow()
store = wf.store

#helpers
def flash(kind, msg):
    st.session_state["flash"] = (kind, msg)


def show_flash():
    if "flash" in st.session_state:
        kind, msg = st.session_state.pop("flash")
        getattr(st, kind)(msg)


def show_result(r, ticket_id=None):
    c1, c2, c3 = st.columns(3)
    c1.metric("Risk score", r.score)
    c2.metric("Risk level", r.level)
    c3.metric("Escalate?", "YES" if r.escalate else "No")
    if r.escalate:
        st.error("ESCALATE: send to the **Senior Support** queue"
                 + (f"  |  Ticket #{ticket_id} created" if ticket_id else ""))
    else:
        st.success("No escalation needed: stays in **Standard Support**"
                   + (f"  |  Ticket #{ticket_id} created" if ticket_id else ""))
    st.markdown("**Why this score:**")
    for line in r.reasons or ["No risky words found."]:
        st.markdown(f"- {line}")


def load_tickets(view):
    q = {
        "Senior queue": "SELECT * FROM tickets WHERE queue='SENIOR_SUPPORT' AND status IN ('ESCALATED','IN_PROGRESS') "
                        "ORDER BY risk_score DESC, created_at",
        "Standard queue": "SELECT * FROM tickets WHERE queue='STANDARD_SUPPORT' AND status!='CLOSED' "
                          "ORDER BY risk_score DESC, created_at",
        "Resolved / Closed": "SELECT * FROM tickets WHERE status IN ('RESOLVED','CLOSED') ORDER BY updated_at DESC",
        "All tickets": "SELECT * FROM tickets ORDER BY risk_score DESC, created_at",
    }[view]
    return [dict(r) for r in store.conn.execute(q).fetchall()]
 
 #page

st.title("🚨 Customer Complaint Escalation Assistant")
st.caption("Complaint → Risk Analysis → Escalation Flag → Senior Queue → Status Tracking")
show_flash()

tab_new, tab_tickets = st.tabs(["📝 New Complaint", "🎫 Tickets & Queue"])

#tab1
with tab_new:
    with st.form("complaint_form"):
        c1, c2, c3, c4 = st.columns(4)
        customer_id = c1.text_input("Customer ID")
        customer_name = c2.text_input("Customer name")
        tier = c3.selectbox("Tier", ["standard", "silver", "gold", "vip"])
        prior = c4.number_input("Earlier contacts", min_value=0, max_value=50, value=0, step=1)
        text = st.text_area("Complaint text", height=150, placeholder="Type or paste the customer's complaint here...")
        b1, b2, _ = st.columns([1, 1, 4])
        do_preview = b1.form_submit_button("Check risk (preview)")
        do_submit = b2.form_submit_button("Submit & create ticket", type="primary")

    if do_preview or do_submit:
        if not text.strip():
            st.warning("Please type the complaint first.")
        elif do_preview:
            st.session_state["result"] = (wf.analyzer.analyze(text, int(prior), tier), None)
        else:
            tid, r = wf.submit_complaint(customer_id.strip() or "UNKNOWN", text, customer_name=customer_name.strip(),
                                         tier=tier, prior_contacts=int(prior))
            st.session_state["result"] = (r, tid)

    if "result" in st.session_state:
        st.divider()
        show_result(*st.session_state["result"])

    st.divider()
    if st.button("Load the 28 sample complaints"):
        with open(SAMPLE, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                wf.submit_complaint(row["customer_id"], row["complaint_text"], tier=row["tier"],
                                    prior_contacts=int(row["prior_contacts"]))
        flash("success", "28 sample complaints added. Open the Tickets & Queue tab.")
        st.rerun()

#tab2
with tab_tickets:
    total = store.conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]
    senior = len(wf.senior_queue())
    crit = store.conn.execute("SELECT COUNT(*) FROM tickets WHERE risk_level='CRITICAL' "
                              "AND status NOT IN ('RESOLVED','CLOSED')").fetchone()[0]
    done = store.conn.execute("SELECT COUNT(*) FROM tickets WHERE status IN ('RESOLVED','CLOSED')").fetchone()[0]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total tickets", total); m2.metric("In senior queue", senior)
    m3.metric("Critical (active)", crit); m4.metric("Resolved / closed", done)

    view = st.selectbox("Show", ["Senior queue", "Standard queue", "Resolved / Closed", "All tickets"])
    rows = load_tickets(view)

    if not rows:
        st.info("No tickets here yet. Submit a complaint or load the sample complaints.")
    else:
        df = pd.DataFrame(rows)[["ticket_id", "customer_id", "risk_level", "risk_score", "primary_category",
                                 "status", "queue", "sla_due_at"]]
        df.columns = ["ID", "Customer", "Risk", "Score", "Category", "Status", "Queue", "Reply due (UTC)"]
        df["Reply due (UTC)"] = df["Reply due (UTC)"].fillna("-").str.replace("T", " ").str.slice(0, 19)
        styled = df.style.apply(lambda col: [f"background-color: {LEVEL_COLORS.get(v, '')}" for v in col], subset=["Risk"])
        try:
            st.dataframe(styled, hide_index=True, width="stretch")
        except TypeError:
            st.dataframe(styled, hide_index=True, use_container_width=True)

        st.subheader("Ticket details")
        ids = [r["ticket_id"] for r in rows]
        tid = st.selectbox("Choose a ticket", ids, format_func=lambda i: next(
            f"#{r['ticket_id']}  |  {r['risk_level']}  |  {r['complaint_text'][:60]}" for r in rows if r["ticket_id"] == i))
        t = dict(store.get(tid))

        left, right = st.columns(2)
        with left:
            st.markdown(f"**Ticket #{tid}**  |  {t['customer_name'] or t['customer_id']}  |  tier: {t['tier']}")
            st.markdown(f"**Status:** {t['status']}  |  **Queue:** {t['queue']}  |  **Assigned to:** {t['assigned_to'] or 'nobody yet'}")
            st.info(t["complaint_text"])
            st.markdown("**Why this score:**")
            for line in (t["escalation_reason"] or "No risky words found.").split("; "):
                st.markdown(f"- {line}")
        with right:
            st.markdown("**Status history**")
            for h in store.history(tid):
                st.markdown(f"`{h['changed_at'].replace('T', ' ')[:19]}`  **{h['old_status'] or 'NEW'} → {h['new_status']}**"
                            f"  ({h['actor']})  \n{h['note'] or ''}")

        st.markdown("#### Actions")
        a1, a2 = st.columns(2)
        with a1, st.form(f"assign_{tid}"):
            agent = st.text_input("Assign to agent")
            if st.form_submit_button("Assign"):
                if not agent.strip():
                    st.warning("Enter an agent name.")
                else:
                    try:
                        wf.assign(tid, agent.strip())
                        flash("success", f"Ticket #{tid} assigned to {agent.strip()}.")
                        st.rerun()
                    except (InvalidTransition, KeyError, ValueError) as e:
                        st.error(str(e))
        with a2:
            allowed = sorted(C.TRANSITIONS[t["status"]])
            if not allowed:
                st.info("This ticket is CLOSED. No further changes are possible.")
            else:
                with st.form(f"status_{tid}"):
                    new_status = st.selectbox("Change status to", allowed)
                    note = st.text_input("Note (optional)")
                    if st.form_submit_button("Update status"):
                        try:
                            wf.update_status(tid, new_status, note)
                            flash("success", f"Ticket #{tid} is now {new_status}.")
                            st.rerun()
                        except (InvalidTransition, KeyError, ValueError) as e:
                            st.error(str(e))     