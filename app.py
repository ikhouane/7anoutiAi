from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from auth import (
    create_shop_and_profile,
    get_authenticated_client,
    get_logged_in_user,
    get_user_profile,
    login,
    logout,
    signup,
)
from analytics import (
    get_dashboard_metrics,
    get_low_stock_products,
    get_restocking_recommendations,
    get_total_unpaid_debt,
    get_top_selling_products,
    get_weekly_report,
)
from config import DATABASE_BACKEND
from db_adapter import (
    add_product,
    add_customer_debt,
    configure_supabase_context,
    delete_product,
    get_customer_balances,
    get_debt_transactions,
    get_products,
    get_restocks,
    get_sales,
    health_check,
    initialize_database,
    record_customer_payment,
    record_restock,
    record_sale,
    update_product,
)


st.set_page_config(
    page_title="7anoutiAI",
    page_icon="🏪",
    layout="wide",
)

active_shop_id: str | None = None
active_user_email = ""
active_shop_name = "Local SQLite demo"


def show_authentication() -> None:
    st.title("7anoutiAI")
    st.caption("Sign in to access your shop.")

    login_tab, signup_tab = st.tabs(["Login", "Create account"])
    with login_tab:
        with st.form("supabase_login_form"):
            login_email = st.text_input("Email", key="login_email")
            login_password = st.text_input(
                "Password",
                type="password",
                key="login_password",
            )
            login_submitted = st.form_submit_button("Login", type="primary")

        if login_submitted:
            try:
                login(login_email, login_password, st.session_state)
                st.success("Login successful.")
                st.rerun()
            except (RuntimeError, ValueError) as exc:
                st.error(str(exc))

    with signup_tab:
        with st.form("supabase_signup_form"):
            signup_email = st.text_input("Email", key="signup_email")
            signup_password = st.text_input(
                "Password",
                type="password",
                key="signup_password",
            )
            signup_submitted = st.form_submit_button(
                "Create account",
                type="primary",
            )

        if signup_submitted:
            try:
                result = signup(signup_email, signup_password, st.session_state)
                if result["requires_email_confirmation"]:
                    st.success(
                        "Account created. Check your email to confirm the account, "
                        "then return here to log in."
                    )
                else:
                    st.success("Account created and logged in.")
                    st.rerun()
            except (RuntimeError, ValueError) as exc:
                st.error(str(exc))


def show_shop_onboarding() -> None:
    user = get_logged_in_user(st.session_state)
    st.title("Set up your hanout")
    st.caption(f"Create the shop linked to {user['email']}.")

    with st.form("shop_onboarding_form"):
        shop_name = st.text_input("Shop name")
        full_name = st.text_input("Your name (optional)")
        submitted = st.form_submit_button("Create shop", type="primary")

    if submitted:
        try:
            create_shop_and_profile(
                shop_name,
                full_name,
                st.session_state,
            )
            st.success("Shop created successfully.")
            st.rerun()
        except (RuntimeError, ValueError) as exc:
            st.error(str(exc))


if DATABASE_BACKEND == "supabase":
    if get_logged_in_user(st.session_state) is None:
        show_authentication()
        st.stop()

    try:
        profile = get_user_profile(st.session_state)
    except RuntimeError as exc:
        st.error(str(exc))
        if st.button("Return to login"):
            logout(st.session_state)
            st.rerun()
        st.stop()

    if profile is None:
        show_shop_onboarding()
        if st.button("Logout"):
            logout(st.session_state)
            st.rerun()
        st.stop()

    configure_supabase_context(
        get_authenticated_client(st.session_state),
        profile["shop_id"],
    )
    active_shop_id = str(profile["shop_id"])

    user = get_logged_in_user(st.session_state)
    active_user_email = str(user["email"])
    active_shop_name = str(profile.get("shop_name") or "Unnamed shop")

try:
    initialize_database()
except RuntimeError as exc:
    st.error(f"Database startup failed. {exc}")
    st.stop()

database_health = health_check(active_shop_id)
with st.sidebar:
    st.markdown("**System status**")
    st.caption(f"Database backend: {DATABASE_BACKEND}")
    if DATABASE_BACKEND == "supabase":
        st.caption(f"Logged-in user: {active_user_email}")
        st.caption(f"Current shop: {active_shop_name}")
    if database_health["ok"]:
        st.success("Database connected")
    else:
        st.error(str(database_health["message"]))
    if DATABASE_BACKEND == "supabase":
        if st.button("Logout", key="supabase_logout"):
            logout(st.session_state)
            st.rerun()


def money(value: float) -> str:
    return f"{value:,.2f} MAD"


def show_table(
    data: pd.DataFrame,
    column_config: dict | None = None,
    empty_message: str = "No records yet. Add data to see it here.",
) -> None:
    if data.empty:
        st.info(empty_message)
        return
    st.dataframe(
        data,
        width="stretch",
        hide_index=True,
        column_config=column_config,
    )


def download_csv(label: str, data: pd.DataFrame, filename: str, key: str) -> None:
    st.download_button(
        label,
        data.to_csv(index=False).encode("utf-8"),
        file_name=filename,
        mime="text/csv",
        key=key,
        disabled=data.empty,
    )


