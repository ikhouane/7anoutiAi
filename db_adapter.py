from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

import database as sqlite_backend
from config import DATABASE_BACKEND


PRODUCT_COLUMNS = [
    "id",
    "name",
    "category",
    "buy_price",
    "sell_price",
    "stock_quantity",
    "low_stock_threshold",
]
SALES_COLUMNS = [
    "id",
    "product_id",
    "product_name",
    "quantity",
    "sale_date",
    "revenue",
    "profit",
]
CUSTOMER_BALANCE_COLUMNS = [
    "customer_id",
    "customer_name",
    "phone",
    "total_debt",
    "total_paid",
    "remaining_balance",
]
DEBT_TRANSACTION_COLUMNS = [
    "id",
    "customer_id",
    "customer_name",
    "phone",
    "transaction_type",
    "amount",
    "note",
    "transaction_date",
]
RESTOCK_COLUMNS = [
    "id",
    "product_id",
    "product_name",
    "quantity_added",
    "supplier_name",
    "unit_buy_price",
    "restock_date",
    "updated_buy_price",
]

_supabase_client: Any | None = None
_supabase_shop_id: str | None = None


def configure_supabase_context(client: Any, shop_id: str) -> None:
    """Set the authenticated client and shop used by Supabase operations."""
    global _supabase_client, _supabase_shop_id

    clean_shop_id = str(shop_id).strip()
    if not clean_shop_id:
        raise ValueError("A valid shop_id is required for Supabase operations.")

    _supabase_client = client
    _supabase_shop_id = clean_shop_id


def clear_supabase_context() -> None:
    global _supabase_client, _supabase_shop_id
    _supabase_client = None
    _supabase_shop_id = None


def _get_supabase_context() -> tuple[Any, str]:
    if _supabase_client is None or not _supabase_shop_id:
        raise RuntimeError(
            "Supabase database context is not configured. Log in and load a "
            "shop profile before accessing production data."
        )
    return _supabase_client, _supabase_shop_id


def _require_supabase_shop(shop_id: str | None) -> tuple[Any, str]:
    client, profile_shop_id = _get_supabase_context()
    requested_shop_id = str(shop_id or "").strip()
    if not requested_shop_id:
        raise ValueError("shop_id is required for Supabase operations.")
    if requested_shop_id != profile_shop_id:
        raise PermissionError(
            "The requested shop does not match the logged-in user's shop."
        )
    return client, profile_shop_id


def _supabase_product_error(action: str, exc: Exception) -> RuntimeError:
    message = str(exc).strip()
    lowered = message.lower()
    if "duplicate key" in lowered or "products_shop_id_name_key" in lowered:
        message = "A product with this name already exists in your shop."
    elif "row-level security" in lowered or "permission denied" in lowered:
        message = "You do not have permission to access this shop's products."
    elif not message:
        message = "Supabase did not return an error message."
    return RuntimeError(f"{action} failed: {message}")


def _supabase_debt_error(action: str, exc: Exception) -> RuntimeError:
    message = str(exc).strip()
    lowered = message.lower()
    if "row-level security" in lowered or "permission denied" in lowered:
        message = "You do not have permission to access this shop's debt records."
    elif not message:
        message = "Supabase did not return an error message."
    return RuntimeError(f"{action} failed: {message}")


def _supabase_restock_error(action: str, exc: Exception) -> RuntimeError:
    message = str(exc).strip()
    lowered = message.lower()
    if "row-level security" in lowered or "permission denied" in lowered:
        message = "You do not have permission to manage this shop's restocks."
    elif not message:
        message = "Supabase did not return an error message."
    return RuntimeError(f"{action} failed: {message}")


def _supabase_sales_error(action: str, exc: Exception) -> RuntimeError:
    message = str(exc).strip()
    lowered = message.lower()
    if "row-level security" in lowered or "permission denied" in lowered:
        message = "You do not have permission to access this shop's sales."
    elif not message:
        message = "Supabase did not return an error message."
    return RuntimeError(f"{action} failed: {message}")


