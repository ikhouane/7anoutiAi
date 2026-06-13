from __future__ import annotations

"""SQLite backend for the local 7anoutiAI demo."""

import sqlite3
from datetime import date
from typing import Any

import pandas as pd

from config import DATABASE_BACKEND, DB_PATH



def get_connection() -> sqlite3.Connection:
    if DATABASE_BACKEND != "sqlite":
        raise RuntimeError(
            "Supabase is selected, but the Supabase data layer has not been "
            "implemented yet. Set DATABASE_BACKEND=sqlite to run the current app."
        )

    try:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(DB_PATH)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection
    except (OSError, sqlite3.Error) as exc:
        raise RuntimeError(
            f"Could not open the SQLite database at {DB_PATH}. "
            "Check that the data directory exists and is writable."
        ) from exc


def initialize_database() -> None:
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL COLLATE NOCASE UNIQUE,
                category TEXT NOT NULL,
                buy_price REAL NOT NULL CHECK (buy_price >= 0),
                sell_price REAL NOT NULL CHECK (sell_price >= 0),
                stock_quantity INTEGER NOT NULL CHECK (stock_quantity >= 0),
                low_stock_threshold INTEGER NOT NULL CHECK (low_stock_threshold >= 0),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER,
                product_name TEXT NOT NULL,
                quantity INTEGER NOT NULL CHECK (quantity > 0),
                sale_date TEXT NOT NULL,
                revenue REAL NOT NULL CHECK (revenue >= 0),
                profit REAL NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL COLLATE NOCASE UNIQUE,
                phone TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS debt_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                customer_name TEXT NOT NULL,
                transaction_type TEXT NOT NULL
                    CHECK (transaction_type IN ('debt', 'payment')),
                amount REAL NOT NULL CHECK (amount > 0),
                note TEXT,
                transaction_date TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS restocks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER,
                product_name TEXT NOT NULL,
                quantity_added INTEGER NOT NULL CHECK (quantity_added > 0),
                supplier_name TEXT NOT NULL,
                unit_buy_price REAL NOT NULL CHECK (unit_buy_price >= 0),
                restock_date TEXT NOT NULL,
                updated_buy_price INTEGER NOT NULL DEFAULT 0
                    CHECK (updated_buy_price IN (0, 1)),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(sale_date);
            CREATE INDEX IF NOT EXISTS idx_sales_product_id ON sales(product_id);
            CREATE INDEX IF NOT EXISTS idx_debt_customer_id
                ON debt_transactions(customer_id);
            CREATE INDEX IF NOT EXISTS idx_debt_date
                ON debt_transactions(transaction_date);
            CREATE INDEX IF NOT EXISTS idx_restocks_product_id
                ON restocks(product_id);
            CREATE INDEX IF NOT EXISTS idx_restocks_date
                ON restocks(restock_date);
            """
        )


def add_product(
    name: str,
    category: str,
    buy_price: float,
    sell_price: float,
    stock_quantity: int,
    low_stock_threshold: int,
) -> int:
    clean_name = name.strip()
    clean_category = category.strip()
    if not clean_name or not clean_category:
        raise ValueError("Product name and category are required.")
    if buy_price < 0 or sell_price < 0:
        raise ValueError("Prices cannot be negative.")
    if stock_quantity < 0 or low_stock_threshold < 0:
        raise ValueError("Stock values cannot be negative.")

    try:
        with get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO products (
                    name, category, buy_price, sell_price,
                    stock_quantity, low_stock_threshold
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    clean_name,
                    clean_category,
                    float(buy_price),
                    float(sell_price),
                    int(stock_quantity),
                    int(low_stock_threshold),
                ),
            )
            return int(cursor.lastrowid)
    except sqlite3.IntegrityError as exc:
        raise ValueError(f'A product named "{clean_name}" already exists.') from exc


def update_product(
    product_id: int,
    name: str,
    category: str,
    buy_price: float,
    sell_price: float,
    stock_quantity: int,
    low_stock_threshold: int,
) -> None:
    clean_name = name.strip()
    clean_category = category.strip()
    if not clean_name or not clean_category:
        raise ValueError("Product name and category are required.")
    if buy_price < 0 or sell_price < 0:
        raise ValueError("Prices cannot be negative.")
    if stock_quantity < 0 or low_stock_threshold < 0:
        raise ValueError("Stock values cannot be negative.")

    try:
        with get_connection() as connection:
            cursor = connection.execute(
                """
                UPDATE products
                SET name = ?,
                    category = ?,
                    buy_price = ?,
                    sell_price = ?,
                    stock_quantity = ?,
                    low_stock_threshold = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    clean_name,
                    clean_category,
                    float(buy_price),
                    float(sell_price),
                    int(stock_quantity),
                    int(low_stock_threshold),
                    int(product_id),
                ),
            )
            if cursor.rowcount == 0:
                raise ValueError("Product not found.")
    except sqlite3.IntegrityError as exc:
        raise ValueError(f'A product named "{clean_name}" already exists.') from exc


