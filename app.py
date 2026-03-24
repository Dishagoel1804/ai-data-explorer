from flask import Flask, request, jsonify
import sqlite3
import os
from dotenv import load_dotenv
from groq import Groq
from flask_cors import CORS

load_dotenv()

app = Flask(__name__)
CORS(app)

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def run_sql(query):
    conn = sqlite3.connect("data.db")
    cursor = conn.cursor()

    try:
        cursor.execute(query)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return rows, columns
    except Exception as e:
        return str(e), []
    finally:
        conn.close()


def result_to_text(user_query, sql, result):
    prompt = f"""
You are a data analyst.

User question:
{user_query}

SQL Query:
{sql}

SQL Result:
{result}

Explain the result in simple human-readable format.
"""

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content.strip()


def prepare_chart_data(rows, columns):
    try:
        # Only works for 2-column results (label + value)
        if len(columns) == 2:
            labels = [str(row[0]) for row in rows]
            values = [float(row[1]) for row in rows]

            return {
                "labels": labels,
                "values": values
            }
    except:
        pass

    return None


@app.route("/query", methods=["POST"])
def query():
    try:
        user_query = request.json.get("query")

        system_prompt = """
You are an expert SQL generator.

Convert user questions into SQL queries.

Database schema:

sales_order_items:
- referenceSdDocument
- referenceSdDocumentItem

delivery_items:
- deliveryDocument
- deliveryDocumentItem
- referenceSdDocument

billing_items:
- billingDocument
- billingDocumentItem
- material
- netAmount
- referenceSdDocument

RULES:
- Use billing_items for sales queries
- material & netAmount exist only in billing_items
- No aliases
- Simple SQL only
- Only return SQL
"""

        # Step 1: Generate SQL
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query}
            ]
        )

        sql_query = response.choices[0].message.content.strip()
        sql_query = sql_query.replace("```sql", "").replace("```", "").strip()

        print("\nSQL:", sql_query)

        # Step 2: Run SQL
        rows, columns = run_sql(sql_query)

        # Step 3: Explanation
        explanation = result_to_text(user_query, sql_query, rows)

        # Step 4: Chart data
        chart_data = prepare_chart_data(rows, columns)

        return jsonify({
            "sql": sql_query,
            "result": rows,
            "explanation": explanation,
            "chart": chart_data
        })

    except Exception as e:
        return jsonify({"error": str(e)})


if __name__ == "__main__":
    app.run(debug=True)