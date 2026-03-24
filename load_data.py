import pandas as pd
import sqlite3
import os

conn = sqlite3.connect("data.db")

# Function to read all json files in a folder
def load_folder(folder_path):
    all_data = []
    
    for file in os.listdir(folder_path) or file.endswith(".json"):
        if file.endswith(".jsonl"):
            full_path = os.path.join(folder_path, file)
            df = pd.read_json(full_path, lines=True)
            all_data.append(df)
    
    return pd.concat(all_data, ignore_index=True)

# Load all folders
sales_items = load_folder("data/sales_order_items")
delivery_items = load_folder("data/outbound_delivery_items")
billing_items = load_folder("data/billing_document_items")

# Save to DB
sales_items.to_sql("sales_order_items", conn, if_exists="replace", index=False)
delivery_items.to_sql("delivery_items", conn, if_exists="replace", index=False)
billing_items.to_sql("billing_items", conn, if_exists="replace", index=False)

conn.close()

print("✅ All partitioned data loaded successfully!")