import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'database/bearing_data.db')

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print("=" * 60)
print("数据库状态检查")
print("=" * 60)

cursor.execute('SELECT COUNT(*) FROM bearing_info')
bearing_count = cursor.fetchone()[0]
print(f"轴承总数: {bearing_count}")

cursor.execute('SELECT COUNT(*) FROM vibration_data')
data_count = cursor.fetchone()[0]
print(f"数据点总数: {data_count:,}")

cursor.execute('SELECT COUNT(*) FROM operating_condition')
condition_count = cursor.fetchone()[0]
print(f"工作条件数: {condition_count}")

print("\n按工作条件分布:")
cursor.execute('''
    SELECT oc.condition_name, COUNT(*) as count
    FROM bearing_info bi
    JOIN operating_condition oc ON bi.condition_id = oc.id
    GROUP BY oc.condition_name
''')
for row in cursor.fetchall():
    print(f"  {row[0]}: {row[1]}个轴承")

print("\nXJTU-SY轴承列表:")
cursor.execute('SELECT bearing_no, fault_type, condition_name FROM bearing_info bi JOIN operating_condition oc ON bi.condition_id=oc.id WHERE bearing_no LIKE "Bearing%" ORDER BY bearing_no')
for row in cursor.fetchall():
    print(f"  {row[0]:<12} - {row[1]:<20} - {row[2]}")

print("\n数据表结构:")
cursor.execute("PRAGMA table_info(bearing_info)")
print("bearing_info:")
for row in cursor.fetchall():
    print(f"  {row[1]:<20} {row[2]}")

cursor.execute("PRAGMA table_info(vibration_data)")
print("\nvibration_data:")
for row in cursor.fetchall():
    print(f"  {row[1]:<20} {row[2]}")

cursor.execute("PRAGMA table_info(operating_condition)")
print("\noperating_condition:")
for row in cursor.fetchall():
    print(f"  {row[1]:<25} {row[2]}")

conn.close()

print("\n" + "=" * 60)
print("检查完成")
print("=" * 60)