def show_supabase_product_management(shop_id: str) -> None:
    st.subheader("Add product")
    with st.form("supabase_add_product_form", clear_on_submit=True):
        add_left, add_middle, add_right = st.columns(3)
        new_name = add_left.text_input("Name")
        new_category = add_middle.text_input("Category")
        new_stock = add_right.number_input("Stock quantity", min_value=0, step=1)
        new_buy_price = add_left.number_input(
            "Buy price (MAD)", min_value=0.0, step=0.5, format="%.2f"
        )
        new_sell_price = add_middle.number_input(
            "Sell price (MAD)", min_value=0.0, step=0.5, format="%.2f"
        )
        new_threshold = add_right.number_input(
            "Low-stock threshold", min_value=0, step=1, value=5
        )
        add_submitted = st.form_submit_button("Add product", type="primary")

    if add_submitted:
        try:
            add_product(
                shop_id,
                new_name,
                new_category,
                new_buy_price,
                new_sell_price,
                int(new_stock),
                int(new_threshold),
            )
            st.success(f'Added "{new_name.strip()}".')
            st.rerun()
        except (PermissionError, RuntimeError, ValueError) as exc:
            st.error(str(exc))

    st.subheader("All products")
    try:
        products = get_products(shop_id)
    except (PermissionError, RuntimeError, ValueError) as exc:
        st.error(str(exc))
        return

    show_table(
        products,
        {
            "id": "ID",
            "name": "Product",
            "category": "Category",
            "buy_price": st.column_config.NumberColumn("Buy price", format="%.2f MAD"),
            "sell_price": st.column_config.NumberColumn("Sell price", format="%.2f MAD"),
            "stock_quantity": "Stock",
            "low_stock_threshold": "Low-stock threshold",
        },
    )
    download_csv(
        "Download products CSV",
        products,
        "7anoutiai_products.csv",
        "download_supabase_products",
    )

    if products.empty:
        return

    product_options = {
        f'{row["name"]} (ID {row["id"]})': str(row["id"])
        for _, row in products.iterrows()
    }

    st.subheader("Edit product")
    selected_edit_label = st.selectbox(
        "Choose a product to edit",
        list(product_options),
        key="supabase_edit_product_select",
    )
    selected_edit_id = product_options[selected_edit_label]
    selected_product = products.loc[products["id"] == selected_edit_id].iloc[0]

    with st.form("supabase_edit_product_form"):
        edit_left, edit_middle, edit_right = st.columns(3)
        edit_name = edit_left.text_input(
            "Name", value=str(selected_product["name"])
        )
        edit_category = edit_middle.text_input(
            "Category", value=str(selected_product["category"])
        )
        edit_stock = edit_right.number_input(
            "Stock quantity",
            min_value=0,
            step=1,
            value=int(selected_product["stock_quantity"]),
        )
        edit_buy_price = edit_left.number_input(
            "Buy price (MAD)",
            min_value=0.0,
            step=0.5,
            format="%.2f",
            value=float(selected_product["buy_price"]),
        )
        edit_sell_price = edit_middle.number_input(
            "Sell price (MAD)",
            min_value=0.0,
            step=0.5,
            format="%.2f",
            value=float(selected_product["sell_price"]),
        )
        edit_threshold = edit_right.number_input(
            "Low-stock threshold",
            min_value=0,
            step=1,
            value=int(selected_product["low_stock_threshold"]),
        )
        edit_submitted = st.form_submit_button("Save changes", type="primary")

    if edit_submitted:
        try:
            update_product(
                shop_id,
                selected_edit_id,
                edit_name,
                edit_category,
                edit_buy_price,
                edit_sell_price,
                int(edit_stock),
                int(edit_threshold),
            )
            st.success("Product updated.")
            st.rerun()
        except (PermissionError, RuntimeError, ValueError) as exc:
            st.error(str(exc))

    st.subheader("Delete product")
    st.warning("Deleting a product removes it from your shop inventory.")
    selected_delete_label = st.selectbox(
        "Choose a product to delete",
        list(product_options),
        key="supabase_delete_product_select",
    )
    confirm_delete = st.checkbox(
        "I understand that this product will be removed.",
        key="supabase_confirm_product_delete",
    )
    if st.button(
        "Delete product",
        disabled=not confirm_delete,
        type="secondary",
        key="supabase_delete_product",
    ):
        try:
            delete_product(shop_id, product_options[selected_delete_label])
            st.success("Product deleted.")
            st.rerun()
        except (PermissionError, RuntimeError, ValueError) as exc:
            st.error(str(exc))


