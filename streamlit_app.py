import streamlit as st
import pandas as pd
import sqlite3
from pyvis.network import Network
import streamlit.components.v1 as components
from groq import Groq
import re

# ---------------- CONFIG ----------------
st.set_page_config(layout="wide", page_title="AI Graph Explorer")

# ---------------- API ----------------
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# ---------------- DB ----------------
def get_connection():
    return sqlite3.connect("sales.db")

# ---------------- SQL CLEANER ----------------
def clean_sql(query):
    query = query.strip()
    query = re.sub(r"```sql|```", "", query, flags=re.IGNORECASE)
    query = re.sub(r"^sql\s*", "", query, flags=re.IGNORECASE)
    return query.strip()

# ---------------- LLM ----------------
def generate_response(messages):
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=messages,
    )
    return response.choices[0].message.content.strip()

# ---------------- GUARDRAILS ----------------
def classify_question(question):
    prompt = f"""
    Classify the question.

    If it is related to this dataset (salesOrder, material, netAmount), return: DATA
    Otherwise return: REJECT

    Question: {question}
    """
    return generate_response([{"role": "user", "content": prompt}]).strip()

# ---------------- SQL GENERATION ----------------
def generate_sql(question):
    prompt = f"""
    You are a strict SQL generator.

    Table: sales_order_items
    Columns: salesOrder, material, netAmount

    Rules:
    - Only generate SELECT queries
    - Use only given columns
    - No assumptions
    - If not possible, return: INVALID
    - Do NOT include 'sql' or markdown

    Question: {question}
    """
    return clean_sql(generate_response([{"role": "user", "content": prompt}]))

# ---------------- GRAPH ----------------
def build_graph(selected_node=None):
    conn = get_connection()

    try:
        if selected_node:
            query = f"""
            SELECT * FROM sales_order_items
            WHERE salesOrder = '{selected_node}'
            OR material = '{selected_node}'
            LIMIT 50
            """
        else:
            query = "SELECT * FROM sales_order_items LIMIT 50"

        df = pd.read_sql_query(query, conn)

        net = Network(
            height="650px",
            width="100%",
            bgcolor="#0e1117",
            font_color="white"
        )

        net.force_atlas_2based()

        for _, row in df.iterrows():
            sales = str(row["salesOrder"])
            material = str(row["material"])
            amount = str(row["netAmount"])

            net.add_node(
                sales,
                label=sales,
                color="#2ca02c",
                title=f"Sales Order: {sales}\nMaterial: {material}\nAmount: {amount}"
            )

            net.add_node(
                material,
                label=material,
                color="#1f77b4",
                title=f"Material: {material}"
            )

            net.add_node(
                amount,
                label=amount,
                color="#ff7f0e",
                title=f"Net Amount: {amount}"
            )

            net.add_edge(sales, material)
            net.add_edge(material, amount)

        net.save_graph("graph.html")

        with open("graph.html", "r", encoding="utf-8") as f:
            components.html(f.read(), height=650)

    except Exception as e:
        st.error(f"Graph Error: {e}")

# ---------------- SESSION ----------------
if "messages" not in st.session_state:
    st.session_state.messages = []

# ---------------- UI ----------------
st.title("🧠 AI Knowledge Graph Explorer")

col1, col2 = st.columns([2, 1])

# -------- GRAPH --------
with col1:
    st.subheader("🔗 Graph Explorer")

    selected_node = st.text_input("🔍 Enter SalesOrder or Material to expand")

    build_graph(selected_node)

# -------- CHAT --------
with col2:
    st.subheader("💬 Chat Interface")

    # Show chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Input
    if prompt := st.chat_input("Ask about your data..."):

        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.chat_message("user"):
            st.markdown(prompt)

        # Guardrail check
        category = classify_question(prompt)

        if "REJECT" in category.upper():
            response_text = "⚠️ This system is designed to answer questions related to the dataset only."

        else:
            sql = generate_sql(prompt)

            if "INVALID" in sql.upper():
                response_text = "❌ Cannot answer this from available dataset."

            else:
                try:
                    conn = get_connection()
                    result = pd.read_sql_query(sql, conn)

                    # Show table nicely
                    st.dataframe(result.head())

                    response_text = f"""
### 🧠 SQL

{sql}

### 📊 Result

{result.head().to_string(index=False)}
"""

                except Exception as e:
                    response_text = f"❌ SQL Error: {e}"

        # Show response
        with st.chat_message("assistant"):
            st.markdown(response_text)

        st.session_state.messages.append({"role": "assistant", "content": response_text})