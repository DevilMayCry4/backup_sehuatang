import sqlite3
import json

def view_database():
    # 连接到数据库
    conn = sqlite3.connect('backup.db')
    cursor = conn.cursor()
    
    # 获取所有表名
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    
    for table in tables:
        table_name = table[0]
        print(f"\n表名: {table_name}")
        print("-" * 50)
        
        # 获取表结构
        cursor.execute(f"PRAGMA table_info({table_name});")
        columns = cursor.fetchall()
        print("列名:")
        for col in columns:
            print(f"  {col[1]} ({col[2]})")
        
        # 获取数据行数
        cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
        count = cursor.fetchone()[0]
        print(f"\n总行数: {count}")
        
        # 显示前5行数据
        if count > 0:
            print("\n前5行数据:")
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 5;")
            rows = cursor.fetchall()
            for row in rows:
                print("\n---行数据---")
                for col_name, value in zip([col[1] for col in columns], row):
                    # 尝试解析JSON字符串
                    if value and isinstance(value, str) and (value.startswith('{') or value.startswith('[')):
                        try:
                            parsed_value = json.loads(value)
                            print(f"  {col_name}: {json.dumps(parsed_value, ensure_ascii=False, indent=2)}")
                        except:
                            print(f"  {col_name}: {value}")
                    else:
                        print(f"  {col_name}: {value}")
    
    conn.close()

if __name__ == '__main__':
    view_database()