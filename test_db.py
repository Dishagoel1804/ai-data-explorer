import sqlite3

conn = sqlite3.connect("data.db")

# 1. Check tables
print("📊 Tables in DB:")
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
print(tables)

print("\n---\n")

# 2. Row counts
print("📦 Row counts:")

print("sales_order_items:", conn.execute("SELECT COUNT(*) FROM sales_order_items").fetchone())
print("delivery_items:", conn.execute("SELECT COUNT(*) FROM delivery_items").fetchone())
print("billing_items:", conn.execute("SELECT COUNT(*) FROM billing_items").fetchone())

print("\n---\n")

# 3. Sample data
print("🔍 Sample billing data:")
rows = conn.execute("SELECT * FROM billing_items LIMIT 5").fetchall()

for row in rows:
    print(row)

print("\n---\n")

# 4. First real business query
print("🏆 Top products by billing:")

query = """
SELECT material, COUNT(*) as count
FROM billing_items
GROUP BY material
ORDER BY count DESC
LIMIT 5;
"""

result = conn.execute(query).fetchall()

for row in result:
    print(row)

conn.close()