def show_supabase_customer_debts(shop_id: str) -> None:
    st.subheader("Customer debt notebook")
    try:
        balances = get_customer_balances(shop_id)
    except (PermissionError, RuntimeError, ValueError) as exc:
        st.error(str(exc))
        return

    total_unpaid = (
        float(balances["remaining_balance"].clip(lower=0).sum())
        if not balances.empty
        else 0.0
    )
    st.metric("Total unpaid debt", money(total_unpaid))

    debt_form_column, payment_form_column = st.columns(2)
    with debt_form_column:
        st.markdown("**Add customer debt**")
        with st.form("supabase_add_customer_debt_form", clear_on_submit=True):
            debt_customer_name = st.text_input(
                "Customer name",
                key="supabase_debt_customer_name",
            )
            debt_phone = st.text_input(
                "Phone (optional)",
                key="supabase_debt_phone",
            )
            debt_amount = st.number_input(
                "Debt amount (MAD)",
                min_value=0.0,
                step=1.0,
                format="%.2f",
                key="supabase_debt_amount",
            )
            debt_note = st.text_input("Note", key="supabase_debt_note")
            debt_date = st.date_input(
                "Debt date",
                value=date.today(),
                key="supabase_debt_date",
            )
            debt_submitted = st.form_submit_button("Add debt", type="primary")

        if debt_submitted:
            try:
                add_customer_debt(
                    shop_id,
                    debt_customer_name,
                    debt_phone,
                    debt_amount,
                    debt_note,
                    debt_date,
                )
                st.success("Customer debt recorded.")
                st.rerun()
            except (PermissionError, RuntimeError, ValueError) as exc:
                st.error(str(exc))

    unpaid_balances = (
        balances[balances["remaining_balance"] > 0].copy()
        if not balances.empty
        else balances
    )
    with payment_form_column:
        st.markdown("**Record customer payment**")
        if unpaid_balances.empty:
            st.info("There are no unpaid customer balances.")
        else:
            payment_options = {
                (
                    f"{row['customer_name']} - "
                    f"{money(float(row['remaining_balance']))} due"
                ): str(row["customer_id"])
                for _, row in unpaid_balances.iterrows()
            }
            with st.form(
                "supabase_record_customer_payment_form",
                clear_on_submit=True,
            ):
                payment_customer_label = st.selectbox(
                    "Customer",
                    list(payment_options),
                    key="supabase_payment_customer",
                )
                payment_amount = st.number_input(
                    "Payment amount (MAD)",
                    min_value=0.0,
                    step=1.0,
                    format="%.2f",
                    key="supabase_payment_amount",
                )
                payment_date = st.date_input(
                    "Payment date",
                    value=date.today(),
                    key="supabase_payment_date",
                )
                payment_submitted = st.form_submit_button(
                    "Record payment",
                    type="primary",
                )

            if payment_submitted:
                try:
                    record_customer_payment(
                        shop_id,
                        payment_options[payment_customer_label],
                        payment_amount,
                        payment_date,
                    )
                    st.success("Customer payment recorded.")
                    st.rerun()
                except (PermissionError, RuntimeError, ValueError) as exc:
                    st.error(str(exc))

    st.subheader("Customer balances")
    show_table(
        balances,
        {
            "customer_id": "Customer ID",
            "customer_name": "Customer",
            "phone": "Phone",
            "total_debt": st.column_config.NumberColumn(
                "Total debt", format="%.2f MAD"
            ),
            "total_paid": st.column_config.NumberColumn(
                "Total paid", format="%.2f MAD"
            ),
            "remaining_balance": st.column_config.NumberColumn(
                "Remaining balance", format="%.2f MAD"
            ),
        },
    )

    st.subheader("Debt transactions")
    try:
        debt_transactions = get_debt_transactions(shop_id)
    except (PermissionError, RuntimeError, ValueError) as exc:
        st.error(str(exc))
        return

    show_table(
        debt_transactions,
        {
            "customer_name": "Customer",
            "phone": "Phone",
            "transaction_type": "Type",
            "amount": st.column_config.NumberColumn("Amount", format="%.2f MAD"),
            "note": "Note",
            "transaction_date": "Date",
        },
    )
    download_csv(
        "Download debts CSV",
        debt_transactions,
        "7anoutiai_debts.csv",
        "download_supabase_debts",
    )


