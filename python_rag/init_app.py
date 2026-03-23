# python_rag/init_app.py
import os
from python_rag.db import execute_sql_file


def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sql_path = os.path.join(base_dir, "db", "init.sql")
    execute_sql_file(sql_path)
    print("[OK] database initialized from:", sql_path)


if __name__ == "__main__":
    main()