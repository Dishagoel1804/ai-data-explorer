import streamlit as st
import pandas as pd
import sqlite3
import os
import json
from pyvis.network import Network
import streamlit.components.v1 as components
from groq import Groq

# ---------------- 1. CONFIG & API ----------------
st.set_page_config(layout="wide", page_title="O2C Knowledge Graph")

# Make sure you have created .streamlit/secrets.toml with your GROQ_API_KEY
if "GROQ_API_KEY" in st.secrets:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
else:
    st.error("Missing GROQ_API_KEY in .streamlit/secrets.toml")
    st.stop()

# ---------------- 2. DATABASE UTILS ----------------
DB_PATH = "sales.db"

def get_connection():
    # check_same_thread=False is essential for Streamlit/SQLite stability
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def get_db_schema():
    """Reads the actual database to tell the AI exactly what tables/columns exist."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [t[0] for t in cursor.fetchall()]
    
    schema_desc = []
    for table in tables:
        cursor.execute(f"PRAGMA table_info({table});")
        columns = [f"{col[1]} ({col[2]})" for col in cursor.fetchall()]
        schema_desc.append(f"Table '{table}' has columns: {', '.join(columns)}")
    conn.close()
    return "\n".join(schema_desc)

# ---------------- 3. GRAPH VISUALIZATION ----------------
def build_o2c_graph(search_id=None):
    conn = get_connection()
    net = Network(height="500px", width="100%", bgcolor="#0e1117", font_color="white")
    net.force_atlas_2based()

    try:
        if search_id:
            # Full O2C Trace Query (Requirement 4b)
            # We use LEFT JOINs to show partial flows (Requirement 4c)
            query = f"""
            SELECT 
                s.salesOrder as SO, 
                d.deliveryDocument as DEL, 
                b.billingDocument as BILL
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
            # Default view: Sales Orders connected to Materials
            df = pd.read_sql_query("SELECT salesOrder, material FROM sales_order_items LIMIT 25", conn)
            for _, row in df.iterrows():
                net.add_node(str(row['salesOrder']), label=f"SO: {row['salesOrder']}", color="#2ecc71")
                net.add_node(str(row['material']), label=f"MAT: {row['material']}", color="#e74c3c")
                net.add_edge(str(row['salesOrder']), str(row['material']))

        net.save_graph("graph.html")
        with open("graph.html", "r", encoding="utf-8") as f:
            components.html(f.read(), height=550)
    except Exception as e:
        st.error(f"Graph Error: {e}")

# ---------------- 4. AI & GUARDRAILS ----------------
def get_ai_response(user_input):
    schema_context = get_db_schema()
    
    # Requirement 5: Strict Guardrails logic inside the prompt
    system_prompt = f"""
    You are a professional SAP Order-to-Cash Data Assistant.
    
    SCHEMA CONTEXT (Use these exact names):
    {schema_context}
    
    RULES:
    1. Only answer questions related to the provided tables. 
    2. For ANY other topic (general knowledge, creative writing, etc.), you MUST respond with: 
       "This system is designed to answer questions related to the provided dataset only."
    3. Return valid SQL inside ```sql blocks.
    4. Provide a brief summary of the findings after the SQL.
    """
    
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ]
    )
    return response.choices[0].message.content

# ---------------- 5. STREAMLIT UI ----------------
st.title("🧠 AI-Powered O2C Knowledge Graph")

# Sidebar for Search/Expansion (Requirement 2)
with st.sidebar:
    st.header("🔍 Graph Explorer")
    search_id = st.text_input("Enter ID (SO, Delivery, or Bill)", placeholder="e.g. 80001234")
    st.info("Searching an ID will 'Expand' the nodes to show the full transaction flow.")

col_left, col_right = st.columns([1.2, 1])

with col_left:
    st.subheader("🔗 Network Visualization")
    build_o2c_graph(search_id)

with col_right:
    st.subheader("💬 Natural Language Query")
    
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    if prompt := st.chat_input("Ask about top products, broken flows, or order status..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            try:
                full_ai_response = get_ai_response(prompt)
                
                # Check if the response contains SQL
                if "```sql" in full_ai_response:
                    sql_query = full_ai_response.split("```sql")[1].split("```")[0].strip()
                    df_result = pd.read_sql_query(sql_query, get_connection())
                    
                    st.markdown(full_ai_response)
                    st.dataframe(df_result, use_container_width=True)
                    st.session_state.messages.append({"role": "assistant", "content": full_ai_response})
                else:
                    # This handles the Guardrail rejection or general text
                    st.markdown(full_ai_response)
                    st.session_state.messages.append({"role": "assistant", "content": full_ai_response})
                    
            except Exception as e:
                err_msg = f"I encountered an error processing that: {e}"
                st.error(err_msg)
                st.session_state.messages.append({"role": "assistant", "content": err_msg})