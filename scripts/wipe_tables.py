from src.utils.db import db_cursor


if __name__ == '__main__':
    with db_cursor() as cursor:
        if input("Would you like to erase all data in accounts table? ") == "y":
            cursor.execute("TRUNCATE TABLE accounts;")
        if input("Would you like to erase all data in contexts table? ") == "y":
            cursor.execute("TRUNCATE TABLE contexts;")