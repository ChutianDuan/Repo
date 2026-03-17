from pathlib import Path
import os

import pymysql
from dotenv import load_dotenv

def main():
    # 加载环境变量
    repo_dir = Path(__file__).resolve().parent.parent
    env_path = repo_dir / '.env'
    load_dotenv(dotenv_path=env_path)

    # 初始化链接
    conn = pymysql.connect(
        host=os.getenv("MYSQL_HOST"),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DATABASE"),
        port=int(os.getenv("MYSQL_PORT", 3306)),
        charset="utf8mb4",
        autocommit=True,
    )

    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS demo_user (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    name VARCHAR(64) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("INSERT INTO demo_user (name) VALUES (%s)", ("day2_test_user",))
            cur.execute("SELECT id, name, created_at FROM demo_user ORDER BY id DESC LIMIT 5")
            rows = cur.fetchall()

            print("MySQL connection successful")
            print("Recent users:")
            for row in rows:
                print(row)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
    