def show_supabase_restock_management(shop_id: str) -> None:
    st.subheader("Add stock")
    try:
        products = get_products(shop_id)
    except (PermissionError, RuntimeError, ValueError) as exc:
        st.error(str(exc))
        return

    if products.empty:
        st.info("Add a product before recording a restock.")
    else:
        restock_options = {
            f'{row["name"]} - {row["stock_quantity"]} in stock': str(row["id"])
            for _, row in products.iterrows()
        }
        selected_restock_label = st.selectbox(
            "Product to restock",
            list(restock_options),
            key="supabase_restock_product_select",
        )
        selected_restock_id = restock_options[selected_restock_label]
        selected_restock_product = products.loc[
            products["id"] == selected_restock_id
        ].iloc[0]

        with st.form("supabase_record_restock_form", clear_on_submit=True):
            restock_left, restock_right = st.columns(2)
            quantity_added = restock_left.number_input(
                "Quantity added",
                min_value=1,
                step=1,
                value=1,
                key="supabase_restock_quantity",
            )
            supplier_name = restock_right.text_input(
                "Supplier name",
                key="supabase_restock_supplier",
            )
            unit_buy_price = restock_left.number_input(
                "Unit buy price (MAD)",
                min_value=0.0,
                step=0.5,
                format="%.2f",
                value=float(selected_restock_product["buy_price"]),
                key="supabase_restock_buy_price",
            )
            restock_date = restock_right.date_input(
                "Restock date",
                value=date.today(),
                key="supabase_restock_date",
            )
            should_update_buy_price = st.checkbox(
                "Update the product's buy price to this new price",
                value=True,
                key="supabase_restock_update_price",
            )
            restock_submitted = st.form_submit_button(
                "Save restock",
                type="primary",
            )

        if restock_submitted:
            try:
                record_restock(
                    shop_id,
                    selected_restock_id,
                    int(quantity_added),
                    supplier_name,
                    unit_buy_price,
                    restock_date,
                    should_update_buy_price,
                )
                st.success("Restock saved and product stock updated.")
                st.rerun()
            except (PermissionError, RuntimeError, ValueError) as exc:
                st.error(str(exc))

    st.subheader("Restocking recommendations")
    st.caption(
        "Based on current stock and average daily sales during the last 7 days."
    )
    try:
        recommendations = get_restocking_recommendations(shop_id=shop_id)
    except (PermissionError, RuntimeError, ValueError) as exc:
        st.error(str(exc))
        recommendations = pd.DataFrame()
    show_table(
        recommendations,
        {
            "name": "Product",
            "category": "Category",
            "stock_quantity": "Stock",
            "low_stock_threshold": "Low-stock threshold",
            "units_sold_7d": "Units sold (7 days)",
            "average_daily_sales": st.column_config.NumberColumn(
                "Average daily sales", format="%.2f"
            ),
            "estimated_days_until_stockout": st.column_config.NumberColumn(
                "Estimated days left", format="%.1f"
            ),
            "recommendation_reason": "Reason",
        },
    )

    st.subheader("Restock history")
    try:
        restocks = get_restocks(shop_id)
    except (PermissionError, RuntimeError, ValueError) as exc:
        st.error(str(exc))
        return

    if not restocks.empty:
        restocks["updated_buy_price"] = restocks["updated_buy_price"].map(
            {True: "Yes", False: "No", 1: "Yes", 0: "No"}
        )
    show_table(
        restocks,
        {
            "product_name": "Product",
            "quantity_added": "Quantity added",
            "supplier_name": "Supplier",
            "unit_buy_price": st.column_config.NumberColumn(
                "Unit buy price", format="%.2f MAD"
            ),
            "restock_date": "Date",
            "updated_buy_price": "Buy price updated",
        },
    )
    download_csv(
        "Download restocks CSV",
        restocks,
        "7anoutiai_restocks.csv",
        "download_supabase_restocks",
    )


def assistant_answer(question: str, shop_id: str | None = None) -> str:
    normalized = question.strip().lower()

    if "restock" in normalized:
        recommendations = get_restocking_recommendations(shop_id=shop_id)
        if recommendations.empty:
            return "No products need restocking right now."
        items = recommendations.head(8).apply(
            lambda row: (
                f"{row['name']} ({row['stock_quantity']} left: "
                f"{row['recommendation_reason']})"
            ),
            axis=1,
        )
        return "Restock these products: " + "; ".join(items.tolist()) + "."

    if "best" in normalized and "product" in normalized:
        top_products = get_top_selling_products(5, shop_id)
        if top_products.empty:
            return "There are no sales yet, so I cannot rank products."
        items = top_products.apply(
            lambda row: f"{row['product_name']} ({int(row['units_sold'])} units)",
            axis=1,
        )
        return "Your best-selling products are: " + "; ".join(items.tolist()) + "."

    if "profit" in normalized and ("week" in normalized or "weekly" in normalized):
        report = get_weekly_report(shop_id=shop_id)
        return f"Profit this week is {money(float(report['profit']))}."

    if "profit" in normalized and ("today" in normalized or "daily" in normalized):
        metrics = get_dashboard_metrics(shop_id=shop_id)
        return f"Profit today is {money(float(metrics['today_profit']))}."

    if "who" in normalized and ("owe" in normalized or "debt" in normalized):
        balances = get_customer_balances(shop_id)
        unpaid = balances[balances["remaining_balance"] > 0]
        if unpaid.empty:
            return "No customers currently owe money."
        items = unpaid.head(8).apply(
            lambda row: (
                f"{row['customer_name']} ({money(float(row['remaining_balance']))})"
            ),
            axis=1,
        )
        return "Customers with unpaid balances: " + "; ".join(items.tolist()) + "."

    if "unpaid" in normalized or ("total" in normalized and "debt" in normalized):
        return (
            "Total unpaid customer debt is "
            f"{money(get_total_unpaid_debt(shop_id))}."
        )

    if "low" in normalized and "stock" in normalized:
        low_stock = get_low_stock_products(shop_id)
        if low_stock.empty:
            return "There are no low-stock products right now."
        items = low_stock.apply(
            lambda row: f"{row['name']} ({int(row['stock_quantity'])} left)",
            axis=1,
        )
        return "Low-stock products: " + "; ".join(items.tolist()) + "."

    return (
        "Try asking: What should I restock? What are my best products? "
        "How much profit today? How much profit this week? Who owes me money? "
        "What is my total unpaid debt? Or show low stock products."
    )


