import streamlit as st
import pandas as pd
import sqlite3
import os
import json
from pyvis.network import Network
import streamlit.components.v1 as components
from groq import Groq

# ---------------- 1. CONFIG & SETUP ----------------
st.set_page_config(layout="wide", page_title="SAP O2C Intelligence Hub", page_icon="📊")

# Simplified CSS for Python 3.14 compatibility
st.markdown("<style>.stMetric { background-color: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d; }</style>", unsafe_allow_html=True)

# API INIT
if "GROQ_API_KEY" in st.secrets:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
else:
    st.error("Please add GROQ_API_KEY to Streamlit Secrets.")
    st.stop()

DB_PATH = "sales.db"

# ---------------- AUTO-BUILD DB FOR CLOUD ----------------
if not os.path.exists(DB_PATH):
    # Check if data folder exists before trying to ingest
    if os.path.exists("data"):
        from load_data import ingest_all_data
        with st.spinner("📦 Initializing Global Knowledge Graph..."):
            ingest_all_data()
    else:
        st.error("Data folder not found on server. Please push the 'data' folder to GitHub.")
        st.stop()
# ---------------- 2. API & DB INIT ----------------
if "GROQ_API_KEY" in st.secrets:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
else:
    st.error("Missing GROQ_API_KEY in .streamlit/secrets.toml")
    st.stop()

DB_PATH = "sales.db"

# Auto-build database for Streamlit Cloud if missing
if not os.path.exists(DB_PATH):
    from load_data import ingest_all_data
    with st.spinner("⚙️ Cloud Setup: Ingesting your JSONL datasets... Please wait."):
        ingest_all_data()

def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def get_db_schema():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [t[0] for t in cursor.fetchall()]
    
    schema_desc = []
    for table in tables:
        cursor.execute(f"PRAGMA table_info({table});")
        columns = [col[1] for col in cursor.fetchall()]
        schema_desc.append(f"Table '{table}' | Columns: {', '.join(columns)}")
    conn.close()
    return "\n".join(schema_desc)

# ---------------- 3. FEATURE: REAL-TIME O2C KPIs ----------------
def render_kpis():
    conn = get_connection()
    try:
        orders_df = pd.read_sql_query("SELECT COUNT(*) as cnt FROM sales_order_headers", conn)
        billing_df = pd.read_sql_query("SELECT SUM(netAmount) as rev FROM billing_document_items", conn)
        delivered_df = pd.read_sql_query("SELECT COUNT(DISTINCT deliveryDocument) as cnt FROM outbound_delivery_headers", conn)
        
        total_orders = orders_df['cnt'][0] if not orders_df.empty else 0
        total_rev = billing_df['rev'][0] if not billing_df.empty else 0.0
        total_deliv = delivered_df['cnt'][0] if not delivered_df.empty else 0

        colA, colB, colC = st.columns(3)
        with colA:
            st.markdown(f'<div class="metric-card"><h4>📦 Total Orders</h4><h2>{total_orders}</h2></div>', unsafe_allow_value=True)
        with colB:
            st.markdown(f'<div class="metric-card"><h4>💰 Total Revenue</h4><h2>₹{total_rev:,.2f}</h2></div>', unsafe_allow_value=True)
        with colC:
            st.markdown(f'<div class="metric-card"><h4>🚚 Total Deliveries</h4><h2>{total_deliv}</h2></div>', unsafe_allow_value=True)
    except:
        st.warning("📊 Loading KPIs... (Waiting for DB schema verification)")