def delete_product(product_id: int) -> None:
    with get_connection() as connection:
        cursor = connection.execute(
            "DELETE FROM products WHERE id = ?",
            (int(product_id),),
        )
        if cursor.rowcount == 0:
            raise ValueError("Product not found.")


def get_products() -> pd.DataFrame:
    with get_connection() as connection:
        return pd.read_sql_query(
            """
            SELECT
                id,
                name,
                category,
                buy_price,
                sell_price,
                stock_quantity,
                low_stock_threshold
            FROM products
            ORDER BY name
            """,
            connection,
        )


def get_product(product_id: int) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                id,
                name,
                category,
                buy_price,
                sell_price,
                stock_quantity,
                low_stock_threshold
            FROM products
            WHERE id = ?
            """,
            (int(product_id),),
        ).fetchone()
    return dict(row) if row else None


def record_sale(product_id: int, quantity: int, sale_date: date | str) -> dict[str, float]:
    if quantity <= 0:
        raise ValueError("Quantity sold must be greater than zero.")

    sale_date_text = sale_date.isoformat() if isinstance(sale_date, date) else str(sale_date)

    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        product = connection.execute(
            """
            SELECT id, name, buy_price, sell_price, stock_quantity
            FROM products
            WHERE id = ?
            """,
            (int(product_id),),
        ).fetchone()

        if product is None:
            raise ValueError("Product not found.")
        if int(product["stock_quantity"]) < int(quantity):
            raise ValueError(
                f'Insufficient stock. Only {product["stock_quantity"]} units are available.'
            )

        revenue = round(float(product["sell_price"]) * int(quantity), 2)
        profit = round(
            (float(product["sell_price"]) - float(product["buy_price"])) * int(quantity),
            2,
        )

        connection.execute(
            """
            INSERT INTO sales (
                product_id, product_name, quantity, sale_date, revenue, profit
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                int(product_id),
                product["name"],
                int(quantity),
                sale_date_text,
                revenue,
                profit,
            ),
        )
        connection.execute(
            """
            UPDATE products
            SET stock_quantity = stock_quantity - ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (int(quantity), int(product_id)),
        )

    return {"revenue": revenue, "profit": profit}


def get_sales() -> pd.DataFrame:
    with get_connection() as connection:
        return pd.read_sql_query(
            """
            SELECT
                id,
                product_id,
                product_name,
                quantity,
                sale_date,
                revenue,
                profit
            FROM sales
            ORDER BY sale_date DESC, id DESC
            """,
            connection,
        )


def add_customer_debt(
    customer_name: str,
    phone: str,
    amount: float,
    note: str,
    transaction_date: date | str,
) -> int:
    clean_name = customer_name.strip()
    clean_phone = phone.strip()
    clean_note = note.strip()
    if not clean_name:
        raise ValueError("Customer name is required.")
    if amount <= 0:
        raise ValueError("Debt amount must be greater than zero.")

    date_text = (
        transaction_date.isoformat()
        if isinstance(transaction_date, date)
        else str(transaction_date)
    )

    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        customer = connection.execute(
            "SELECT id FROM customers WHERE name = ? COLLATE NOCASE",
            (clean_name,),
        ).fetchone()

        if customer is None:
            cursor = connection.execute(
                "INSERT INTO customers (name, phone) VALUES (?, ?)",
                (clean_name, clean_phone or None),
            )
            customer_id = int(cursor.lastrowid)
        else:
            customer_id = int(customer["id"])
            if clean_phone:
                connection.execute(
                    """
                    UPDATE customers
                    SET phone = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (clean_phone, customer_id),
                )

        cursor = connection.execute(
            """
            INSERT INTO debt_transactions (
                customer_id, customer_name, transaction_type,
                amount, note, transaction_date
            )
            VALUES (?, ?, 'debt', ?, ?, ?)
            """,
            (
                customer_id,
                clean_name,
                round(float(amount), 2),
                clean_note or None,
                date_text,
            ),
        )
        return int(cursor.lastrowid)


