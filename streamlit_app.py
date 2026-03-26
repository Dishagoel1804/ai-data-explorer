import streamlit as st
import pandas as pd
import sqlite3
import os
import tempfile
from pyvis.network import Network
import streamlit.components.v1 as components
from groq import Groq

# 1. SETUP & THEME
st.set_page_config(layout="wide", page_title="O2C Intelligence")
st.markdown("<style>.stApp { background-color: #0b0e14; } .stTextInput > div > div > input { color: white; }</style>", unsafe_allow_html=True)

client = Groq(api_key=st.secrets["GROQ_API_KEY"])
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

# 2. THE WORKING CHATBOT (Requirement 5 + O2C Logic)
def get_ai_sql_response(user_input):
    schema_context = get_full_schema_context()
    
    system_prompt = f"""
    You are an expert SAP O2C Data Analyst.
    SCHEMA: {schema_context}
    
    RELATIONSHIPS:
    - sales_order_items.salesOrder -> outbound_delivery_items.referenceSdDocument
    - outbound_delivery_items.deliveryDocument -> billing_document_items.referenceSdDocument
    
    RULES:
    1. GUARDRAIL: If query is NOT about the dataset (jokes, general knowledge), respond: "This system is designed to answer questions related to the provided dataset only."
    2. MAPPING: Use 'productDescription' for product names. Use 'netAmount' for revenue.
    3. Output ONLY raw SQL. No markdown.
    """
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_input}]
        )
        return response.choices[0].message.content.strip().replace("```sql", "").replace("```", "")
    except:
        return "ERROR: Connection issue."

# 3. THE WORKING GRAPH (Color-Coded + Rich Hover)
def draw_graph(search_id=None, limit=50):
    conn = get_connection()
    net = Network(height="700px", width="100%", bgcolor="#0b0e14", font_color="white")
    net.force_atlas_2based(gravity=-50, central_gravity=0.01, spring_length=100)
    
    try:
        if search_id and search_id.strip() != "":
            # TRACE MODE: The "Broken Flow" visualization
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
                # Green Node (Hover shows Net Amount)
                net.add_node(so, label=f"Order {so}", color="#2ecc71", title=f"Value: {r['netAmount']} INR", size=25)
                if r['deliveryDocument']:
                    de = str(r['deliveryDocument'])
                    # Blue Node
                    net.add_node(de, label=f"Del {de}", color="#3498db", title=f"Delivery ID: {de}", size=20)
                    net.add_edge(so, de, color="#575757")
                    if r['billingDocument']:
                        bi = str(r['billingDocument'])
                        # Yellow Node
                        net.add_node(bi, label=f"Inv {bi}", color="#f1c40f", title=f"Invoice ID: {bi}", size=20)
                        net.add_edge(de, bi, color="#575757")
        else:
            # EXPLORATION MODE: Basic view using only guaranteed columns
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

# 4. MAIN INTERFACE
with st.sidebar:
    st.title("💬 Assistant")
    if "messages" not in st.session_state: st.session_state.messages = []
    
    prompt = st.chat_input("Ask a question...")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        ai_response = get_ai_sql_response(prompt)
        
        if "designed to answer" in ai_response:
            st.session_state.messages.append({"role": "assistant", "content": ai_response})
        else:
            try:
                res_df = pd.read_sql_query(ai_response, get_connection())
                st.session_state.messages.append({"role": "assistant", "content": res_df})
            except:
                st.session_state.messages.append({"role": "assistant", "content": "Query failed. Try rephrasing."})
        st.rerun()

    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            if isinstance(m["content"], pd.DataFrame): st.dataframe(m["content"])
            else: st.markdown(m["content"])

st.title("🔗 O2C Knowledge Map")
search_id = st.text_input("🔍 Trace Transaction ID (Sales Order, Delivery, or Invoice)")
draw_graph(search_id)