# imports
import json
import os  # for env vars
from contextlib import contextmanager
from typing import overload, Union, Literal
import hashlib

import mysql.connector

# variables
addr: str = os.getenv("DB_ADDR", "127.0.0.1")
port: int = int(os.getenv("DB_PORT", "3306"))
root_pass: str = os.getenv("DB_ROOT_PASS")
# root_pass: str = "toiletbar"


# functions
# ===== GENERAL FUNCTIONS =====
@contextmanager
def db_cursor() -> mysql.connector.connection.MySQLCursor:
    try:
        connection = mysql.connector.connect(
            host=addr,
            port=port,
            user="root",
            password=root_pass,
            database="aipi"
        )
        cursor = connection.cursor()
    except mysql.connector.errors.DatabaseError as e:
        raise ConnectionError(f"Couldn't connect to MySQL server. Is it plugged in? ({e})")

    try:
        yield cursor
        connection.commit()
    finally:
        cursor.close()
        connection.close()


def init_tables() -> None:
    """Creates, configures and initializes tables in the specified db if they don't already exist."""
    # init connection
    try:
        connection = mysql.connector.connect(
            host=addr,
            port=port,
            user="root",
            password=root_pass
        )
        cursor = connection.cursor()
    except mysql.connector.errors.DatabaseError as e:
        raise ConnectionError(f"Couldn't connect to MySQL server. Is it plugged in? ({e})")

    # init database
    print("Initializing database...")
    cursor.execute("CREATE DATABASE IF NOT EXISTS aipi;")
    cursor.execute("USE aipi")
    print("Database initialized...")

    # init accounts table
    print("Initializing accounts table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            uid INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    print("Accounts table initialized...")

    # init contexts table
    print("Initializing context table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contexts (
            id INT AUTO_INCREMENT PRIMARY KEY,
            task VARCHAR(128) NOT NULL,
            model_id VARCHAR(255) NOT NULL,
            owner INT NOT NULL,
            context JSON,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (owner) REFERENCES accounts(uid) ON DELETE CASCADE
        );
    """)
    print("Context table initialized...")

    # disconnect
    connection.commit()
    cursor.close()
    connection.close()


# ===== CONTEXTS FUNCTIONS =====
def get_context(cid: int) -> dict:
    # with db_cursor() as cursor:
    #     cursor.execute("SELECT context FROM contexts WHERE id = %s;", (cid,))
    #     row: Union[None, tuple[Union[str, bytes]]] = cursor.fetchone()
    #     if not row:
    #         raise KeyError(f"No context could be found under cid {cid}")
    #     context_bytes: Union[str, bytes] = row[0]
    #     if not context_bytes:
    #         raise KeyError(f"No context could be found under cid {cid}")
    #     return json.loads(context_bytes)
    with db_cursor() as cursor:
        # Use dictionary cursor so results are returned as a dict
        cursor.execute("SELECT * FROM contexts WHERE id = %s;", (cid,))
        row = cursor.fetchone()
        if row is None:
            raise KeyError(f"No context exists with id {cid}")

        # Convert tuple to dict if cursor is not a dictionary cursor
        # If you want automatic dict, create cursor as:
        # cursor = conn.cursor(dictionary=True)
        if not isinstance(row, dict):
            columns = [col[0] for col in cursor.description]
            row = dict(zip(columns, row))

        return row


def get_context_owner(cid: int) -> int:
    with db_cursor() as cursor:
        cursor.execute("SELECT owner FROM contexts WHERE id = %s;", (cid,))
        return int(cursor.fetchone()[0])


def create_context(model_id: str, task: (Literal, str), uid: int) -> int:
    """Creates a context with `model_id` owned by `uid`, and returns it's `cid`."""
    with db_cursor() as cursor:
        cursor.execute("INSERT INTO contexts (owner, task, model_id, context) VALUES (%s, %s, %s, %s);", (uid, task, model_id, json.dumps({"history": []})))
        cid: int = cursor.lastrowid
        return cid


def add_to_context(message: dict, cid: int) -> dict:
    context: dict = get_context(cid)
    with db_cursor() as cursor:
        context["history"].append(message)
        cursor.execute("UPDATE contexts SET context = %s WHERE id = %s;", (json.dumps(context), cid))
        return context


# ===== ACCOUNTS FUNCTIONS =====
@overload
def user_exists(username: str) -> bool:
    """Returns whether a user with `username` exists in the specified db's accounts table."""
    ...


@overload
def user_exists(uid: int) -> bool:
    """Returns whether a user with `uid` exists in the specified db's accounts table."""
    ...


def user_exists(user: Union[str, int]) -> bool:
    if not any([isinstance(user, str), isinstance(user, int)]):  # sanitize...
        raise TypeError(f"`user` must be of type `str` or `int` not {user.__class__}")

    with db_cursor() as cursor:
        cursor.execute(
            f"SELECT uid FROM accounts WHERE {'username' if isinstance(user, str) else 'uid'} = %s;",
            (user,))
        return cursor.fetchone() is not None


def get_user_by_username(username: str) -> dict | None:
    """
    Fetch all fields for a user by username.
    Returns a dict of the row (column names as keys) or None if not found.
    FUNCTION GENERATED WITH AI.
    """
    with db_cursor() as cursor:
        # Use dictionary cursor so results are returned as a dict
        cursor.execute("SELECT * FROM accounts WHERE username = %s;", (username,))
        row = cursor.fetchone()
        if row is None:
            return None

        # Convert tuple to dict if cursor is not a dictionary cursor
        # If you want automatic dict, create cursor as:
        # cursor = conn.cursor(dictionary=True)
        if not isinstance(row, dict):
            columns = [col[0] for col in cursor.description]
            row = dict(zip(columns, row))

        return row


@overload
def is_correct_pass(username: str, password: str) -> bool:
    ...


@overload
def is_correct_pass(uid: int, password: str) -> bool:
    ...


def is_correct_pass(user: Union[str, int], password: str) -> bool:
    if not user_exists(user):  # technically this does all the `user` sanitization we need...
        raise ValueError(f"User '{user}' does not exist!")

    with db_cursor() as cursor:
        password_hash: str = hashlib.sha256(password.encode("utf-8")).hexdigest()
        cursor.execute(
            f"SELECT password_hash FROM accounts WHERE {'username' if isinstance(user, str) else 'uid'} = %s",
            (user,))
        real_password = cursor.fetchone()[0]
        print(f"Determining if {password_hash} ({password}) is equal to {real_password}")
        return password_hash == real_password


def create_user(username: str, password: str) -> int:
    """Creates a user with `username` and `password` in the db's accounts table. Returns the uid of the newly created user if successful"""
    if user_exists(username):
        raise RuntimeError(f"User {username} already exists!")

    password_hash: str = hashlib.sha256(password.encode("utf-8")).hexdigest()

    with db_cursor() as cursor:
        cursor.execute("INSERT INTO accounts (username, password_hash) VALUES (%s, %s);", (username, password_hash))
        uid: int = cursor.lastrowid
        return uid
