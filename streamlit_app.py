import streamlit as st
import sqlite3
import pandas as pd
import os
from dotenv import load_dotenv
from groq import Groq
from pyvis.network import Network
import streamlit.components.v1 as components

# ---------- SETUP ----------
load_dotenv()
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

st.set_page_config(page_title="AI Data Explorer", layout="wide")
st.title("📊 AI Data Explorer with Interactive Graph + Chat")

# ---------- DATABASE ----------
def run_sql(query):
    conn = sqlite3.connect("data.db")
    try:
        df = pd.read_sql_query(query, conn)
        return df
    except Exception as e:
        return str(e)
    finally:
        conn.close()

# ---------- LOAD GRAPH DATA ----------
def load_graph_data():
    conn = sqlite3.connect("data.db")
    df = pd.read_sql_query(
        "SELECT material, netAmount FROM billing_items LIMIT 30", conn
    )
    conn.close()
    return df

# ---------- GRAPH ----------
def build_graph(df):
    net = Network(height="500px", width="100%")

    for _, row in df.iterrows():
        product = str(row["material"])
        amount = str(row["netAmount"])

        net.add_node(product, label=product, color="blue")
        net.add_node(amount, label=amount, color="green")
        net.add_edge(product, amount)

    net.save_graph("graph.html")

    with open("graph.html", "r", encoding="utf-8") as f:
        components.html(f.read(), height=550)

# ---------- INTENT ----------
def is_data_question(question):
    keywords = ["sales", "total", "amount", "top", "count", "product", "material"]
    return any(word in question.lower() for word in keywords)

# ---------- LLM ----------
def generate_sql(question):
    prompt = f"""
Convert this question to SQL using table billing_items(material, netAmount).
Question: {question}
Only return SQL.
"""
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}]
    )

    sql = response.choices[0].message.content.strip()
    sql = sql.replace("```sql", "").replace("```", "").strip()
    return sql


def explain(question, sql, result_df):
    limited = result_df.head(5).to_string(index=False)

    prompt = f"""
Explain clearly.

Question: {question}
SQL: {sql}
Result:
{limited}
"""

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content.strip()


def normal_chat(q):
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": q}]
    )
    return response.choices[0].message.content.strip()

# ---------- CHAT MEMORY ----------
if "messages" not in st.session_state:
    st.session_state.messages = []

# ---------- LOAD DATA ----------
df_graph = load_graph_data()

# ---------- LAYOUT ----------
col1, col2 = st.columns([2, 1])

# ---------- LEFT: GRAPH + INTERACTION ----------
with col1:
    st.subheader("🔗 Interactive Graph")

    build_graph(df_graph)

    st.markdown("### 🔍 Explore Node")

    selected_node = st.selectbox(
        "Select a material:",
        df_graph["material"].unique()
    )

    if st.button("Analyze Selected Node"):
        query = f"""
        SELECT material, SUM(netAmount) as total_sales
        FROM billing_items
        WHERE material = '{selected_node}'
        GROUP BY material
        """

        result = run_sql(query)

        if not isinstance(result, str):
            st.success(f"Analysis for {selected_node}")
            st.dataframe(result)

# ---------- RIGHT: CHAT ----------
with col2:
    st.subheader("💬 Chat with Data")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    if prompt := st.chat_input("Ask anything..."):

        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)

        if is_data_question(prompt):

            sql = generate_sql(prompt)
            result = run_sql(sql)

            if isinstance(result, str):
                reply = f"❌ {result}"
            else:
                explanation = explain(prompt, sql, result)

                reply = f"""
SQL:
{sql}

Result:
{result.head().to_string(index=False)}

Explanation:
{explanation}
"""

        else:
            reply = normal_chat(prompt)

        st.session_state.messages.append({"role": "assistant", "content": reply})
        with st.chat_message("assistant"):
            st.write(reply)