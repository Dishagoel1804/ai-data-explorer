# 🧠 O2C Intelligence: AI-Powered Supply Chain Graph
> **An Enterprise-Grade SAP Order-to-Cash (O2C) Analytics Engine with Natural Language Querying.**

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge.svg)](https://ai-data-explorer-4nzhv7dklqhytmbftv4cu7.streamlit.app/)
![Llama 3.1](https://img.shields.io/badge/AI-Llama%203.1-orange.svg)
![SQLite](https://img.shields.io/badge/DB-SQLite-blue.svg)
![NetworkX](https://img.shields.io/badge/Graph-PyVis-green.svg)

---

## 🚀 Overview
**O2C Intelligence** is a decision-support tool designed to audit and visualize complex SAP lifecycles. By processing **19 high-scale data folders**, this application constructs a unified **Knowledge Graph** that allows users to identify "Broken Flows"—revenue-critical gaps where orders are placed but never fulfilled or billed.
<img width="1365" height="683" alt="image" src="https://github.com/user-attachments/assets/7e7cbe9e-31cd-4f13-8ab7-d4f1da6814c2" />
<img width="1365" height="718" alt="image" src="https://github.com/user-attachments/assets/2181b5a6-179b-47d4-86b7-9774d1a27c0c" />

## ✨ Special Features & Highlights

### 🎨 1. Dynamic Visual Encoding (Knowledge Map)
The graph uses **Semantic Color Coding** to represent the state of a transaction at a glance:
* 🟢 **Green Nodes**: Sales Orders (The initial customer intent).
* 🔵 **Blue Nodes**: Outbound Deliveries (Physical fulfillment).
* 🟡 **Yellow Nodes**: Billing Documents (Realized revenue).
* 🔴 **Red Nodes**: Material Master Data (The underlying products).
* 📍 **Interactive Tooltips**: Hover over any node to reveal instant metadata including **Net Value**, **Material IDs**, and **Document Types**.

### 🤖 2. NLP Assistant (Llama 3.1 Powered)
Stop writing SQL. Start asking questions. Our assistant uses **Groq-accelerated Llama 3.1** to translate business English into optimized SQLite queries.
* **Schema-Aware**: The AI reads the database structure dynamically to ensure 100% accuracy.
* **Zero-Knowledge Entry**: Pre-mapped logic for "Top Products," "Customer Revenue," and "Process Gaps."

### 🛠️ 3. Audit-Ready "Broken Flow" Detection
Built specifically for supply chain auditors to find **Revenue Leakage**:
* **Unbilled Deliveries**: Identifies items shipped but not yet invoiced.
* **Unfulfilled Orders**: Highlights sales demand that hasn't triggered a delivery.
* **Visual Trace**: Enter any ID to see a "dead-end" on the graph, visually proving where a process stalled.

### 🛡️ 4. Enterprise Guardrails
* **Domain Strictness**: The AI is strictly tethered to the O2C dataset. It will politely decline non-business queries (jokes, general trivia) to maintain professional integrity and system security.
<img width="1333" height="677" alt="image" src="https://github.com/user-attachments/assets/0d1c9389-98e7-4311-8ec3-013ad65d83de" />

---

## 🛠️ Technical Architecture

| Layer | Technology |
| :--- | :--- |
| **Interface** | Streamlit (High-performance Web UI) |
| **Logic Engine** | Python 3.11 + Pandas |
| **Brain** | Llama 3.1 (via Groq Cloud API) |
| **Database** | SQLite (Relational Storage for 19 O2C Folders) |
| **Graphing** | PyVis / Javascript (Force-Directed Network) |

---

## 🗃️ Data Coverage
The engine successfully normalizes and indexes 19 distinct SAP O2C datasets, including:
* **Sales**: Items, Headers, Partner Functions.
* **Logistics**: Outbound Deliveries, Picking Status, Loading.
* **Finance**: Billing Items, Pricing Elements, Conditions.
  <img width="1364" height="669" alt="image" src="https://github.com/user-attachments/assets/6b0d884a-6ac6-4468-b843-8557d163dcbd" />


## 📦 Getting Started

1. **Clone & Install**
   ```bash
   git clone [https://github.com/Dishagoel1804/ai-data-explorer.git](https://github.com/Dishagoel1804/ai-data-explorer.git)
   pip install streamlit pandas pyvis groq

2. **Launch**
     ```bash
streamlit run streamlit_app.py
