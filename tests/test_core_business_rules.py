from datetime import date

import pytest

import database
import db_adapter


@pytest.fixture()
def sqlite_database(tmp_path, monkeypatch):
    database_path = tmp_path / "hanout-test.db"
    monkeypatch.setattr(database, "DB_PATH", database_path)
    monkeypatch.setattr(database, "DATABASE_BACKEND", "sqlite")
    monkeypatch.setattr(db_adapter, "DATABASE_BACKEND", "sqlite")
    database.initialize_database()
    return database


@pytest.mark.parametrize(
    "values",
    [
        ("", "Dairy", 5.0, 7.0, 10, 3),
        ("Milk", "", 5.0, 7.0, 10, 3),
        ("Milk", "Dairy", -1.0, 7.0, 10, 3),
        ("Milk", "Dairy", 5.0, -1.0, 10, 3),
        ("Milk", "Dairy", 5.0, 7.0, -1, 3),
        ("Milk", "Dairy", 5.0, 7.0, 10, -1),
    ],
)
def test_product_validation_rejects_invalid_values(sqlite_database, values):
    with pytest.raises(ValueError):
        sqlite_database.add_product(*values)


def test_sale_prevents_insufficient_stock(sqlite_database):
    product_id = sqlite_database.add_product(
        "Milk",
        "Dairy",
        5.0,
        7.0,
        2,
        1,
    )

    with pytest.raises(ValueError, match="Insufficient stock"):
        sqlite_database.record_sale(product_id, 3, date(2026, 6, 12))

    product = sqlite_database.get_product(product_id)
    assert product["stock_quantity"] == 2
    assert sqlite_database.get_sales().empty


def test_customer_payment_prevents_overpayment(sqlite_database):
    sqlite_database.add_customer_debt(
        "Amina",
        "",
        100.0,
        "Weekly groceries",
        date(2026, 6, 10),
    )
    customer_id = int(sqlite_database.get_customer_balances().iloc[0]["customer_id"])

    with pytest.raises(ValueError, match="exceeds the remaining balance"):
        sqlite_database.record_customer_payment(
            customer_id,
            101.0,
            date(2026, 6, 12),
        )

    balance = sqlite_database.get_customer_balances().iloc[0]
    assert balance["total_paid"] == 0.0
    assert balance["remaining_balance"] == 100.0


def test_restock_increases_product_stock(sqlite_database):
    product_id = sqlite_database.add_product(
        "Tea",
        "Drinks",
        20.0,
        25.0,
        4,
        3,
    )

    sqlite_database.record_restock(
        product_id,
        8,
        "Atlas Supplier",
        21.5,
        date(2026, 6, 12),
        True,
    )

    product = sqlite_database.get_product(product_id)
    assert product["stock_quantity"] == 12
    assert product["buy_price"] == 21.5
    assert len(sqlite_database.get_restocks()) == 1


def test_sale_calculates_revenue_and_profit(sqlite_database):
    product_id = sqlite_database.add_product(
        "Bread",
        "Bakery",
        1.2,
        2.0,
        20,
        5,
    )

    result = sqlite_database.record_sale(
        product_id,
        5,
        date(2026, 6, 12),
    )

    assert result == {"revenue": 10.0, "profit": 4.0}
    product = sqlite_database.get_product(product_id)
    assert product["stock_quantity"] == 15


def test_sqlite_health_check(sqlite_database):
    result = db_adapter.health_check()

    assert result["ok"] is True
    assert result["backend"] == "sqlite"
