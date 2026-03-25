import os
from load_data import ingest_all_data

def create_database():
    if not os.path.exists("sales.db"):
        print("Database not found. Starting full ingestion...")
        ingest_all_data()
    else:
        print("Database already exists.")

if __name__ == "__main__":
    create_database()