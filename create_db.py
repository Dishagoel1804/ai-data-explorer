import os
import json
import sqlite3
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(BASE_DIR, "sales.db")

conn = sqlite3.connect(DB_PATH)

def load_jsonl_folder(folder_name, table_name):
    folder_path = os.path.join(DATA_DIR, folder_name)

    all_data = []

    for file in os.listdir(folder_path):
        if file.endswith(".jsonl"):
            file_path = os.path.join(folder_path, file)

            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    all_data.append(json.loads(line))

    if all_data:
        df = pd.DataFrame(all_data)
        df.to_sql(table_name, conn, if_exists="replace", index=False)
        print(f"✅ Loaded {table_name} ({len(df)} rows)")
    else:
        print(f"❌ No data in {folder_name}")

# Load all 3 datasets
load_jsonl_folder("sales_order_items", "sales_order_items")
load_jsonl_folder("billing_document_items", "billing_items")
load_jsonl_folder("outbound_delivery_items", "delivery_items")

conn.close()