def _unsupported_supabase(operation: str) -> RuntimeError:
    return RuntimeError(
        f"{operation} is not available in Supabase mode yet. "
        "Products, sales history, customer debts, restocks, and analytics "
        "have been migrated."
    )


def _validate_product(
    name: str,
    category: str,
    buy_price: float,
    sell_price: float,
    stock_quantity: int,
    low_stock_threshold: int,
) -> tuple[str, str]:
    clean_name = name.strip()
    clean_category = category.strip()
    if not clean_name or not clean_category:
        raise ValueError("Product name and category are required.")
    if buy_price < 0 or sell_price < 0:
        raise ValueError("Prices cannot be negative.")
    if stock_quantity < 0 or low_stock_threshold < 0:
        raise ValueError("Stock values cannot be negative.")
    return clean_name, clean_category


def _product_dataframe(rows: list[dict[str, Any]] | None) -> pd.DataFrame:
    products = pd.DataFrame(rows or [])
    if products.empty:
        return pd.DataFrame(columns=PRODUCT_COLUMNS)
    products = products.reindex(columns=PRODUCT_COLUMNS)
    for column in ("buy_price", "sell_price"):
        products[column] = pd.to_numeric(products[column], errors="coerce").fillna(0.0)
    for column in ("stock_quantity", "low_stock_threshold"):
        products[column] = (
            pd.to_numeric(products[column], errors="coerce").fillna(0).astype(int)
        )
    return products


def _date_text(value: date | str) -> str:
    return value.isoformat() if isinstance(value, date) else str(value)


def _get_supabase_customers(client: Any, shop_id: str) -> list[dict[str, Any]]:
    response = (
        client.table("customers")
        .select("id, name, phone")
        .eq("shop_id", shop_id)
        .order("name")
        .execute()
    )
    return response.data or []


def _get_supabase_debt_rows(client: Any, shop_id: str) -> list[dict[str, Any]]:
    response = (
        client.table("debt_transactions")
        .select(
            "id, customer_id, transaction_type, amount, note, transaction_date"
        )
        .eq("shop_id", shop_id)
        .order("transaction_date", desc=True)
        .execute()
    )
    return response.data or []


def initialize_database() -> None:
    if DATABASE_BACKEND == "sqlite":
        sqlite_backend.initialize_database()


def health_check(shop_id: str | None = None) -> dict[str, str | bool]:
    """Run a lightweight read-only check against the selected database."""
    try:
        if DATABASE_BACKEND == "sqlite":
            with sqlite_backend.get_connection() as connection:
                connection.execute("SELECT 1").fetchone()
        else:
            client, scoped_shop_id = _require_supabase_shop(shop_id)
            (
                client.table("shops")
                .select("id")
                .eq("id", scoped_shop_id)
                .limit(1)
                .execute()
            )
        return {
            "ok": True,
            "backend": DATABASE_BACKEND,
            "message": "Database connection healthy.",
        }
    except Exception as exc:
        return {
            "ok": False,
            "backend": DATABASE_BACKEND,
            "message": (
                f"Could not connect to the {DATABASE_BACKEND} database. "
                f"Check the database configuration and try again. Details: {exc}"
            ),
        }


def get_products(shop_id: str | None = None) -> pd.DataFrame:
    if DATABASE_BACKEND == "sqlite":
        return sqlite_backend.get_products()

    client, scoped_shop_id = _require_supabase_shop(shop_id)
    try:
        response = (
            client.table("products")
            .select(", ".join(PRODUCT_COLUMNS))
            .eq("shop_id", scoped_shop_id)
            .order("name")
            .execute()
        )
        return _product_dataframe(response.data)
    except Exception as exc:
        raise _supabase_product_error("Loading products", exc) from exc