def record_customer_payment(
    customer_id: int,
    payment_amount: float,
    payment_date: date | str,
) -> int:
    if payment_amount <= 0:
        raise ValueError("Payment amount must be greater than zero.")

    date_text = (
        payment_date.isoformat()
        if isinstance(payment_date, date)
        else str(payment_date)
    )

    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        customer = connection.execute(
            "SELECT id, name FROM customers WHERE id = ?",
            (int(customer_id),),
        ).fetchone()
        if customer is None:
            raise ValueError("Customer not found.")

        totals = connection.execute(
            """
            SELECT
                COALESCE(SUM(CASE WHEN transaction_type = 'debt' THEN amount END), 0)
                    AS total_debt,
                COALESCE(SUM(CASE WHEN transaction_type = 'payment' THEN amount END), 0)
                    AS total_paid
            FROM debt_transactions
            WHERE customer_id = ?
            """,
            (int(customer_id),),
        ).fetchone()
        remaining_balance = round(
            float(totals["total_debt"]) - float(totals["total_paid"]),
            2,
        )
        if payment_amount > remaining_balance:
            raise ValueError(
                f"Payment exceeds the remaining balance of {remaining_balance:.2f} MAD."
            )

        cursor = connection.execute(
            """
            INSERT INTO debt_transactions (
                customer_id, customer_name, transaction_type,
                amount, note, transaction_date
            )
            VALUES (?, ?, 'payment', ?, 'Customer payment', ?)
            """,
            (
                int(customer_id),
                customer["name"],
                round(float(payment_amount), 2),
                date_text,
            ),
        )
        return int(cursor.lastrowid)


def get_customer_balances() -> pd.DataFrame:
    with get_connection() as connection:
        return pd.read_sql_query(
            """
            SELECT
                c.id AS customer_id,
                c.name AS customer_name,
                COALESCE(c.phone, '') AS phone,
                ROUND(COALESCE(SUM(
                    CASE WHEN dt.transaction_type = 'debt' THEN dt.amount ELSE 0 END
                ), 0), 2) AS total_debt,
                ROUND(COALESCE(SUM(
                    CASE WHEN dt.transaction_type = 'payment' THEN dt.amount ELSE 0 END
                ), 0), 2) AS total_paid,
                ROUND(COALESCE(SUM(
                    CASE
                        WHEN dt.transaction_type = 'debt' THEN dt.amount
                        ELSE -dt.amount
                    END
                ), 0), 2) AS remaining_balance
            FROM customers c
            LEFT JOIN debt_transactions dt ON dt.customer_id = c.id
            GROUP BY c.id, c.name, c.phone
            ORDER BY remaining_balance DESC, c.name
            """,
            connection,
        )


def get_debt_transactions() -> pd.DataFrame:
    with get_connection() as connection:
        return pd.read_sql_query(
            """
            SELECT
                dt.id,
                dt.customer_id,
                dt.customer_name,
                COALESCE(c.phone, '') AS phone,
                dt.transaction_type,
                dt.amount,
                COALESCE(dt.note, '') AS note,
                dt.transaction_date
            FROM debt_transactions dt
            LEFT JOIN customers c ON c.id = dt.customer_id
            ORDER BY dt.transaction_date DESC, dt.id DESC
            """,
            connection,
        )


def record_restock(
    product_id: int,
    quantity_added: int,
    supplier_name: str,
    unit_buy_price: float,
    restock_date: date | str,
    update_buy_price: bool = True,
) -> int:
    clean_supplier = supplier_name.strip()
    if quantity_added <= 0:
        raise ValueError("Restock quantity must be greater than zero.")
    if not clean_supplier:
        raise ValueError("Supplier name is required.")
    if unit_buy_price < 0:
        raise ValueError("Unit buy price cannot be negative.")

    date_text = (
        restock_date.isoformat()
        if isinstance(restock_date, date)
        else str(restock_date)
    )

    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        product = connection.execute(
            "SELECT id, name FROM products WHERE id = ?",
            (int(product_id),),
        ).fetchone()
        if product is None:
            raise ValueError("Product not found.")

        if update_buy_price:
            connection.execute(
                """
                UPDATE products
                SET stock_quantity = stock_quantity + ?,
                    buy_price = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    int(quantity_added),
                    float(unit_buy_price),
                    int(product_id),
                ),
            )
        else:
            connection.execute(
                """
                UPDATE products
                SET stock_quantity = stock_quantity + ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (int(quantity_added), int(product_id)),
            )

        cursor = connection.execute(
            """
            INSERT INTO restocks (
                product_id, product_name, quantity_added, supplier_name,
                unit_buy_price, restock_date, updated_buy_price
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(product_id),
                product["name"],
                int(quantity_added),
                clean_supplier,
                round(float(unit_buy_price), 2),
                date_text,
                int(update_buy_price),
            ),
        )
        return int(cursor.lastrowid)


def get_restocks() -> pd.DataFrame:
    with get_connection() as connection:
        return pd.read_sql_query(
            """
            SELECT
                id,
                product_id,
                product_name,
                quantity_added,
                supplier_name,
                unit_buy_price,
                restock_date,
                updated_buy_price
            FROM restocks
            ORDER BY restock_date DESC, id DESC
            """,
            connection,
        )
