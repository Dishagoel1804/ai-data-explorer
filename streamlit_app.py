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

# 2. THE CHAT ENGINE (Exact logic you liked)
def ask_ai(user_query):
    schema = get_schema_for_ai()
    
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

# 3. INTERACTIVE GRAPH (With Colors & Tooltips)
def draw_graph(search_id=None, limit=50):
    conn = get_connection()
    net = Network(height="650px", width="100%", bgcolor="#0b0e14", font_color="white")
    net.force_atlas_2based()
    
    try:
        if search_id and search_id.strip() != "":
            # TRACE MODE: The "Lifecycle" flow
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
                # Order Node (Green)
                net.add_node(so, label=f"Order {so}", color="#2ecc71", title=f"Value: {r['netAmount']}", size=25)
                
                if r['deliveryDocument']:
                    de = str(r['deliveryDocument'])
                    # Delivery Node (Blue)
                    net.add_node(de, label=f"Del {de}", color="#3498db", title=f"Delivery ID: {de}", size=20)
                    net.add_edge(so, de, color="#575757")
                    
                    if r['billingDocument']:
                        bi = str(r['billingDocument'])
                        # Invoice Node (Yellow)
                        net.add_node(bi, label=f"Inv {bi}", color="#f1c40f", title=f"Invoice ID: {bi}", size=20)
                        net.add_edge(de, bi, color="#575757")
        else:
            # EXPLORATION MODE: Standard view
            query = "SELECT salesOrder, material FROM sales_order_items LIMIT 40"
            df = pd.read_sql_query(query, conn)
            for _, r in df.iterrows():
                net.add_node(str(r['salesOrder']), label=f"SO {r['salesOrder']}", color="#2ecc71", title="Sales Order")
                net.add_node(str(r['material']), label=f"Mat {r['material']}", color="#e74c3c", title="Material/Product")
                net.add_edge(str(r['salesOrder']), str(r['material']))

        with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp:
            net.save_graph(tmp.name)
            with open(tmp.name, 'r', encoding='utf-8') as f:
                components.html(f.read(), height=660)
    except:
        st.info("No matching data found for this ID.")

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
search = st.text_input("🔍 Trace Transaction (Enter ID)")
draw_graph(search)