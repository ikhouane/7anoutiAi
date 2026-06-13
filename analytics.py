from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from db_adapter import get_customer_balances, get_products, get_sales


def _sales_with_dates(shop_id: str | None = None) -> pd.DataFrame:
    sales = get_sales(shop_id)
    if not sales.empty:
        sales = sales.copy()
        sales["sale_date"] = pd.to_datetime(
            sales["sale_date"],
            errors="coerce",
        ).dt.date
        sales = sales.dropna(subset=["sale_date"]).reset_index(drop=True)
    return sales


def get_dashboard_metrics(
    today: date | None = None,
    shop_id: str | None = None,
) -> dict[str, float | int]:
    today = today or date.today()
    products = get_products(shop_id)
    sales = _sales_with_dates(shop_id)
    today_sales = sales[sales["sale_date"] == today] if not sales.empty else sales

    return {
        "today_revenue": float(today_sales["revenue"].sum()) if not today_sales.empty else 0.0,
        "today_profit": float(today_sales["profit"].sum()) if not today_sales.empty else 0.0,
        "total_stock_value": (
            float((products["buy_price"] * products["stock_quantity"]).sum())
            if not products.empty
            else 0.0
        ),
        "low_stock_count": (
            int((products["stock_quantity"] <= products["low_stock_threshold"]).sum())
            if not products.empty
            else 0
        ),
    }


def get_low_stock_products(shop_id: str | None = None) -> pd.DataFrame:
    products = get_products(shop_id)
    if products.empty:
        return products
    return (
        products[products["stock_quantity"] <= products["low_stock_threshold"]]
        .sort_values(["stock_quantity", "name"])
        .reset_index(drop=True)
    )


def get_top_selling_products(
    limit: int = 10,
    shop_id: str | None = None,
) -> pd.DataFrame:
    sales = _sales_with_dates(shop_id)
    if sales.empty:
        return pd.DataFrame(
            columns=["product_name", "units_sold", "revenue", "profit"]
        )

    return (
        sales.groupby("product_name", as_index=False)
        .agg(
            units_sold=("quantity", "sum"),
            revenue=("revenue", "sum"),
            profit=("profit", "sum"),
        )
        .sort_values(["units_sold", "revenue"], ascending=False)
        .head(limit)
        .reset_index(drop=True)
    )


def get_weekly_report(
    today: date | None = None,
    shop_id: str | None = None,
) -> dict[str, object]:
    today = today or date.today()
    week_start = today - timedelta(days=today.weekday())
    sales = _sales_with_dates(shop_id)
    week_sales = sales[
        (sales["sale_date"] >= week_start) & (sales["sale_date"] <= today)
    ] if not sales.empty else sales

    empty_products = pd.DataFrame(
        columns=["product_name", "units_sold", "revenue", "profit"]
    )
    if week_sales.empty:
        return {
            "week_start": week_start,
            "week_end": today,
            "revenue": 0.0,
            "profit": 0.0,
            "sales_count": 0,
            "top_products": empty_products.copy(),
            "highest_profit_products": empty_products.copy(),
        }

    product_summary = (
        week_sales.groupby("product_name", as_index=False)
        .agg(
            units_sold=("quantity", "sum"),
            revenue=("revenue", "sum"),
            profit=("profit", "sum"),
        )
    )
    top_products = (
        product_summary.sort_values(
            ["units_sold", "revenue"],
            ascending=False,
        )
        .head(5)
        .reset_index(drop=True)
    )
    highest_profit_products = (
        product_summary.sort_values(
            ["profit", "revenue"],
            ascending=False,
        )
        .head(5)
        .reset_index(drop=True)
    )

    return {
        "week_start": week_start,
        "week_end": today,
        "revenue": float(week_sales["revenue"].sum()),
        "profit": float(week_sales["profit"].sum()),
        "sales_count": int(len(week_sales)),
        "top_products": top_products,
        "highest_profit_products": highest_profit_products,
    }


def get_total_unpaid_debt(shop_id: str | None = None) -> float:
    balances = get_customer_balances(shop_id)
    if balances.empty:
        return 0.0
    return float(balances["remaining_balance"].clip(lower=0).sum())


def get_restocking_recommendations(
    today: date | None = None,
    shop_id: str | None = None,
) -> pd.DataFrame:
    today = today or date.today()
    products = get_products(shop_id)
    sales = _sales_with_dates(shop_id)

    columns = [
        "name",
        "category",
        "stock_quantity",
        "low_stock_threshold",
        "units_sold_7d",
        "average_daily_sales",
        "estimated_days_until_stockout",
        "recommendation_reason",
    ]
    if products.empty:
        return pd.DataFrame(columns=columns)

    start_date = today - timedelta(days=6)
    recent_sales = sales[
        (sales["sale_date"] >= start_date) & (sales["sale_date"] <= today)
    ] if not sales.empty else sales

    if recent_sales.empty:
        recent_totals = pd.DataFrame(columns=["product_id", "units_sold_7d"])
    else:
        recent_totals = (
            recent_sales.dropna(subset=["product_id"])
            .groupby("product_id", as_index=False)["quantity"]
            .sum()
            .rename(columns={"quantity": "units_sold_7d"})
        )

    recommendations = products.merge(
        recent_totals,
        how="left",
        left_on="id",
        right_on="product_id",
    )
    recommendations["units_sold_7d"] = (
        recommendations["units_sold_7d"].fillna(0).astype(int)
    )
    recommendations["average_daily_sales"] = recommendations["units_sold_7d"] / 7
    recommendations["estimated_days_until_stockout"] = recommendations.apply(
        lambda row: (
            row["stock_quantity"] / row["average_daily_sales"]
            if row["average_daily_sales"] > 0
            else float("inf")
        ),
        axis=1,
    )

    below_threshold = (
        recommendations["stock_quantity"] <= recommendations["low_stock_threshold"]
    )
    running_out_soon = recommendations["estimated_days_until_stockout"] < 3
    recommendations = recommendations[below_threshold | running_out_soon].copy()

    def reason(row: pd.Series) -> str:
        low = row["stock_quantity"] <= row["low_stock_threshold"]
        soon = row["estimated_days_until_stockout"] < 3
        if low and soon:
            return "Low stock and likely to run out within 3 days"
        if low:
            return "Stock is at or below the low-stock threshold"
        return "Likely to run out within 3 days"

    recommendations["recommendation_reason"] = recommendations.apply(reason, axis=1)
    recommendations["average_daily_sales"] = recommendations[
        "average_daily_sales"
    ].round(2)
    recommendations["estimated_days_until_stockout"] = recommendations[
        "estimated_days_until_stockout"
    ].map(lambda value: round(value, 1) if value != float("inf") else None)

    return (
        recommendations[columns]
        .sort_values(
            ["estimated_days_until_stockout", "stock_quantity"],
            na_position="last",
        )
        .reset_index(drop=True)
    )
