import streamlit as st
import pandas as pd
import sqlite3
import os
import tempfile
from pyvis.network import Network
import streamlit.components.v1 as components
from groq import Groq

# ---------------- 1. CONFIG ----------------
st.set_page_config(layout="wide", page_title="O2C Intelligence Graph")
st.markdown("<style>.stApp { background-color: #0b0e14; } iframe { border: none; }</style>", unsafe_allow_html=True)

if "GROQ_API_KEY" in st.secrets:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
else:
    st.error("Missing GROQ_API_KEY")
    st.stop()

DB_PATH = "sales.db"

def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def get_full_schema_context():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [t[0] for t in cursor.fetchall()]
    schema_info = []
    for table in tables:
        cursor.execute(f"PRAGMA table_info({table});")
        cols = [f"{c[1]}" for c in cursor.fetchall()]
        schema_info.append(f"Table {table}: {', '.join(cols)}")
    conn.close()
    return "\n".join(schema_info)

# ---------------- 2. THE GRAPH (Now with correct columns) ----------------
def render_interactive_graph(search_id=None, sample_size=50):
    conn = get_connection()
    net = Network(height="700px", width="100%", bgcolor="#0b0e14", font_color="white", notebook=False)
    net.force_atlas_2based(gravity=-50, central_gravity=0.01, spring_length=100, spring_strength=0.08)
    
    try:
        if search_id and search_id.strip() != "":
            # TRACE MODE
            query = f"""
            SELECT s.salesOrder, d.deliveryDocument, b.billingDocument, s.material
            FROM sales_order_items s
            LEFT JOIN outbound_delivery_items d ON s.salesOrder = d.referenceSdDocument
            LEFT JOIN billing_document_items b ON d.deliveryDocument = b.referenceSdDocument
            WHERE s.salesOrder='{search_id}' OR d.deliveryDocument='{search_id}' OR b.billingDocument='{search_id}'
            """
            df = pd.read_sql_query(query, conn)
            for _, row in df.iterrows():
                so, deli, bill = str(row['salesOrder']), str(row['deliveryDocument']), str(row['billingDocument'])
                if so != "None": net.add_node(so, label=f"Order {so}", color="#2ecc71", title=f"SO: {so}")
                if deli != "None": 
                    net.add_node(deli, label=f"Deliv {deli}", color="#3498db", title=f"Delivery: {deli}")
                    if so != "None": net.add_edge(so, deli, color="#575757")
                if bill != "None":
                    net.add_node(bill, label=f"Inv {bill}", color="#f1c40f", title=f"Invoice: {bill}")
                    if deli != "None": net.add_edge(deli, bill, color="#575757")
        else:
            # EXPLORATION MODE - Fixed Join Column Names
            query = f"""
            SELECT s.salesOrder, s.material, p.productDescription 
            FROM sales_order_items s 
            LEFT JOIN product_descriptions p ON s.material = p.product 
            LIMIT {sample_size}
            """
            df = pd.read_sql_query(query, conn)
            for _, row in df.iterrows():
                desc = row['productDescription'] if row['productDescription'] else "No Description"
                net.add_node(str(row['salesOrder']), label=f"SO {row['salesOrder']}", color="#2ecc71")
                net.add_node(str(row['material']), label=f"Mat {row['material']}", color="#e74c3c", title=f"Name: {desc}")
                net.add_edge(str(row['salesOrder']), str(row['material']))

        with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp:
            net.save_graph(tmp.name)
            with open(tmp.name, "r", encoding="utf-8") as f:
                components.html(f.read(), height=720)
    except Exception as e:
        st.error(f"Visualization Error: {e}")

# ---------------- 3. AI ENGINE (Requirement 5 Guardrails) ----------------
def get_ai_sql_response(user_input):
    schema_context = get_full_schema_context()
    system_prompt = f"""
    You are a strictly SAP O2C Data Assistant.
    SCHEMA: {schema_context}
    
    1. GUARDRAIL: If query is NOT about the dataset (jokes, poems, general knowledge), respond: "This system is designed to answer questions related to the provided dataset only."
    2. MAPPING: Use 'productDescription' from 'product_descriptions' for names. Use 'netAmount' for revenue.
    3. Return ONLY raw SQL. No markdown.
    """
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_input}]
    )
    return response.choices[0].message.content.strip()

# ---------------- 4. UI ----------------
with st.sidebar:
    st.title("💬 Data Assistant")
    density = st.slider("Graph Density", 10, 200, 50)
    trace_id = st.text_input("🔍 Trace Specific ID", placeholder="e.g. 80001234")
    
    if "messages" not in st.session_state: st.session_state.messages = []
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            if isinstance(m["content"], pd.DataFrame): st.dataframe(m["content"], use_container_width=True)
            else: st.markdown(m["content"])

    if prompt := st.chat_input("Ask a question..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        ai_output = get_ai_sql_response(prompt)
        
        if "designed to answer questions" in ai_output:
            st.session_state.messages.append({"role": "assistant", "content": ai_output})
        else:
            try:
                res_df = pd.read_sql_query(ai_output, get_connection())
                st.session_state.messages.append({"role": "assistant", "content": res_df})
            except:
                st.session_state.messages.append({"role": "assistant", "content": "I couldn't find that data. Try rephrasing."})
        st.rerun()

st.subheader("🔗 Order-to-Cash Knowledge Map")
render_interactive_graph(trace_id, density)