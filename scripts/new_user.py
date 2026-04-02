from src.utils.db import create_user


if __name__ == '__main__':
    username = input("Enter a username: ")
    password = input("Enter a password: ")
    create_user(username, password)
