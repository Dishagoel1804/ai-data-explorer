import pandas as pd
import sqlite3
import os
import json

def ingest_all_data(data_root="data", db_name="sales.db"):
    conn = sqlite3.connect(db_name)
    
    if not os.path.exists(data_root):
        print(f"Error: {data_root} directory not found.")
        return

    folders = [f for f in os.listdir(data_root) if os.path.isdir(os.path.join(data_root, f))]
    
    for folder in folders:
        folder_path = os.path.join(data_root, folder)
        all_dfs = []
        
        jsonl_files = [f for f in os.listdir(folder_path) if f.endswith(".jsonl")]
        
        for file in jsonl_files:
            full_path = os.path.join(folder_path, file)
            try:
                df = pd.read_json(full_path, lines=True)
                all_dfs.append(df)
            except Exception as e:
                print(f"Skipping {file} due to error: {e}")
        
        if all_dfs:
            combined_df = pd.concat(all_dfs, ignore_index=True)
            combined_df.columns = [col.strip() for col in combined_df.columns]

            # --- THE FIX STARTS HERE ---
            # Convert any columns that contain dictionaries or lists into strings
            for col in combined_df.columns:
                if combined_df[col].apply(lambda x: isinstance(x, (dict, list))).any():
                    combined_df[col] = combined_df[col].apply(lambda x: json.dumps(x) if x is not None else None)
            # --- THE FIX ENDS HERE ---

            combined_df.to_sql(folder, conn, if_exists="replace", index=False)
            print(f"✅ Table '{folder}': Loaded {len(combined_df)} rows.")

    conn.close()
    print("\n🚀 Database 'sales.db' is ready!")

if __name__ == "__main__":
    ingest_all_data()