def show_dashboard(shop_id: str | None = None, key_prefix: str = "") -> None:
    try:
        metrics = get_dashboard_metrics(shop_id=shop_id)
        low_stock = get_low_stock_products(shop_id)
        top_sellers = get_top_selling_products(shop_id=shop_id)
        weekly_report = get_weekly_report(shop_id=shop_id)
    except (PermissionError, RuntimeError, ValueError) as exc:
        st.error(str(exc))
        return

    metric_columns = st.columns(4)
    metric_columns[0].metric("Today's revenue", money(metrics["today_revenue"]))
    metric_columns[1].metric("Today's profit", money(metrics["today_profit"]))
    metric_columns[2].metric(
        "Total stock value",
        money(metrics["total_stock_value"]),
    )
    metric_columns[3].metric("Low-stock products", metrics["low_stock_count"])

    st.subheader("Low-stock products")
    show_table(
        low_stock[
            [
                "name",
                "category",
                "stock_quantity",
                "low_stock_threshold",
                "buy_price",
                "sell_price",
            ]
        ] if not low_stock.empty else low_stock,
        {
            "name": "Product",
            "category": "Category",
            "stock_quantity": "Stock",
            "low_stock_threshold": "Low-stock threshold",
            "buy_price": st.column_config.NumberColumn(
                "Buy price",
                format="%.2f MAD",
            ),
            "sell_price": st.column_config.NumberColumn(
                "Sell price",
                format="%.2f MAD",
            ),
        },
    )

    st.subheader("Top selling products")
    show_table(
        top_sellers,
        {
            "product_name": "Product",
            "units_sold": "Units sold",
            "revenue": st.column_config.NumberColumn(
                "Revenue",
                format="%.2f MAD",
            ),
            "profit": st.column_config.NumberColumn(
                "Profit",
                format="%.2f MAD",
            ),
        },
    )

    st.subheader("Weekly report")
    st.caption(
        f"{weekly_report['week_start'].isoformat()} to "
        f"{weekly_report['week_end'].isoformat()}"
    )
    weekly_columns = st.columns(3)
    weekly_columns[0].metric(
        "Revenue this week",
        money(float(weekly_report["revenue"])),
    )
    weekly_columns[1].metric(
        "Profit this week",
        money(float(weekly_report["profit"])),
    )
    weekly_columns[2].metric(
        "Sales this week",
        int(weekly_report["sales_count"]),
    )

    weekly_left, weekly_right = st.columns(2)
    with weekly_left:
        st.markdown("**Top 5 products this week**")
        show_table(
            weekly_report["top_products"],
            {
                "product_name": "Product",
                "units_sold": "Units sold",
                "revenue": st.column_config.NumberColumn(
                    "Revenue",
                    format="%.2f MAD",
                ),
                "profit": st.column_config.NumberColumn(
                    "Profit",
                    format="%.2f MAD",
                ),
            },
        )
    with weekly_right:
        st.markdown("**Highest-profit products this week**")
        show_table(
            weekly_report["highest_profit_products"],
            {
                "product_name": "Product",
                "units_sold": "Units sold",
                "revenue": st.column_config.NumberColumn(
                    "Revenue",
                    format="%.2f MAD",
                ),
                "profit": st.column_config.NumberColumn(
                    "Profit",
                    format="%.2f MAD",
                ),
            },
        )

    st.subheader("Simple assistant")
    st.caption("Rule-based answers using your shop data. No external API is used.")
    with st.form(f"{key_prefix}assistant_form"):
        assistant_question = st.text_input(
            "Ask a question",
            placeholder="What should I restock?",
            key=f"{key_prefix}assistant_question",
        )
        assistant_submitted = st.form_submit_button("Ask")
    answer_key = f"{key_prefix}assistant_answer"
    if assistant_submitted:
        try:
            st.session_state[answer_key] = assistant_answer(
                assistant_question,
                shop_id,
            )
        except (PermissionError, RuntimeError, ValueError) as exc:
            st.session_state[answer_key] = f"I could not load shop data: {exc}"
    if st.session_state.get(answer_key):
        st.info(st.session_state[answer_key])


def show_sales_history(shop_id: str | None = None, key_prefix: str = "") -> None:
    st.subheader("Sales history")
    try:
        sales = get_sales(shop_id)
    except (PermissionError, RuntimeError, ValueError) as exc:
        st.error(str(exc))
        return

    show_table(
        sales,
        {
            "product_name": "Product",
            "quantity": "Quantity",
            "sale_date": "Date",
            "revenue": st.column_config.NumberColumn(
                "Revenue",
                format="%.2f MAD",
            ),
            "profit": st.column_config.NumberColumn(
                "Profit",
                format="%.2f MAD",
            ),
        },
    )
    download_csv(
        "Download sales CSV",
        sales,
        "7anoutiai_sales.csv",
        f"{key_prefix}download_sales",
    )


if DATABASE_BACKEND == "supabase":
    st.title("7anoutiAI")
    st.caption("Shop management for your authenticated hanout")
    st.info(
        "Sales history and analytics are available. Sale recording remains "
        "disabled until its stock-update transaction is migrated safely."
    )
    (
        supabase_dashboard_tab,
        supabase_products_tab,
        supabase_sales_tab,
        supabase_debts_tab,
        supabase_restock_tab,
    ) = st.tabs(
        ["Dashboard", "Products", "Sales", "Customer Debts", "Restock"]
    )
    with supabase_dashboard_tab:
        show_dashboard(active_shop_id, "supabase_")
    with supabase_products_tab:
        show_supabase_product_management(active_shop_id)
    with supabase_sales_tab:
        show_sales_history(active_shop_id, "supabase_")
    with supabase_debts_tab:
        show_supabase_customer_debts(active_shop_id)
    with supabase_restock_tab:
        show_supabase_restock_management(active_shop_id)
    st.stop()

