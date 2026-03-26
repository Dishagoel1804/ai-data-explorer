import streamlit as st
import pandas as pd
import sqlite3
import os
from pyvis.network import Network
import streamlit.components.v1 as components
from groq import Groq

# ---------------- 1. CONFIG ----------------
st.set_page_config(layout="wide", page_title="O2C Intelligence Graph")
st.markdown("<style>.stApp { background-color: #0b0e14; } .stChatInput { bottom: 20px; }</style>", unsafe_allow_html=True)

if "GROQ_API_KEY" in st.secrets:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
else:
    st.error("Missing GROQ_API_KEY in Secrets.")
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
        schema_info.append(f"Table {table} has columns: {', '.join(cols)}")
    conn.close()
    return "\n".join(schema_info)

# ---------------- 2. INTERACTIVE GRAPH WITH TOOLTIPS ----------------
def build_main_graph(search_id=None, sample_size=50):
    conn = get_connection()
    net = Network(height="700px", width="100%", bgcolor="#0b0e14", font_color="white", notebook=False)
    
    # Advanced Physics for the "Dodge AI" feel
    net.force_atlas_2based(gravity=-50, central_gravity=0.01, spring_length=100, spring_strength=0.08)
    
    try:
        if search_id and search_id.strip() != "":
            # TRACE MODE with Tooltips
            query = f"""
            SELECT s.salesOrder, d.deliveryDocument, b.billingDocument, s.material, s.netAmount, s.requestedQuantity
            FROM sales_order_items s
            LEFT JOIN outbound_delivery_items d ON s.salesOrder = d.referenceSdDocument
            LEFT JOIN billing_document_items b ON d.deliveryDocument = b.referenceSdDocument
            WHERE s.salesOrder='{search_id}' OR d.deliveryDocument='{search_id}' OR b.billingDocument='{search_id}'
            """
            df = pd.read_sql_query(query, conn)
            for _, row in df.iterrows():
                so, deli, bill = str(row['salesOrder']), str(row['deliveryDocument']), str(row['billingDocument'])
                
                # Adding Tooltips via the 'title' attribute
                if so != "None":
                    net.add_node(so, label=f"Order {so}", color="#2ecc71", size=25, 
                                 title=f"Order: {so}\nMaterial: {row['material']}\nValue: {row['netAmount']} INR")
                if deli != "None": 
                    net.add_node(deli, label=f"Delivery {deli}", color="#3498db", size=20,
                                 title=f"Delivery: {deli}\nQty: {row['requestedQuantity']}")
                    if so != "None": net.add_edge(so, deli, color="#575757")
                if bill != "None":
                    net.add_node(bill, label=f"Invoice {bill}", color="#f1c40f", size=20,
                                 title=f"Billing: {bill}\nStatus: Cleared")
                    if deli != "None": net.add_edge(deli, bill, color="#575757")
        else:
            # EXPLORATION MODE with Product Names
            query = f"""
            SELECT s.salesOrder, s.material, p.productName 
            FROM sales_order_items s 
            LEFT JOIN product_descriptions p ON s.material = p.product 
            LIMIT {sample_size}
            """
            df = pd.read_sql_query(query, conn)
            for _, row in df.iterrows():
                p_name = row['productName'] if row['productName'] else "Unknown Product"
                net.add_node(str(row['salesOrder']), label=f"SO {row['salesOrder']}", color="#2ecc71", title=f"Sales Order {row['salesOrder']}")
                net.add_node(str(row['material']), label=f"Prod {row['material']}", color="#e74c3c", title=f"Name: {p_name}")
                net.add_edge(str(row['salesOrder']), str(row['material']))

        net.save_graph("large_graph.html")
        with open("large_graph.html", "r", encoding="utf-8") as f:
            components.html(f.read(), height=720)
    except Exception: pass

# ---------------- 3. INTELLIGENT AI CORE (Requirement 5) ----------------
def get_ai_response(user_input):
    schema = get_full_schema_context()
    system_prompt = f"""
    You are an expert SAP O2C Data Analyst.
    SCHEMA: {schema}
    
    1. GUARDRAIL: If query is NOT about the dataset (jokes, general info, coding help), respond: "This system is designed to answer questions related to the provided dataset only."
    2. MAPPING: 
       - 'sales' or 'revenue' -> sum(netAmount)
       - 'top product' -> group by material and join with product_descriptions to get productName.
       - 'unbilled' -> LEFT JOIN outbound_delivery_items with billing_document_items where billingDocument is NULL.
    3. Return ONLY a valid SQLite query. No formatting, no conversation.
    """
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_input}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"ERROR: {str(e)}"

# ---------------- 4. UI LAYOUT ----------------
with st.sidebar:
    st.title("💬 Data Assistant")
    sample_val = st.slider("Graph Density (Nodes)", 10, 200, 50)
    search_input = st.text_input("🔍 Trace Specific ID", placeholder="e.g. 80001234")
    
    st.write("---")
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            if isinstance(m["content"], pd.DataFrame):
                st.dataframe(m["content"], use_container_width=True)
            else:
                st.markdown(m["content"])

    if prompt := st.chat_input("Ask a question..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        ai_sql = get_ai_response(prompt)
        
        if "designed to answer questions" in ai_sql:
            st.session_state.messages.append({"role": "assistant", "content": ai_sql})
        else:
            try:
                res_df = pd.read_sql_query(ai_sql, get_connection())
                st.session_state.messages.append({"role": "assistant", "content": res_df})
            except:
                st.session_state.messages.append({"role": "assistant", "content": "I couldn't process that. Try: 'Top 5 materials by netAmount'."})
        st.rerun()

st.subheader("🔗 Order-to-Cash Knowledge Map")
build_main_graph(search_input, sample_val)