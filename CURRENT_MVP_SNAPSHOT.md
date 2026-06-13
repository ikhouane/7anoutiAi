# 7anoutiAI Current MVP Snapshot

Snapshot date: June 12, 2026

This document records the working local MVP before any production-oriented
changes. It is a documentation checkpoint only.

## Confirmed Features

### Dashboard

- Today's revenue
- Today's profit
- Total stock value based on current quantity and buy price
- Number of low-stock products
- Low-stock product table
- Top-selling products with units sold, revenue, and profit

### Weekly Report

- Revenue from Monday through the current date
- Profit from Monday through the current date
- Number of sale transactions this week
- Top five products this week by units sold
- Top five products this week by profit

### Product Management

- Add products
- View all products
- Edit product details
- Delete products with confirmation
- Track name, category, buy price, sell price, stock quantity, and low-stock
  threshold
- Prevent duplicate product names and negative prices or stock values

### Sales Management

- Record a product sale with quantity and date
- Calculate revenue and profit automatically
- Decrease stock automatically
- Prevent a sale when available stock is insufficient
- View sales history

### Customer Debts

- Add a customer debt with customer name, optional phone, amount, note, and date
- Record customer payments
- Prevent payments greater than the remaining balance
- Show total debt, total paid, and remaining balance for each customer
- Show total unpaid debt across all customers
- View the complete debt and payment transaction ledger

### Restock Management

- Select a product and record added stock
- Track quantity, supplier, unit buy price, and date
- Increase product stock automatically
- Optionally update the product's current buy price
- View restock history

### Restocking Recommendations

- Calculate average daily sales over the latest seven days
- Estimate days until each product runs out
- Recommend products at or below their low-stock threshold
- Recommend products estimated to run out in less than three days

### Rule-Based Assistant

The local assistant answers these supported questions using current shop data:

- What should I restock?
- What are my best products?
- How much profit today?
- How much profit this week?
- Who owes me money?
- What is my total unpaid debt?
- Show low stock products

The assistant is keyword-based and does not use an external API.

### CSV Exports

- Products
- Sales
- Debt and payment transactions
- Restock history

### Demo Data

- 24 Moroccan hanout products
- 289 sale transactions covering the latest 14 days
- 5 customers
- 8 debt and payment transactions
- 8 supplier restock transactions

Running the seed script resets the local database to this demo dataset.

## Current Architecture

### `app.py`

The Streamlit user interface. It defines the five tabs:

- Dashboard
- Products
- Sales
- Customer Debts
- Restock

It contains forms, tables, metrics, the rule-based assistant, validation error
display, and CSV download buttons.

### `database.py`

The SQLite data-access layer. It:

- Creates the database schema and indexes
- Handles product CRUD
- Records sales and decreases stock atomically
- Records debts and payments
- Calculates customer balances through SQL queries
- Records restocks and increases stock atomically
- Returns query results as Pandas DataFrames

### `analytics.py`

The Pandas analytics layer. It calculates:

- Daily dashboard metrics
- Low-stock products
- Overall top-selling products
- Weekly revenue, profit, sale count, and product rankings
- Total unpaid customer debt
- Seven-day restocking recommendations

### `seed_data.py`

Creates deterministic demo data for:

- Products
- The latest 14 days of sales
- Customers
- Debts and payments
- Supplier restocks

### `data/hanout.db`

The local SQLite database. The current schema contains:

- `products`
- `sales`
- `customers`
- `debt_transactions`
- `restocks`

Foreign keys, validation checks, indexes, and database transactions protect the
main data relationships and stock updates.

### Other Files

- `MVP_SPEC.md`: Original MVP scope
- `README.md`: Current feature and usage documentation
- `requirements.txt`: Python runtime dependencies

## Technology Stack

- Python
- Streamlit
- SQLite through Python's built-in `sqlite3` module
- Pandas
- SQL
- CSV

Runtime dependencies in `requirements.txt`:

```text
streamlit>=1.35,<2.0
pandas>=2.0,<3.0
```

## Run Locally

Open PowerShell in the project root:

```powershell
cd C:\Users\HOSNI\OneDrive\Documents\7anoutiAi
pip install -r requirements.txt
python seed_data.py
streamlit run app.py
```

Open the URL printed by Streamlit, normally:

```text
http://localhost:8501
```

`python seed_data.py` deletes current local records and restores the
deterministic demo dataset. It should not be run when preserving manually
entered shop data is required.

## Current MVP Boundaries

- Local single-shop application
- Local SQLite storage
- No user accounts or authentication
- No electronic payment processing
- No external APIs
- No cloud synchronization
- No mobile application
- No barcode scanner
- No advanced AI model
- No Darija voice input

## Safety Checkpoint

At the time of this snapshot, the requested capabilities are present in the
codebase:

- Dashboard: confirmed
- Weekly report: confirmed
- Product management: confirmed
- Sales management: confirmed
- Customer debts: confirmed
- Restock management: confirmed
- Recommendations: confirmed
- Assistant: confirmed
- CSV exports: confirmed
- SQLite local storage: confirmed

No application feature or production change was made while creating this
snapshot.