st.title("7anoutiAI")
st.caption("Simple stock, sales, and restocking management for Moroccan hanouts")

dashboard_tab, products_tab, sales_tab, debts_tab, restock_tab = st.tabs(
    ["Dashboard", "Products", "Sales", "Customer Debts", "Restock"]
)

with dashboard_tab:
    metrics = get_dashboard_metrics()
    metric_columns = st.columns(4)
    metric_columns[0].metric("Today's revenue", money(metrics["today_revenue"]))
    metric_columns[1].metric("Today's profit", money(metrics["today_profit"]))
    metric_columns[2].metric(
        "Total stock value", money(metrics["total_stock_value"])
    )
    metric_columns[3].metric("Low-stock products", metrics["low_stock_count"])

    st.subheader("Low-stock products")
    low_stock = get_low_stock_products()
    show_table(
        low_stock[
            [
                "name",
                "category",
                "stock_quantity",
                "low_stock_threshold",
                "buy_price",
                "sell_price",
            ]
        ] if not low_stock.empty else low_stock,
        {
            "name": "Product",
            "category": "Category",
            "stock_quantity": "Stock",
            "low_stock_threshold": "Low-stock threshold",
            "buy_price": st.column_config.NumberColumn("Buy price", format="%.2f MAD"),
            "sell_price": st.column_config.NumberColumn("Sell price", format="%.2f MAD"),
        },
    )

    st.subheader("Top selling products")
    top_sellers = get_top_selling_products()
    show_table(
        top_sellers,
        {
            "product_name": "Product",
            "units_sold": "Units sold",
            "revenue": st.column_config.NumberColumn("Revenue", format="%.2f MAD"),
            "profit": st.column_config.NumberColumn("Profit", format="%.2f MAD"),
        },
    )

    st.subheader("Weekly report")
    weekly_report = get_weekly_report()
    st.caption(
        f"{weekly_report['week_start'].isoformat()} to "
        f"{weekly_report['week_end'].isoformat()}"
    )
    weekly_columns = st.columns(3)
    weekly_columns[0].metric(
        "Revenue this week", money(float(weekly_report["revenue"]))
    )
    weekly_columns[1].metric(
        "Profit this week", money(float(weekly_report["profit"]))
    )
    weekly_columns[2].metric("Sales this week", int(weekly_report["sales_count"]))

    weekly_left, weekly_right = st.columns(2)
    with weekly_left:
        st.markdown("**Top 5 products this week**")
        show_table(
            weekly_report["top_products"],
            {
                "product_name": "Product",
                "units_sold": "Units sold",
                "revenue": st.column_config.NumberColumn(
                    "Revenue", format="%.2f MAD"
                ),
                "profit": st.column_config.NumberColumn(
                    "Profit", format="%.2f MAD"
                ),
            },
        )
    with weekly_right:
        st.markdown("**Highest-profit products this week**")
        show_table(
            weekly_report["highest_profit_products"],
            {
                "product_name": "Product",
                "units_sold": "Units sold",
                "revenue": st.column_config.NumberColumn(
                    "Revenue", format="%.2f MAD"
                ),
                "profit": st.column_config.NumberColumn(
                    "Profit", format="%.2f MAD"
                ),
            },
        )

    st.subheader("Simple assistant")
    st.caption("Rule-based answers using your local shop data. No external API is used.")
    with st.form("assistant_form"):
        assistant_question = st.text_input(
            "Ask a question",
            placeholder="What should I restock?",
        )
        assistant_submitted = st.form_submit_button("Ask")
    if assistant_submitted:
        st.session_state["assistant_answer"] = assistant_answer(assistant_question)
    if st.session_state.get("assistant_answer"):
        st.info(st.session_state["assistant_answer"])

