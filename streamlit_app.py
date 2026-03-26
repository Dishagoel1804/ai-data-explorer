import streamlit as st
import pandas as pd
import sqlite3
import os
import tempfile
from pyvis.network import Network
import streamlit.components.v1 as components
from groq import Groq

# 1. SETUP
st.set_page_config(layout="wide", page_title="O2C Intelligence")
st.markdown("<style>.stApp { background-color: #0b0e14; }</style>", unsafe_allow_html=True)

client = Groq(api_key=st.secrets["GROQ_API_KEY"])
DB_PATH = "sales.db"

def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def get_schema_for_ai():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [t[0] for t in cursor.fetchall()]
    schema_text = ""
    for table in tables:
        cursor.execute(f"PRAGMA table_info({table});")
        cols = [f"{c[1]}" for c in cursor.fetchall()]
        schema_text += f"Table {table}: {', '.join(cols)}\n"
    conn.close()
    return schema_text

# 2. CHATBOT (NLP Logic)
def ask_ai(user_query):
    schema = get_schema_for_ai()
    system_message = f"""
    You are an expert SAP Data Scientist. 
    SCHEMA: {schema}
    
    RELATIONSHIPS:
    - sales_order_items.salesOrder -> outbound_delivery_items.referenceSdDocument
    - outbound_delivery_items.deliveryDocument -> billing_document_items.referenceSdDocument
    
    GUARDRAIL: If query unrelated to SAP/O2C, respond: "This system is designed to answer questions related to the provided dataset only."
    
    IMPORTANT: Use ONLY column names found in the SCHEMA above. Output ONLY raw SQL.
    """
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "system", "content": system_message}, {"role": "user", "content": user_query}]
        )
        return response.choices[0].message.content.strip().replace("```sql", "").replace("```", "")
    except: return "Error"

# 3. GRAPH (Visualization Logic - Fixed Columns)
def draw_graph(search_id=None):
    conn = get_connection()
    net = Network(height="700px", width="100%", bgcolor="#0b0e14", font_color="white")
    net.force_atlas_2based(gravity=-50, central_gravity=0.01, spring_length=100)
    
    try:
        if search_id and search_id.strip() != "":
            # TRACE MODE
            query = f"""
            SELECT s.salesOrder, s.material, s.netAmount, d.deliveryDocument, b.billingDocument 
            FROM sales_order_items s 
            LEFT JOIN outbound_delivery_items d ON s.salesOrder = d.referenceSdDocument 
            LEFT JOIN billing_document_items b ON d.deliveryDocument = b.referenceSdDocument 
            WHERE s.salesOrder='{search_id}' OR d.deliveryDocument='{search_id}' OR b.billingDocument='{search_id}'
            """
            df = pd.read_sql_query(query, conn)
            for _, r in df.iterrows():
                so = str(r['salesOrder'])
                # Green Node
                net.add_node(so, label=f"Order {so}", color="#2ecc71", title=f"Value: {r['netAmount']}", size=25)
                if r['deliveryDocument']:
                    de = str(r['deliveryDocument'])
                    # Blue Node
                    net.add_node(de, label=f"Del {de}", color="#3498db", title=f"Delivery: {de}", size=20)
                    net.add_edge(so, de, color="#575757")
                    if r['billingDocument']:
                        bi = str(r['billingDocument'])
                        # Yellow Node
                        net.add_node(bi, label=f"Inv {bi}", color="#f1c40f", title=f"Invoice: {bi}", size=20)
                        net.add_edge(de, bi, color="#575757")
        else:
            # EXPLORATION MODE - Safe Columns only
            query = "SELECT salesOrder, material, netAmount FROM sales_order_items LIMIT 40"
            df = pd.read_sql_query(query, conn)
            for _, r in df.iterrows():
                net.add_node(str(r['salesOrder']), label=f"SO {r['salesOrder']}", color="#2ecc71", title=f"Value: {r['netAmount']}")
                net.add_node(str(r['material']), label=f"Mat {r['material']}", color="#e74c3c", title=f"Material ID: {r['material']}")
                net.add_edge(str(r['salesOrder']), str(r['material']))

        with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp:
            net.save_graph(tmp.name)
            with open(tmp.name, 'r', encoding='utf-8') as f:
                components.html(f.read(), height=720)
    except Exception as e:
        st.error(f"Graph Error: {e}")

# 4. UI LAYOUT
with st.sidebar:
    st.title("💬 Assistant")
    if "history" not in st.session_state: st.session_state.history = []
    user_input = st.chat_input("Ask a question...")
    if user_input:
        st.session_state.history.append({"role": "user", "content": user_input})
        sql_or_msg = ask_ai(user_input)
        if "designed to answer" in sql_or_msg:
            st.session_state.history.append({"role": "assistant", "content": sql_or_msg})
        else:
            try:
                res = pd.read_sql_query(sql_or_msg, get_connection())
                st.session_state.history.append({"role": "assistant", "content": res})
            except:
                st.session_state.history.append({"role": "assistant", "content": "I understood but the database column names didn't match. Try rephrasing."})
        st.rerun()
    for m in st.session_state.history:
        with st.chat_message(m["role"]):
            if isinstance(m["content"], pd.DataFrame): st.dataframe(m["content"])
            else: st.markdown(m["content"])

st.title("🔗 O2C Knowledge Map")
search = st.text_input("🔍 Trace Transaction ID")
draw_graph(search)