def get_product(
    product_id: int | str,
    shop_id: str | None = None,
) -> dict[str, Any] | None:
    if DATABASE_BACKEND == "sqlite":
        return sqlite_backend.get_product(int(product_id))

    client, scoped_shop_id = _require_supabase_shop(shop_id)
    try:
        response = (
            client.table("products")
            .select(", ".join(PRODUCT_COLUMNS))
            .eq("id", str(product_id))
            .eq("shop_id", scoped_shop_id)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None
    except Exception as exc:
        raise _supabase_product_error("Loading the product", exc) from exc


def add_product(
    shop_id: str | None,
    name: str,
    category: str,
    buy_price: float,
    sell_price: float,
    stock_quantity: int,
    low_stock_threshold: int,
) -> int | str:
    if DATABASE_BACKEND == "sqlite":
        return sqlite_backend.add_product(
            name,
            category,
            buy_price,
            sell_price,
            stock_quantity,
            low_stock_threshold,
        )

    clean_name, clean_category = _validate_product(
        name,
        category,
        buy_price,
        sell_price,
        stock_quantity,
        low_stock_threshold,
    )
    client, scoped_shop_id = _require_supabase_shop(shop_id)
    try:
        response = (
            client.table("products")
            .insert(
                {
                    "shop_id": scoped_shop_id,
                    "name": clean_name,
                    "category": clean_category,
                    "buy_price": float(buy_price),
                    "sell_price": float(sell_price),
                    "stock_quantity": int(stock_quantity),
                    "low_stock_threshold": int(low_stock_threshold),
                }
            )
            .execute()
        )
        if not response.data:
            raise RuntimeError("Supabase did not return the new product.")
        return str(response.data[0]["id"])
    except Exception as exc:
        raise _supabase_product_error("Adding the product", exc) from exc


def update_product(
    shop_id: str | None,
    product_id: int | str,
    name: str,
    category: str,
    buy_price: float,
    sell_price: float,
    stock_quantity: int,
    low_stock_threshold: int,
) -> None:
    if DATABASE_BACKEND == "sqlite":
        sqlite_backend.update_product(
            int(product_id),
            name,
            category,
            buy_price,
            sell_price,
            stock_quantity,
            low_stock_threshold,
        )
        return

    clean_name, clean_category = _validate_product(
        name,
        category,
        buy_price,
        sell_price,
        stock_quantity,
        low_stock_threshold,
    )
    client, scoped_shop_id = _require_supabase_shop(shop_id)
    try:
        response = (
            client.table("products")
            .update(
                {
                    "name": clean_name,
                    "category": clean_category,
                    "buy_price": float(buy_price),
                    "sell_price": float(sell_price),
                    "stock_quantity": int(stock_quantity),
                    "low_stock_threshold": int(low_stock_threshold),
                }
            )
            .eq("id", str(product_id))
            .eq("shop_id", scoped_shop_id)
            .execute()
        )
        if not response.data:
            raise ValueError("Product not found in your shop.")
    except ValueError:
        raise
    except Exception as exc:
        raise _supabase_product_error("Updating the product", exc) from exc


def delete_product(shop_id: str | None, product_id: int | str) -> None:
    if DATABASE_BACKEND == "sqlite":
        sqlite_backend.delete_product(int(product_id))
        return

    client, scoped_shop_id = _require_supabase_shop(shop_id)
    try:
        response = (
            client.table("products")
            .delete()
            .eq("id", str(product_id))
            .eq("shop_id", scoped_shop_id)
            .execute()
        )
        if not response.data:
            raise ValueError("Product not found in your shop.")
    except ValueError:
        raise
    except Exception as exc:
        raise _supabase_product_error("Deleting the product", exc) from exc


def record_sale(
    product_id: int | str,
    quantity: int,
    sale_date: date | str,
) -> dict[str, float]:
    if DATABASE_BACKEND == "sqlite":
        return sqlite_backend.record_sale(int(product_id), quantity, sale_date)
    raise _unsupported_supabase("Sales recording")


def get_sales(shop_id: str | None = None) -> pd.DataFrame:
    if DATABASE_BACKEND == "sqlite":
        return sqlite_backend.get_sales()

    client, scoped_shop_id = _require_supabase_shop(shop_id)
    try:
        sales_response = (
            client.table("sales")
            .select("id, product_id, quantity, sale_date, revenue, profit")
            .eq("shop_id", scoped_shop_id)
            .order("sale_date", desc=True)
            .execute()
        )
        sales = pd.DataFrame(sales_response.data or [])
        if sales.empty:
            return pd.DataFrame(columns=SALES_COLUMNS)

        products_response = (
            client.table("products")
            .select("id, name")
            .eq("shop_id", scoped_shop_id)
            .execute()
        )
        products = pd.DataFrame(products_response.data or [])
        if products.empty:
            sales["product_name"] = "Deleted product"
        else:
            product_lookup = products.rename(
                columns={"id": "product_id", "name": "product_name"}
            )[["product_id", "product_name"]]
            sales = sales.merge(
                product_lookup,
                how="left",
                on="product_id",
            )
            sales["product_name"] = sales["product_name"].fillna("Deleted product")

        sales["quantity"] = (
            pd.to_numeric(sales["quantity"], errors="coerce").fillna(0).astype(int)
        )
        for column in ("revenue", "profit"):
            sales[column] = pd.to_numeric(
                sales[column],
                errors="coerce",
            ).fillna(0.0)
        return sales.reindex(columns=SALES_COLUMNS).reset_index(drop=True)
    except Exception as exc:
        raise _supabase_sales_error("Loading sales history", exc) from exc


def add_customer_debt(
    shop_id: str | None,
    customer_name: str,
    phone: str,
    amount: float,
    note: str,
    transaction_date: date | str,
) -> int | str:
    if DATABASE_BACKEND == "sqlite":
        return sqlite_backend.add_customer_debt(
            customer_name,
            phone,
            amount,
            note,
            transaction_date,
        )

    clean_name = customer_name.strip()
    clean_phone = phone.strip()
    clean_note = note.strip()
    if not clean_name:
        raise ValueError("Customer name is required.")
    if amount <= 0:
        raise ValueError("Debt amount must be greater than zero.")

    client, scoped_shop_id = _require_supabase_shop(shop_id)
    try:
        customers = _get_supabase_customers(client, scoped_shop_id)
        customer = next(
            (
                row
                for row in customers
                if str(row["name"]).strip().casefold() == clean_name.casefold()
            ),
            None,
        )

        if customer is None:
            customer_response = (
                client.table("customers")
                .insert(
                    {
                        "shop_id": scoped_shop_id,
                        "name": clean_name,
                        "phone": clean_phone or None,
                    }
                )
                .execute()
            )
            if not customer_response.data:
                raise RuntimeError("Supabase did not return the new customer.")
            customer = customer_response.data[0]
        elif clean_phone and clean_phone != (customer.get("phone") or ""):
            update_response = (
                client.table("customers")
                .update({"phone": clean_phone})
                .eq("id", str(customer["id"]))
                .eq("shop_id", scoped_shop_id)
                .execute()
            )
            if not update_response.data:
                raise RuntimeError("The existing customer could not be updated.")

        transaction_response = (
            client.table("debt_transactions")
            .insert(
                {
                    "shop_id": scoped_shop_id,
                    "customer_id": str(customer["id"]),
                    "transaction_type": "debt",
                    "amount": round(float(amount), 2),
                    "note": clean_note or None,
                    "transaction_date": _date_text(transaction_date),
                }
            )
            .execute()
        )
        if not transaction_response.data:
            raise RuntimeError("Supabase did not return the new debt transaction.")
        return str(transaction_response.data[0]["id"])
    except (PermissionError, ValueError):
        raise
    except Exception as exc:
        raise _supabase_debt_error("Adding customer debt", exc) from exc


def record_customer_payment(
    shop_id: str | None,
    customer_id: int | str,
    payment_amount: float,
    payment_date: date | str,
) -> int | str:
    if DATABASE_BACKEND == "sqlite":
        return sqlite_backend.record_customer_payment(
            int(customer_id),
            payment_amount,
            payment_date,
        )
    if payment_amount <= 0:
        raise ValueError("Payment amount must be greater than zero.")

    client, scoped_shop_id = _require_supabase_shop(shop_id)
    try:
        customer_response = (
            client.table("customers")
            .select("id, name")
            .eq("id", str(customer_id))
            .eq("shop_id", scoped_shop_id)
            .limit(1)
            .execute()
        )
        if not customer_response.data:
            raise ValueError("Customer not found in your shop.")

        transactions_response = (
            client.table("debt_transactions")
            .select("transaction_type, amount")
            .eq("shop_id", scoped_shop_id)
            .eq("customer_id", str(customer_id))
            .execute()
        )
        total_debt = sum(
            float(row["amount"])
            for row in transactions_response.data or []
            if row["transaction_type"] == "debt"
        )
        total_paid = sum(
            float(row["amount"])
            for row in transactions_response.data or []
            if row["transaction_type"] == "payment"
        )
        remaining_balance = round(total_debt - total_paid, 2)
        if payment_amount > remaining_balance:
            raise ValueError(
                f"Payment exceeds the remaining balance of "
                f"{remaining_balance:.2f} MAD."
            )

        payment_response = (
            client.table("debt_transactions")
            .insert(
                {
                    "shop_id": scoped_shop_id,
                    "customer_id": str(customer_id),
                    "transaction_type": "payment",
                    "amount": round(float(payment_amount), 2),
                    "note": "Customer payment",
                    "transaction_date": _date_text(payment_date),
                }
            )
            .execute()
        )
        if not payment_response.data:
            raise RuntimeError("Supabase did not return the new payment.")
        return str(payment_response.data[0]["id"])
    except (PermissionError, ValueError):
        raise
    except Exception as exc:
        raise _supabase_debt_error("Recording customer payment", exc) from exc


def get_customer_balances(shop_id: str | None = None) -> pd.DataFrame:
    if DATABASE_BACKEND == "sqlite":
        return sqlite_backend.get_customer_balances()

    client, scoped_shop_id = _require_supabase_shop(shop_id)
    try:
        customers = pd.DataFrame(_get_supabase_customers(client, scoped_shop_id))
        if customers.empty:
            return pd.DataFrame(columns=CUSTOMER_BALANCE_COLUMNS)

        debt_rows = pd.DataFrame(
            _get_supabase_debt_rows(client, scoped_shop_id)
        )
        customers = customers.rename(
            columns={"id": "customer_id", "name": "customer_name"}
        )
        customers["phone"] = customers["phone"].fillna("")

        if debt_rows.empty:
            customers["total_debt"] = 0.0
            customers["total_paid"] = 0.0
        else:
            debt_rows["amount"] = debt_rows["amount"].astype(float)
            totals = (
                debt_rows.pivot_table(
                    index="customer_id",
                    columns="transaction_type",
                    values="amount",
                    aggfunc="sum",
                    fill_value=0.0,
                )
                .reset_index()
                .rename(columns={"debt": "total_debt", "payment": "total_paid"})
            )
            for column in ("total_debt", "total_paid"):
                if column not in totals:
                    totals[column] = 0.0
            customers = customers.merge(
                totals[["customer_id", "total_debt", "total_paid"]],
                how="left",
                on="customer_id",
            )
            customers[["total_debt", "total_paid"]] = customers[
                ["total_debt", "total_paid"]
            ].fillna(0.0)

        customers["remaining_balance"] = (
            customers["total_debt"] - customers["total_paid"]
        ).round(2)
        customers[["total_debt", "total_paid"]] = customers[
            ["total_debt", "total_paid"]
        ].round(2)
        return (
            customers.reindex(columns=CUSTOMER_BALANCE_COLUMNS)
            .sort_values(
                ["remaining_balance", "customer_name"],
                ascending=[False, True],
            )
            .reset_index(drop=True)
        )
    except Exception as exc:
        raise _supabase_debt_error("Loading customer balances", exc) from exc


def get_debt_transactions(shop_id: str | None = None) -> pd.DataFrame:
    if DATABASE_BACKEND == "sqlite":
        return sqlite_backend.get_debt_transactions()

    client, scoped_shop_id = _require_supabase_shop(shop_id)
    try:
        customers = pd.DataFrame(_get_supabase_customers(client, scoped_shop_id))
        debt_rows = pd.DataFrame(_get_supabase_debt_rows(client, scoped_shop_id))
        if debt_rows.empty:
            return pd.DataFrame(columns=DEBT_TRANSACTION_COLUMNS)

        if customers.empty:
            debt_rows["customer_name"] = ""
            debt_rows["phone"] = ""
        else:
            customer_lookup = customers.rename(
                columns={"id": "customer_id", "name": "customer_name"}
            )[["customer_id", "customer_name", "phone"]]
            customer_lookup["phone"] = customer_lookup["phone"].fillna("")
            debt_rows = debt_rows.merge(
                customer_lookup,
                how="left",
                on="customer_id",
            )
            debt_rows[["customer_name", "phone"]] = debt_rows[
                ["customer_name", "phone"]
            ].fillna("")

        debt_rows["note"] = debt_rows["note"].fillna("")
        debt_rows["amount"] = debt_rows["amount"].astype(float)
        return debt_rows.reindex(columns=DEBT_TRANSACTION_COLUMNS).reset_index(
            drop=True
        )
    except Exception as exc:
        raise _supabase_debt_error("Loading debt history", exc) from exc


def record_restock(
    shop_id: str | None,
    product_id: int | str,
    quantity_added: int,
    supplier_name: str,
    unit_buy_price: float,
    restock_date: date | str,
    update_buy_price: bool = True,
) -> int | str:
    if DATABASE_BACKEND == "sqlite":
        return sqlite_backend.record_restock(
            int(product_id),
            quantity_added,
            supplier_name,
            unit_buy_price,
            restock_date,
            update_buy_price,
        )

    clean_supplier = supplier_name.strip()
    if quantity_added <= 0:
        raise ValueError("Restock quantity must be greater than zero.")
    if not clean_supplier:
        raise ValueError("Supplier name is required.")
    if unit_buy_price < 0:
        raise ValueError("Unit buy price cannot be negative.")

    client, scoped_shop_id = _require_supabase_shop(shop_id)
    try:
        restock_response = (
            client.rpc(
                "record_restock",
                {
                    "p_shop_id": scoped_shop_id,
                    "p_product_id": str(product_id),
                    "p_quantity_added": int(quantity_added),
                    "p_supplier_name": clean_supplier,
                    "p_unit_buy_price": round(float(unit_buy_price), 2),
                    "p_restock_date": _date_text(restock_date),
                    "p_update_buy_price": bool(update_buy_price),
                },
            )
            .execute()
        )
        restock_id = restock_response.data
        if isinstance(restock_id, list):
            restock_id = restock_id[0] if restock_id else None
        if not restock_id:
            raise RuntimeError("Supabase did not return the new restock.")
        return str(restock_id)
    except (PermissionError, ValueError):
        raise
    except Exception as exc:
        raise _supabase_restock_error("Recording the restock", exc) from exc


def get_restocks(shop_id: str | None = None) -> pd.DataFrame:
    if DATABASE_BACKEND == "sqlite":
        return sqlite_backend.get_restocks()

    client, scoped_shop_id = _require_supabase_shop(shop_id)
    try:
        restock_response = (
            client.table("restocks")
            .select(
                "id, product_id, quantity_added, supplier_name, "
                "unit_buy_price, restock_date, updated_buy_price"
            )
            .eq("shop_id", scoped_shop_id)
            .order("restock_date", desc=True)
            .execute()
        )
        restocks = pd.DataFrame(restock_response.data or [])
        if restocks.empty:
            return pd.DataFrame(columns=RESTOCK_COLUMNS)

        product_response = (
            client.table("products")
            .select("id, name")
            .eq("shop_id", scoped_shop_id)
            .execute()
        )
        products = pd.DataFrame(product_response.data or [])
        if products.empty:
            restocks["product_name"] = ""
        else:
            products = products.rename(
                columns={"id": "product_id", "name": "product_name"}
            )
            restocks = restocks.merge(
                products[["product_id", "product_name"]],
                how="left",
                on="product_id",
            )
            restocks["product_name"] = restocks["product_name"].fillna("")

        restocks["unit_buy_price"] = restocks["unit_buy_price"].astype(float)
        return restocks.reindex(columns=RESTOCK_COLUMNS).reset_index(drop=True)
    except Exception as exc:
        raise _supabase_restock_error("Loading restock history", exc) from exc