with products_tab:
    st.subheader("Add product")
    with st.form("add_product_form", clear_on_submit=True):
        add_left, add_middle, add_right = st.columns(3)
        new_name = add_left.text_input("Name")
        new_category = add_middle.text_input("Category")
        new_stock = add_right.number_input(
            "Stock quantity", min_value=0, step=1
        )
        new_buy_price = add_left.number_input(
            "Buy price (MAD)", min_value=0.0, step=0.5, format="%.2f"
        )
        new_sell_price = add_middle.number_input(
            "Sell price (MAD)", min_value=0.0, step=0.5, format="%.2f"
        )
        new_threshold = add_right.number_input(
            "Low-stock threshold", min_value=0, step=1, value=5
        )
        add_submitted = st.form_submit_button("Add product", type="primary")

    if add_submitted:
        try:
            add_product(
                None,
                new_name,
                new_category,
                new_buy_price,
                new_sell_price,
                int(new_stock),
                int(new_threshold),
            )
            st.success(f'Added "{new_name.strip()}".')
            st.rerun()
        except (RuntimeError, ValueError) as exc:
            st.error(str(exc))

    st.subheader("All products")
    products = get_products()
    show_table(
        products,
        {
            "id": "ID",
            "name": "Product",
            "category": "Category",
            "buy_price": st.column_config.NumberColumn("Buy price", format="%.2f MAD"),
            "sell_price": st.column_config.NumberColumn("Sell price", format="%.2f MAD"),
            "stock_quantity": "Stock",
            "low_stock_threshold": "Low-stock threshold",
        },
    )
    download_csv(
        "Download products CSV",
        products,
        "7anoutiai_products.csv",
        "download_products",
    )

    if not products.empty:
        product_options = {
            f'{row["name"]} (ID {row["id"]})': int(row["id"])
            for _, row in products.iterrows()
        }

        st.subheader("Edit product")
        selected_edit_label = st.selectbox(
            "Choose a product to edit",
            list(product_options),
            key="edit_product_select",
        )
        selected_edit_id = product_options[selected_edit_label]
        selected_product = products.loc[
            products["id"] == selected_edit_id
        ].iloc[0]

        with st.form("edit_product_form"):
            edit_left, edit_middle, edit_right = st.columns(3)
            edit_name = edit_left.text_input(
                "Name", value=str(selected_product["name"])
            )
            edit_category = edit_middle.text_input(
                "Category", value=str(selected_product["category"])
            )
            edit_stock = edit_right.number_input(
                "Stock quantity",
                min_value=0,
                step=1,
                value=int(selected_product["stock_quantity"]),
            )
            edit_buy_price = edit_left.number_input(
                "Buy price (MAD)",
                min_value=0.0,
                step=0.5,
                format="%.2f",
                value=float(selected_product["buy_price"]),
            )
            edit_sell_price = edit_middle.number_input(
                "Sell price (MAD)",
                min_value=0.0,
                step=0.5,
                format="%.2f",
                value=float(selected_product["sell_price"]),
            )
            edit_threshold = edit_right.number_input(
                "Low-stock threshold",
                min_value=0,
                step=1,
                value=int(selected_product["low_stock_threshold"]),
            )
            edit_submitted = st.form_submit_button("Save changes", type="primary")

        if edit_submitted:
            try:
                update_product(
                    None,
                    selected_edit_id,
                    edit_name,
                    edit_category,
                    edit_buy_price,
                    edit_sell_price,
                    int(edit_stock),
                    int(edit_threshold),
                )
                st.success("Product updated.")
                st.rerun()
            except (RuntimeError, ValueError) as exc:
                st.error(str(exc))

        st.subheader("Delete product")
        st.warning(
            "Deleting a product removes it from inventory. Existing sales history is kept."
        )
        selected_delete_label = st.selectbox(
            "Choose a product to delete",
            list(product_options),
            key="delete_product_select",
        )
        confirm_delete = st.checkbox(
            "I understand that this product will be removed.",
            key="confirm_product_delete",
        )
        if st.button(
            "Delete product",
            disabled=not confirm_delete,
            type="secondary",
        ):
            try:
                delete_product(None, product_options[selected_delete_label])
                st.success("Product deleted.")
                st.rerun()
            except (RuntimeError, ValueError) as exc:
                st.error(str(exc))

with sales_tab:
    st.subheader("Record sale")
    products = get_products()
    if products.empty:
        st.info("Add a product before recording a sale.")
    else:
        sale_options = {
            f'{row["name"]} — {row["stock_quantity"]} in stock': int(row["id"])
            for _, row in products.iterrows()
        }
        with st.form("record_sale_form", clear_on_submit=True):
            sale_product_label = st.selectbox("Product", list(sale_options))
            sale_quantity = st.number_input(
                "Quantity sold", min_value=1, step=1, value=1
            )
            sale_date = st.date_input("Sale date", value=date.today())
            sale_submitted = st.form_submit_button("Record sale", type="primary")

        if sale_submitted:
            try:
                result = record_sale(
                    sale_options[sale_product_label],
                    int(sale_quantity),
                    sale_date,
                )
                st.success(
                    f"Sale recorded: {money(result['revenue'])} revenue and "
                    f"{money(result['profit'])} profit."
                )
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    st.subheader("Sales history")
    sales = get_sales()
    show_table(
        sales,
        {
            "product_name": "Product",
            "quantity": "Quantity",
            "sale_date": "Date",
            "revenue": st.column_config.NumberColumn("Revenue", format="%.2f MAD"),
            "profit": st.column_config.NumberColumn("Profit", format="%.2f MAD"),
        },
    )
    download_csv(
        "Download sales CSV",
        sales,
        "7anoutiai_sales.csv",
        "download_sales",
    )

