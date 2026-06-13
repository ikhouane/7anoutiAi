from __future__ import annotations

import random
from datetime import date, timedelta

from database import get_connection, initialize_database


PRODUCTS = [
    ("Milk 1L", "Dairy", 7.00, 8.50, 8, 10),
    ("Yogurt", "Dairy", 2.20, 3.00, 16, 8),
    ("Bread", "Bakery", 1.00, 1.20, 7, 12),
    ("Sugar 1kg", "Groceries", 7.50, 9.00, 18, 8),
    ("Green Tea 200g", "Beverages", 14.00, 17.00, 12, 5),
    ("Coffee 250g", "Beverages", 22.00, 27.00, 9, 4),
    ("Cooking Oil 1L", "Groceries", 15.00, 18.00, 6, 8),
    ("Flour 1kg", "Groceries", 5.00, 6.50, 20, 7),
    ("Eggs (unit)", "Dairy", 1.10, 1.50, 24, 18),
    ("Water 1.5L", "Beverages", 4.00, 5.00, 14, 12),
    ("Soda 1L", "Beverages", 7.00, 9.00, 10, 8),
    ("Biscuits", "Snacks", 2.50, 3.50, 11, 10),
    ("Cheese portions", "Dairy", 8.00, 10.00, 5, 6),
    ("Tuna can", "Canned Food", 9.00, 12.00, 15, 6),
    ("Rice 1kg", "Groceries", 12.00, 15.00, 17, 7),
    ("Pasta 500g", "Groceries", 5.00, 6.50, 13, 6),
    ("Lentils 1kg", "Legumes", 13.00, 16.00, 9, 5),
    ("Chickpeas 1kg", "Legumes", 14.00, 17.00, 4, 5),
    ("Hand Soap", "Personal Care", 5.00, 7.00, 8, 5),
    ("Shampoo", "Personal Care", 18.00, 23.00, 7, 4),
    ("Laundry Detergent", "Cleaning", 16.00, 20.00, 5, 6),
    ("Dishwashing Liquid", "Cleaning", 9.00, 12.00, 10, 5),
    ("Chocolate Bar", "Snacks", 3.00, 4.50, 15, 8),
    ("Potato Chips", "Snacks", 4.00, 5.50, 12, 7),
]

# Higher weights make everyday products the demo's clear best sellers.
DAILY_SALES = {
    "Milk 1L": (5, 10),
    "Yogurt": (3, 8),
    "Bread": (8, 16),
    "Sugar 1kg": (1, 4),
    "Green Tea 200g": (0, 2),
    "Coffee 250g": (0, 2),
    "Cooking Oil 1L": (1, 4),
    "Flour 1kg": (1, 3),
    "Eggs (unit)": (8, 20),
    "Water 1.5L": (5, 12),
    "Soda 1L": (2, 7),
    "Biscuits": (3, 9),
    "Cheese portions": (1, 5),
    "Tuna can": (0, 3),
    "Rice 1kg": (1, 3),
    "Pasta 500g": (1, 4),
    "Lentils 1kg": (0, 2),
    "Chickpeas 1kg": (0, 2),
    "Hand Soap": (0, 2),
    "Shampoo": (0, 1),
    "Laundry Detergent": (0, 2),
    "Dishwashing Liquid": (0, 2),
    "Chocolate Bar": (2, 7),
    "Potato Chips": (2, 6),
}

CUSTOMERS = [
    ("Ahmed Benali", "0612345678"),
    ("Fatima Zahra", "0623456789"),
    ("Youssef Amrani", "0634567890"),
    ("Khadija El Idrissi", ""),
    ("Mohamed Alaoui", "0656789012"),
]

DEBT_TRANSACTIONS = [
    ("Ahmed Benali", "debt", 120.00, "Monthly groceries", 10),
    ("Ahmed Benali", "payment", 50.00, "Partial payment", 4),
    ("Fatima Zahra", "debt", 78.50, "Milk, oil, and household items", 8),
    ("Fatima Zahra", "payment", 30.00, "Partial payment", 2),
    ("Youssef Amrani", "debt", 45.00, "Groceries", 6),
    ("Youssef Amrani", "payment", 45.00, "Paid in full", 1),
    ("Khadija El Idrissi", "debt", 95.00, "Weekly household shopping", 5),
    ("Mohamed Alaoui", "debt", 32.00, "Bread, eggs, and tea", 3),
]

