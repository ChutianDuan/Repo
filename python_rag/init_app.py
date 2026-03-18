from .db import init_table
from .logger import logger

def main():
    logger.info("Initializing database...")
    init_table()
    logger.info("Database initialized successfully.")

if __name__ == "__main__":
    main()
    