with debts_tab:
    st.subheader("Customer debt notebook")
    total_unpaid = get_total_unpaid_debt()
    st.metric("Total unpaid debt", money(total_unpaid))

    debt_form_column, payment_form_column = st.columns(2)
    with debt_form_column:
        st.markdown("**Add customer debt**")
        with st.form("add_customer_debt_form", clear_on_submit=True):
            debt_customer_name = st.text_input("Customer name")
            debt_phone = st.text_input("Phone (optional)")
            debt_amount = st.number_input(
                "Debt amount (MAD)",
                min_value=0.0,
                step=1.0,
                format="%.2f",
            )
            debt_note = st.text_input("Note")
            debt_date = st.date_input("Debt date", value=date.today())
            debt_submitted = st.form_submit_button("Add debt", type="primary")

        if debt_submitted:
            try:
                add_customer_debt(
                    None,
                    debt_customer_name,
                    debt_phone,
                    debt_amount,
                    debt_note,
                    debt_date,
                )
                st.success("Customer debt recorded.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    balances = get_customer_balances()
    unpaid_balances = (
        balances[balances["remaining_balance"] > 0].copy()
        if not balances.empty
        else balances
    )
    with payment_form_column:
        st.markdown("**Record customer payment**")
        if unpaid_balances.empty:
            st.info("There are no unpaid customer balances.")
        else:
            payment_options = {
                (
                    f"{row['customer_name']} - "
                    f"{money(float(row['remaining_balance']))} due"
                ): int(row["customer_id"])
                for _, row in unpaid_balances.iterrows()
            }
            with st.form("record_customer_payment_form", clear_on_submit=True):
                payment_customer_label = st.selectbox(
                    "Customer",
                    list(payment_options),
                )
                payment_amount = st.number_input(
                    "Payment amount (MAD)",
                    min_value=0.0,
                    step=1.0,
                    format="%.2f",
                )
                payment_date = st.date_input("Payment date", value=date.today())
                payment_submitted = st.form_submit_button(
                    "Record payment",
                    type="primary",
                )

            if payment_submitted:
                try:
                    record_customer_payment(
                        None,
                        payment_options[payment_customer_label],
                        payment_amount,
                        payment_date,
                    )
                    st.success("Customer payment recorded.")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))

    st.subheader("Customer balances")
    show_table(
        balances,
        {
            "customer_id": "Customer ID",
            "customer_name": "Customer",
            "phone": "Phone",
            "total_debt": st.column_config.NumberColumn(
                "Total debt", format="%.2f MAD"
            ),
            "total_paid": st.column_config.NumberColumn(
                "Total paid", format="%.2f MAD"
            ),
            "remaining_balance": st.column_config.NumberColumn(
                "Remaining balance", format="%.2f MAD"
            ),
        },
    )

    st.subheader("Debt transactions")
    debt_transactions = get_debt_transactions()
    show_table(
        debt_transactions,
        {
            "customer_name": "Customer",
            "phone": "Phone",
            "transaction_type": "Type",
            "amount": st.column_config.NumberColumn("Amount", format="%.2f MAD"),
            "note": "Note",
            "transaction_date": "Date",
        },
    )
    download_csv(
        "Download debts CSV",
        debt_transactions,
        "7anoutiai_debts.csv",
        "download_debts",
    )

with restock_tab:
    st.subheader("Add stock")
    products = get_products()
    if products.empty:
        st.info("Add a product before recording a restock.")
    else:
        restock_options = {
            f'{row["name"]} - {row["stock_quantity"]} in stock': int(row["id"])
            for _, row in products.iterrows()
        }
        selected_restock_label = st.selectbox(
            "Product to restock",
            list(restock_options),
            key="restock_product_select",
        )
        selected_restock_id = restock_options[selected_restock_label]
        selected_restock_product = products.loc[
            products["id"] == selected_restock_id
        ].iloc[0]

        with st.form("record_restock_form", clear_on_submit=True):
            restock_left, restock_right = st.columns(2)
            quantity_added = restock_left.number_input(
                "Quantity added",
                min_value=1,
                step=1,
                value=1,
            )
            supplier_name = restock_right.text_input("Supplier name")
            unit_buy_price = restock_left.number_input(
                "Unit buy price (MAD)",
                min_value=0.0,
                step=0.5,
                format="%.2f",
                value=float(selected_restock_product["buy_price"]),
            )
            restock_date = restock_right.date_input(
                "Restock date",
                value=date.today(),
            )
            should_update_buy_price = st.checkbox(
                "Update the product's buy price to this new price",
                value=True,
            )
            restock_submitted = st.form_submit_button(
                "Save restock",
                type="primary",
            )

        if restock_submitted:
            try:
                record_restock(
                    None,
                    selected_restock_id,
                    int(quantity_added),
                    supplier_name,
                    unit_buy_price,
                    restock_date,
                    should_update_buy_price,
                )
                st.success("Restock saved and product stock updated.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    st.subheader("Restocking recommendations")
    st.caption(
        "Based on current stock and average daily sales during the last 7 days."
    )
    recommendations = get_restocking_recommendations()
    show_table(
        recommendations,
        {
            "name": "Product",
            "category": "Category",
            "stock_quantity": "Stock",
            "low_stock_threshold": "Low-stock threshold",
            "units_sold_7d": "Units sold (7 days)",
            "average_daily_sales": st.column_config.NumberColumn(
                "Average daily sales", format="%.2f"
            ),
            "estimated_days_until_stockout": st.column_config.NumberColumn(
                "Estimated days left", format="%.1f"
            ),
            "recommendation_reason": "Reason",
        },
    )

    st.subheader("Restock history")
    restocks = get_restocks()
    if not restocks.empty:
        restocks["updated_buy_price"] = restocks["updated_buy_price"].map(
            {1: "Yes", 0: "No"}
        )
    show_table(
        restocks,
        {
            "product_name": "Product",
            "quantity_added": "Quantity added",
            "supplier_name": "Supplier",
            "unit_buy_price": st.column_config.NumberColumn(
                "Unit buy price", format="%.2f MAD"
            ),
            "restock_date": "Date",
            "updated_buy_price": "Buy price updated",
        },
    )
    download_csv(
        "Download restocks CSV",
        restocks,
        "7anoutiai_restocks.csv",
        "download_restocks",
    )
