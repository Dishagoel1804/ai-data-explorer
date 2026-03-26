import streamlit as st
import pandas as pd
import sqlite3
import os
from pyvis.network import Network
import streamlit.components.v1 as components
from groq import Groq

# ---------------- 1. INITIAL CONFIG ----------------
st.set_page_config(layout="wide", page_title="O2C Data Explorer", page_icon="🔍")

# Clean, simple styling
st.markdown("<style>.stApp { background-color: #0e1117; } .stDataFrame { border: 1px solid #30363d; }</style>", unsafe_allow_html=True)

# API INIT
if "GROQ_API_KEY" in st.secrets:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
else:
    st.error("Missing GROQ_API_KEY in Streamlit Secrets.")
    st.stop()

DB_PATH = "sales.db"

# Auto-Build Database if missing on Cloud
if not os.path.exists(DB_PATH):
    if os.path.exists("data"):
        from load_data import ingest_all_data
        with st.spinner("Preparing dataset..."):
            ingest_all_data()
    else:
        st.error("Data folder not found. Please upload the 'data' folder to GitHub.")
        st.stop()

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
        schema_desc.append(f"Table '{table}': {', '.join(columns)}")
    conn.close()
    return "\n".join(schema_desc)

# ---------------- 2. GRAPH VISUALIZATION (SIDEBAR) ----------------
def build_o2c_graph(search_id=None):
    conn = get_connection()
    net = Network(height="400px", width="100%", bgcolor="#0e1117", font_color="white")
    net.force_atlas_2based()

    try:
        if search_id:
            query = f"""
            SELECT s.salesOrder, d.deliveryDocument, b.billingDocument
            FROM sales_order_items s
            LEFT JOIN outbound_delivery_items d ON s.salesOrder = d.referenceSdDocument
            LEFT JOIN billing_document_items b ON d.deliveryDocument = b.referenceSdDocument
            WHERE s.salesOrder='{search_id}' OR d.deliveryDocument='{search_id}' OR b.billingDocument='{search_id}'
            """
            df = pd.read_sql_query(query, conn)
            for _, row in df.iterrows():
                so, deli, bill = str(row['salesOrder']), str(row['deliveryDocument']), str(row['billingDocument'])
                if so != "None": net.add_node(so, label=f"Order {so}", color="#2ecc71")
                if deli != "None": 
                    net.add_node(deli, label=f"Deliv {deli}", color="#3498db")
                    if so != "None": net.add_edge(so, deli)
                if bill != "None":
                    net.add_node(bill, label=f"Bill {bill}", color="#f1c40f")
                    if deli != "None": net.add_edge(deli, bill)
        else:
            # Default preview
            df = pd.read_sql_query("SELECT salesOrder, material FROM sales_order_items LIMIT 10", conn)
            for _, row in df.iterrows():
                net.add_node(str(row['salesOrder']), label=f"SO {row['salesOrder']}", color="#2ecc71")
                net.add_node(str(row['material']), label=f"MAT {row['material']}", color="#e74c3c")
                net.add_edge(str(row['salesOrder']), str(row['material']))

        net.save_graph("graph.html")
        with open("graph.html", "r", encoding="utf-8") as f:
            components.html(f.read(), height=420)
    except Exception:
        pass

# ---------------- 3. CLEAN AI CORE (NO SQL DISPLAY) ----------------
def get_ai_sql(user_input):
    schema_context = get_db_schema()
    system_prompt = f"""
    You are a hidden SQL generator. 
    DATABASE SCHEMA: {schema_context}
    
    TASK: Translate user input into one valid SQLite query.
    RULES:
    - Return ONLY the raw SQL code. No markdown blocks, no '```sql', no explanations.
    - If the user asks something non-SAP related, return 'GUARDRAIL'.
    - To find 'unbilled deliveries', use a LEFT JOIN where billingDocument IS NULL.
    """
    
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_input}]
    )
    return response.choices[0].message.content.strip()

# ---------------- 4. MAIN INTERFACE ----------------
st.title("📊 SAP Process Intelligence")

# Sidebar for the Graph (Trace Feature)
with st.sidebar:
    st.header("Trace Transaction")
    search_id = st.text_input("Enter Order or Delivery ID", placeholder="e.g. 80001234")
    build_o2c_graph(search_id)
    st.write("---")
    if st.button("Clear History"):
        st.session_state.messages = []
        st.rerun()

# Main Chat Interface
if "messages" not in st.session_state:
    st.session_state.messages = []

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        if isinstance(m["content"], pd.DataFrame):
            st.dataframe(m["content"], use_container_width=True)
        else:
            st.markdown(m["content"])

if prompt := st.chat_input("What would you like to know about the O2C data?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        raw_sql = get_ai_sql(prompt)
        
        if "GUARDRAIL" in raw_sql:
            msg = "This system is designed to answer questions related to the provided dataset only."
            st.markdown(msg)
            st.session_state.messages.append({"role": "assistant", "content": msg})
        else:
            try:
                # Execute the hidden SQL
                df = pd.read_sql_query(raw_sql, get_connection())
                
                if not df.empty:
                    st.dataframe(df, use_container_width=True)
                    st.session_state.messages.append({"role": "assistant", "content": df})
                    # Download option
                    st.download_button("📥 Export CSV", df.to_csv(index=False), "data.csv", "text/csv")
                else:
                    msg = "No results found for your query."
                    st.info(msg)
                    st.session_state.messages.append({"role": "assistant", "content": msg})
            except Exception:
                msg = "I'm sorry, I couldn't process that data request. Please try rephrasing."
                st.error(msg)
                st.session_state.messages.append({"role": "assistant", "content": msg})