from src.utils.db import db_cursor


if __name__ == '__main__':
    with db_cursor() as cursor:
        if input("Would you like to nuke the accounts table? ") == "y":
            cursor.execute("DROP TABLE IF EXISTS accounts;")
        if input("Would you like to nuke the contexts table? ") == "y":
            cursor.execute("DROP TABLE IF EXISTS contexts;")