RESTOCK_HISTORY = [
    ("Milk 1L", 48, "Laiterie Atlas", 7.10, 12, 1),
    ("Bread", 80, "Boulangerie Al Amal", 1.00, 10, 0),
    ("Eggs (unit)", 120, "Ferme Chaouia", 1.15, 9, 1),
    ("Water 1.5L", 60, "Distributeur Ain", 4.00, 7, 0),
    ("Cooking Oil 1L", 24, "Grossiste Derb Omar", 15.20, 6, 1),
    ("Biscuits", 36, "Distributeur Bimo", 2.50, 4, 0),
    ("Laundry Detergent", 12, "Casa Hygiene", 16.50, 3, 1),
    ("Soda 1L", 36, "Boissons Maroc", 7.10, 1, 1),
]


def seed_database() -> None:
    initialize_database()
    random.seed(7)

    with get_connection() as connection:
        connection.execute("DELETE FROM debt_transactions")
        connection.execute("DELETE FROM customers")
        connection.execute("DELETE FROM restocks")
        connection.execute("DELETE FROM sales")
        connection.execute("DELETE FROM products")
        connection.execute(
            """
            DELETE FROM sqlite_sequence
            WHERE name IN (
                'products', 'sales', 'customers',
                'debt_transactions', 'restocks'
            )
            """
        )

        connection.executemany(
            """
            INSERT INTO products (
                name, category, buy_price, sell_price,
                stock_quantity, low_stock_threshold
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            PRODUCTS,
        )

        product_rows = connection.execute(
            "SELECT id, name, buy_price, sell_price FROM products"
        ).fetchall()
        product_ids = {row["name"]: int(row["id"]) for row in product_rows}

        sales_rows = []
        today = date.today()
        for days_ago in range(13, -1, -1):
            sale_date = today - timedelta(days=days_ago)
            weekend_boost = 1.15 if sale_date.weekday() >= 5 else 1.0

            for product in product_rows:
                minimum, maximum = DAILY_SALES[product["name"]]
                quantity = random.randint(minimum, maximum)
                quantity = round(quantity * weekend_boost)
                if quantity <= 0:
                    continue

                revenue = round(product["sell_price"] * quantity, 2)
                profit = round(
                    (product["sell_price"] - product["buy_price"]) * quantity,
                    2,
                )
                sales_rows.append(
                    (
                        product["id"],
                        product["name"],
                        quantity,
                        sale_date.isoformat(),
                        revenue,
                        profit,
                    )
                )

        connection.executemany(
            """
            INSERT INTO sales (
                product_id, product_name, quantity, sale_date, revenue, profit
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            sales_rows,
        )

        connection.executemany(
            "INSERT INTO customers (name, phone) VALUES (?, NULLIF(?, ''))",
            CUSTOMERS,
        )
        customer_rows = connection.execute(
            "SELECT id, name FROM customers"
        ).fetchall()
        customer_ids = {row["name"]: int(row["id"]) for row in customer_rows}

        debt_rows = [
            (
                customer_ids[customer_name],
                customer_name,
                transaction_type,
                amount,
                note,
                (today - timedelta(days=days_ago)).isoformat(),
            )
            for (
                customer_name,
                transaction_type,
                amount,
                note,
                days_ago,
            ) in DEBT_TRANSACTIONS
        ]
        connection.executemany(
            """
            INSERT INTO debt_transactions (
                customer_id, customer_name, transaction_type,
                amount, note, transaction_date
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            debt_rows,
        )

        restock_rows = [
            (
                product_ids[product_name],
                product_name,
                quantity_added,
                supplier_name,
                unit_buy_price,
                (today - timedelta(days=days_ago)).isoformat(),
                updated_buy_price,
            )
            for (
                product_name,
                quantity_added,
                supplier_name,
                unit_buy_price,
                days_ago,
                updated_buy_price,
            ) in RESTOCK_HISTORY
        ]
        connection.executemany(
            """
            INSERT INTO restocks (
                product_id, product_name, quantity_added, supplier_name,
                unit_buy_price, restock_date, updated_buy_price
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            restock_rows,
        )

    print(
        f"Seeded {len(PRODUCTS)} products, {len(sales_rows)} sales, "
        f"{len(debt_rows)} debt transactions, and "
        f"{len(restock_rows)} restocks into data/hanout.db."
    )


if __name__ == "__main__":
    seed_database()