# ---------------- 4. GRAPH VISUALIZATION ----------------
def build_o2c_graph(search_id=None):
    conn = get_connection()
    net = Network(height="500px", width="100%", bgcolor="#0e1117", font_color="white")
    net.force_atlas_2based()

    try:
        if search_id:
            query = f"""
            SELECT s.salesOrder as SO, d.deliveryDocument as DEL, b.billingDocument as BILL
            FROM sales_order_items s
            LEFT JOIN outbound_delivery_items d ON s.salesOrder = d.referenceSdDocument
            LEFT JOIN billing_document_items b ON d.deliveryDocument = b.referenceSdDocument
            WHERE s.salesOrder = '{search_id}' OR d.deliveryDocument = '{search_id}' OR b.billingDocument = '{search_id}'
            LIMIT 30
            """
            df = pd.read_sql_query(query, conn)
            
            if df.empty:
                st.warning(f"No records found for ID: {search_id}")
                return

            for _, row in df.iterrows():
                so, deli, bill = str(row['SO']), str(row['DEL']), str(row['BILL'])
                if so != "None":
                    net.add_node(so, label=f"Order {so}", color="#2ecc71", title=f"Type: Sales Order")
                if deli != "None":
                    net.add_node(deli, label=f"Deliv {deli}", color="#3498db", title=f"Type: Delivery")
                    if so != "None": net.add_edge(so, deli)
                if bill != "None":
                    net.add_node(bill, label=f"Bill {bill}", color="#f1c40f", title=f"Type: Billing")
                    if deli != "None": net.add_edge(deli, bill)
        else:
            df = pd.read_sql_query("SELECT salesOrder, material FROM sales_order_items LIMIT 20", conn)
            for _, row in df.iterrows():
                net.add_node(str(row['salesOrder']), label=f"SO: {row['salesOrder']}", color="#2ecc71")
                net.add_node(str(row['material']), label=f"MAT: {row['material']}", color="#e74c3c")
                net.add_edge(str(row['salesOrder']), str(row['material']))

        net.save_graph("graph.html")
        with open("graph.html", "r", encoding="utf-8") as f:
            components.html(f.read(), height=550)
    except Exception as e:
        st.error(f"Graph Error: {e}")

# ---------------- 5. HIDDEN SQL & ANSWER GENERATION ----------------
def get_clean_answer(user_input):
    schema_context = get_db_schema()
    
    # Strictly instruct AI to write standard SQL and explain it conversationally
    system_prompt = f"""
    You are an SAP Order-to-Cash Database Expert.
    
    SCHEMA:
    {schema_context}
    
    RULES:
    1. Translate the user query into SQLite. 
    2. Write the query inside ```sql blocks.
    3. After the SQL, write a conversational human answer summing up the results.
    4. For non-dataset queries, do not output SQL. Reply exactly: "This system is designed to answer questions related to the provided dataset only."
    """
    
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ]
    )
    ai_raw = response.choices[0].message.content

    if "This system is designed" in ai_raw:
        return ai_raw

    # Extract SQL and execute it behind the scenes
    if "```sql" in ai_raw:
        try:
            sql_query = ai_raw.split("```sql")[1].split("```")[0].strip()
            df = pd.read_sql_query(sql_query, get_connection())
            
            # Second AI pass to turn the table into a friendly sentence
            human_prompt = f"""
            User Question: {user_input}
            Data Table Results: {df.head(5).to_string()}
            
            Based on this table, give a friendly, direct answer. 
            Do NOT mention the SQL query, column names, or coding terms. 
            Just state the facts. Use bullet points if listing multiple items.
            """
            
            human_response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": human_prompt}]
            )
            return human_response.choices[0].message.content
        except Exception as e:
            return f"I ran into an issue querying the dataset: {e}"
    
    return ai_raw

# ---------------- 6. UI LAYOUT ----------------
st.title("🧠 SAP Order-to-Cash Analytics Hub")

# 📊 Top Section: KPIs
render_kpis()

col_left, col_right = st.columns([1.2, 1])

with col_left:
    st.subheader("🔗 Network Node Visualization")
    search_id = st.text_input("Trace an Order Flow (Enter Order or Delivery ID)", placeholder="Search...")
    build_o2c_graph(search_id)

with col_right:
    st.subheader("💬 Natural Language Assistant")
    
    # 🕵️ Smart Prompts / Quick Prompts
    st.write("✨ Quick Queries:")
    quick_col1, quick_col2 = st.columns(2)
    with quick_col1:
        trigger_top = st.button("🔝 Top products by billing count")
    with quick_col2:
        trigger_broken = st.button("⚠️ Find undelivered sales orders")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Print chat history
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    # Normal Chat Input
    prompt = st.chat_input("Ask about sales, deliveries, or billing data...")
    
    # Override prompt if quick buttons were pressed
    if trigger_top:
        prompt = "Which 5 products appear in the highest number of billing document items?"
    if trigger_broken:
        prompt = "Identify sales order items that do not have a corresponding outbound delivery document item."

    if prompt:
        # Show human message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Analyzing Database..."):
                clean_answer = get_clean_answer(prompt)
                st.markdown(clean_answer)
                st.session_state.messages.append({"role": "assistant", "content": clean_answer})