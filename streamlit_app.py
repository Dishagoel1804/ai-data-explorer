import streamlit as st
import pandas as pd
import sqlite3
import os
from pyvis.network import Network
import streamlit.components.v1 as components
from groq import Groq

# ---------------- 1. CONFIG ----------------
st.set_page_config(layout="wide", page_title="O2C Intelligence Graph")

# Custom CSS to make the interface cleaner
st.markdown("<style>.stApp { background-color: #0b0e14; } .stChatInput { bottom: 20px; }</style>", unsafe_allow_html=True)

if "GROQ_API_KEY" in st.secrets:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
else:
    st.error("Missing GROQ_API_KEY")
    st.stop()

DB_PATH = "sales.db"

def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

# ---------------- 2. LARGE INTERACTIVE GRAPH ----------------
def build_main_graph(search_id=None, sample_size=50):
    conn = get_connection()
    # Increased height and enabled full interactivity
    net = Network(height="700px", width="100%", bgcolor="#0b0e14", font_color="white", notebook=False)
    
    # Enable complex physics for that "bouncy" interactive feel
    net.force_atlas_2based(gravity=-50, central_gravity=0.01, spring_length=100, spring_strength=0.08)
    
    try:
        if search_id and search_id.strip() != "":
            # TRACE MODE: Show the specific lifecycle of one document
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
                if so != "None": net.add_node(so, label=f"Order {so}", color="#2ecc71", size=25)
                if deli != "None": 
                    net.add_node(deli, label=f"Delivery {deli}", color="#3498db", size=20)
                    if so != "None": net.add_edge(so, deli, color="#575757")
                if bill != "None":
                    net.add_node(bill, label=f"Invoice {bill}", color="#f1c40f", size=20)
                    if deli != "None": net.add_edge(deli, bill, color="#575757")
        else:
            # EXPLORATION MODE: Show cross-section of the 19 folders
            # We link Sales Orders to Materials (Products) across the dataset
            df = pd.read_sql_query(f"SELECT salesOrder, material FROM sales_order_items LIMIT {sample_size}", conn)
            for _, row in df.iterrows():
                net.add_node(str(row['salesOrder']), label=f"SO {row['salesOrder']}", color="#2ecc71", title="Sales Order")
                net.add_node(str(row['material']), label=f"Product {row['material']}", color="#e74c3c", title="Material ID")
                net.add_edge(str(row['salesOrder']), str(row['material']))

        net.save_graph("large_graph.html")
        with open("large_graph.html", "r", encoding="utf-8") as f:
            components.html(f.read(), height=720)
    except Exception as e:
        st.error(f"Graph Error: {e}")

# ---------------- 3. HIDDEN AI LOGIC ----------------
def get_ai_sql(user_input):
    # Simple schema fetch for the AI
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    schema = ", ".join([t[0] for t in cursor.fetchall()])
    conn.close()

    system_prompt = f"You are a SQL engine. Tables: {schema}. Return ONLY raw SQL. No explanations. If unrelated, return 'GUARDRAIL'."
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_input}]
    )
    return response.choices[0].message.content.strip()

# ---------------- 4. REARRANGED LAYOUT ----------------

# Sidebar: Chat and Controls
with st.sidebar:
    st.title("💬 Data Assistant")
    
    # Sample Size Slider (Feature to show more data)
    sample_val = st.slider("Graph Density (Nodes)", 10, 200, 50)
    
    # ID Search
    search_input = st.text_input("🔍 Trace Specific ID", placeholder="e.g. 80001234")
    
    st.write("---")
    # Chat History
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            if isinstance(m["content"], pd.DataFrame):
                st.dataframe(m["content"], use_container_width=True)
            else:
                st.markdown(m["content"])

    if prompt := st.chat_input("Ask about the data..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        sql = get_ai_sql(prompt)
        if "GUARDRAIL" in sql:
            st.session_state.messages.append({"role": "assistant", "content": "I only answer SAP O2C data queries."})
        else:
            try:
                res_df = pd.read_sql_query(sql, get_connection())
                st.session_state.messages.append({"role": "assistant", "content": res_df})
            except:
                st.session_state.messages.append({"role": "assistant", "content": "Query failed. Try rephrasing."})
        st.rerun()

# Main Area: The Massive Graph
st.subheader("🔗 Order-to-Cash Knowledge Map")
build_main_graph(search_input, sample_val)