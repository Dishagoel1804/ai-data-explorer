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
    """Reads the actual database structure so the AI doesn't have to guess."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [t[0] for t in cursor.fetchall()]
    schema_text = ""
    for table in tables:
        cursor.execute(f"PRAGMA table_info({table});")
        cols = [f"{c[1]}" for c in cursor.fetchall()]
        schema_text += f"Table {table} has columns: {', '.join(cols)}\n"
    conn.close()
    return schema_text

# 2. THE CHAT ENGINE (The "ChatGPT-like" Intelligence)
def ask_ai(user_query):
    schema = get_schema_for_ai()
    
    # This prompt forces the AI to understand the O2C relationships automatically
    system_message = f"""
    You are an expert SAP Data Scientist. 
    DATASET SCHEMA:
    {schema}

    O2C RELATIONSHIPS:
    - sales_order_items.salesOrder links to outbound_delivery_items.referenceSdDocument
    - outbound_delivery_items.deliveryDocument links to billing_document_items.referenceSdDocument

    YOUR GOAL:
    Translate the user's natural language into a valid SQLite query.
    - 'Broken flow' or 'stuck' means a record exists in a 'parent' table but not the 'child' table.
    - 'Top products' means grouping by 'productDescription' and summing 'netAmount'.
    
    GUARDRAIL (Requirement 5):
    If the user asks about ANYTHING other than this dataset (e.g. coffee, jokes, history), 
    respond EXACTLY: "This system is designed to answer questions related to the provided dataset only."

    Output ONLY the raw SQL. No explanation.
    """

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "system", "content": system_message}, {"role": "user", "content": user_query}]
        )
        sql = response.choices[0].message.content.strip().replace("```sql", "").replace("```", "")
        return sql
    except Exception as e:
        return f"Error: {e}"

# 3. INTERACTIVE GRAPH
def draw_graph(search_id=None, limit=50):
    conn = get_connection()
    net = Network(height="600px", width="100%", bgcolor="#0b0e14", font_color="white")
    net.force_atlas_2based()
    
    try:
        if search_id:
            query = f"SELECT s.salesOrder, d.deliveryDocument, b.billingDocument FROM sales_order_items s LEFT JOIN outbound_delivery_items d ON s.salesOrder = d.referenceSdDocument LEFT JOIN billing_document_items b ON d.deliveryDocument = b.referenceSdDocument WHERE s.salesOrder='{search_id}' OR d.deliveryDocument='{search_id}'"
        else:
            query = f"SELECT salesOrder, material FROM sales_order_items LIMIT {limit}"
        
        df = pd.read_sql_query(query, conn)
        for _, r in df.iterrows():
            # Add nodes dynamically based on query results
            for col in df.columns:
                if str(r[col]) != "None":
                    net.add_node(str(r[col]), label=str(r[col]), title=f"Type: {col}")
            # Simple edges for visualization
            if len(df.columns) > 1:
                net.add_edge(str(r[df.columns[0]]), str(r[df.columns[1]]))
                
        with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp:
            net.save_graph(tmp.name)
            with open(tmp.name, 'r') as f:
                components.html(f.read(), height=650)
    except:
        st.info("Search for an ID to see its lifecycle graph.")

# 4. MAIN LAYOUT
with st.sidebar:
    st.title("💬 Assistant")
    if "history" not in st.session_state: st.session_state.history = []
    
    user_input = st.chat_input("Ask about broken flows or top products...")
    if user_input:
        st.session_state.history.append({"role": "user", "content": user_input})
        answer = ask_ai(user_input)
        
        if "designed to answer" in answer:
            st.session_state.history.append({"role": "assistant", "content": answer})
        else:
            try:
                data = pd.read_sql_query(answer, get_connection())
                st.session_state.history.append({"role": "assistant", "content": data})
            except:
                st.session_state.history.append({"role": "assistant", "content": "I understood the request but the data structure didn't match. Try asking differently."})
        st.rerun()

    for m in st.session_state.history:
        with st.chat_message(m["role"]):
            if isinstance(m["content"], pd.DataFrame): st.dataframe(m["content"])
            else: st.markdown(m["content"])

st.title("🔗 O2C Knowledge Map")
search = st.text_input("🔍 Trace Transaction (ID)")
draw_graph(search)