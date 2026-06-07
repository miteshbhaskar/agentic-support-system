"""
app.py - FlowDesk Support Agent UI (Streamlit)
Run: streamlit run app.py
Requires API server running on localhost:8001
"""

import streamlit as st
import httpx
import json
from pathlib import Path

API_URL = "http://localhost:8001/support/query"

st.set_page_config(
    page_title="FlowDesk Support Agent",
    page_icon="⬡",
    layout="wide",
)

# ── Load example queries ──────────────────────────────────────────
@st.cache_data
def load_examples():
    try:
        return json.loads(Path("sample-requests/example-queries.json").read_text())
    except:
        return []

examples = load_examples()

# ── Styling ───────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stAppViewContainer"]{background:#0a0e17}
[data-testid="stSidebar"]{background:#111827;border-right:1px solid #1e2d45}
.stTextInput input,.stTextArea textarea,.stSelectbox select{background:#1a2234!important;color:#e2e8f0!important;border:1px solid #1e2d45!important}
h1,h2,h3{color:#e2e8f0!important}
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────
st.markdown("## ⬡ FlowDesk Support Agent")
st.markdown("---")

col_input, col_output = st.columns([1, 1.6])

# ══════════════════════════════════════════════════════════════════
# LEFT COLUMN — Input
# ══════════════════════════════════════════════════════════════════
with col_input:
    st.markdown("### Query Input")

    # Example query dropdown
    example_labels = ["— select a test case —"] + [
        f"[{q['difficulty'].upper()}] {q['id']} · {q['customer_id']}"
        for q in examples
    ]
    selected_idx = st.selectbox("Load Example Query", range(len(example_labels)), format_func=lambda i: example_labels[i])

    # Auto-fill from example
    default_cid = ""
    default_query = ""
    if selected_idx > 0:
        ex = examples[selected_idx - 1]
        default_cid = ex["customer_id"]
        default_query = ex["query"]

        with st.expander("📋 Test Case Details", expanded=True):
            st.markdown(f"**ID:** `{ex['id']}`")
            st.markdown(f"**Difficulty:** `{ex['difficulty'].upper()}`")
            esc_color = "🟡" if ex["expected_escalation"] else "🟢"
            st.markdown(f"**Expected Escalation:** {esc_color} {'Yes' if ex['expected_escalation'] else 'No'}")
            st.markdown(f"**Workflow:** {ex['expected_workflow']}")

    st.markdown("---")

    customer_id = st.text_input("Customer ID", value=default_cid, placeholder="e.g. cust_1001")
    query = st.text_area("Query", value=default_query, placeholder="Describe the customer's issue...", height=120)

    run = st.button("▶ Run Agent", use_container_width=True, type="primary")

# ══════════════════════════════════════════════════════════════════
# RIGHT COLUMN — Output
# ══════════════════════════════════════════════════════════════════
with col_output:
    st.markdown("### Agent Response")

    if not run:
        st.info("Submit a query to see the agent's resolution.")
    else:
        if not customer_id or not query:
            st.error("Please enter both Customer ID and Query.")
        else:
            with st.spinner("Agent processing your query..."):
                try:
                    response = httpx.post(
                        API_URL,
                        json={"customer_id": customer_id, "query": query},
                        timeout=120.0,
                    )
                    data = response.json()
                except httpx.TimeoutException:
                    st.error("⏱ Request timed out. Try again.")
                    st.stop()
                except Exception as e:
                    st.error(f"Connection failed: {e}")
                    st.stop()

            if "error" in data:
                st.error(f"Agent error: {data['error']}")
                st.stop()

            # ── Status ────────────────────────────────────────────
            status = data.get("status", "unknown")
            confidence = data.get("confidence", 0)
            escalated = data.get("escalation_required", False)
            ticket_id = data.get("ticket_id")

            status_map = {
                "resolved": ("✅", "Resolved", "normal"),
                "escalated": ("⚠️", "Escalated", "warning"),
                "rejected": ("🚫", "Rejected", "error"),
            }
            icon, label, stype = status_map.get(status, ("❓", status, "normal"))

            c1, c2, c3 = st.columns(3)
            c1.metric("Status", f"{icon} {label}")
            c2.metric("Confidence", f"{round(confidence * 100)}%")
            c3.metric("Ticket", ticket_id or "—")

            st.markdown("---")

            # ── Answer ────────────────────────────────────────────
            st.markdown("#### 💬 Answer")
            st.markdown(
                f'<div style="background:#1a2234;border:1px solid #1e2d45;border-radius:8px;padding:1rem;font-size:.9rem;line-height:1.75;color:#e2e8f0;white-space:pre-wrap">{data.get("answer","")}</div>',
                unsafe_allow_html=True,
            )

            # ── Escalation reason ─────────────────────────────────
            if escalated and data.get("escalation_reason"):
                st.warning(f"**Escalation Reason:** {data['escalation_reason']}")

            # ── Execution trace ───────────────────────────────────
            trace = data.get("execution_trace", [])
            if trace:
                with st.expander(f"▸ Execution Trace ({len(trace)} steps)", expanded=True):
                    icons = {
                        "security": "🛡️", "guard": "🛡️", "threat": "🛡️",
                        "intent": "🔍", "classif": "🔍",
                        "customer": "👤", "fetched customer": "👤",
                        "plan": "📋", "incident": "⚠️",
                        "diagnost": "🔧", "knowledge": "📚",
                        "searching": "📚", "retrieved": "📚",
                        "decision": "⚖️", "evaluat": "⚖️",
                        "ticket": "🎫", "generat": "✍️", "reject": "🚫",
                    }
                    for i, step in enumerate(trace, 1):
                        step_icon = next(
                            (v for k, v in icons.items() if k in step.lower()), "▸"
                        )
                        st.markdown(
                            f'<div style="font-family:monospace;font-size:.8rem;color:#94a3b8;padding:.3rem .5rem;border-radius:5px">'
                            f'<span style="color:#64748b">{str(i).zfill(2)}</span> {step_icon} {step}</div>',
                            unsafe_allow_html=True,
                        )

            # ── Tools used ────────────────────────────────────────
            tools = data.get("tools_used", [])
            if tools:
                with st.expander(f"⚙ Tools Used ({len(tools)} calls)"):
                    for t in tools:
                        ok = t["status"] == "success"
                        dot = "🟢" if ok else "🔴"
                        cites = f" · {len(t['citations'])} citations" if t.get("citations") else ""
                        st.markdown(
                            f'<div style="font-family:monospace;font-size:.8rem;background:#1a2234;border:1px solid #1e2d45;border-radius:6px;padding:.5rem .75rem;margin-bottom:.35rem;color:#e2e8f0">'
                            f'{dot} <b>{t["tool"]}</b><span style="color:#64748b"> · {t["latency_ms"]}ms{cites}</span></div>',
                            unsafe_allow_html=True,
                        )

            # ── Citations ─────────────────────────────────────────
            citations = data.get("citations", [])
            if citations:
                with st.expander(f"📄 Citations ({len(citations)})"):
                    for c in citations:
                        rel = round((c.get("relevance", 0)) * 100)
                        st.markdown(
                            f'<div style="background:#1a2234;border:1px solid #1e2d45;border-left:3px solid #7c3aed;border-radius:0 6px 6px 0;padding:.6rem .8rem;margin-bottom:.35rem">'
                            f'<span style="font-family:monospace;font-size:.78rem;color:#00d4ff">{c["source"]}</span>'
                            f'<span style="font-size:.75rem;color:#94a3b8"> · {c["section"]}</span>'
                            f'<span style="font-family:monospace;font-size:.7rem;color:#64748b;float:right">{rel}% match</span></div>',
                            unsafe_allow_html=True,
                        )
