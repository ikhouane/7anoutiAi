# 7anoutiAI MVP

7anoutiAI is a simple local inventory and sales application for Moroccan
hanout owners. It tracks products, records sales, updates stock automatically,
shows daily and weekly business metrics, manages customer debt, and tracks
supplier restocks.

## Features

- Add, view, edit, and delete products
- Record dated sales and prevent sales when stock is insufficient
- Automatically calculate revenue and profit
- Dashboard for today's revenue, today's profit, stock value, low stock, and
  best sellers
- Weekly revenue, profit, sale count, best sellers, and highest-profit products
- Restocking recommendations based on low-stock thresholds and the last seven
  days of sales
- Customer debt notebook with debts, payments, balances, and total unpaid debt
- Supplier restock history with automatic stock increases and optional buy-price
  updates
- Rule-based shop assistant for common stock, profit, product, and debt questions
- CSV exports for products, sales, debt transactions, and restock history
- Realistic demo products, 14 days of sales, customer debts, and restocks

## Technology

- Python
- Streamlit
- SQLite
- Pandas
- Supabase Python client (prepared for the future production backend)

## Run locally

From the project root, create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create your local environment file:

```powershell
Copy-Item .env.example .env
```

Keep `DATABASE_BACKEND=sqlite` in `.env`, then seed and run the app:

```powershell
python seed_data.py
streamlit run app.py
```

Streamlit will print a local URL, normally `http://localhost:8501`. Open that
address in a browser.

Running `python seed_data.py` resets the database and recreates all demo
products, sales, customer debts, payments, and restock history. The application
also creates missing database tables automatically.

## Validation and health checks

Install dependencies and run the lightweight business-rule tests with:

```powershell
pytest -q
```

The tests use temporary SQLite databases and cover product validation,
insufficient-stock protection, overpayment protection, restock stock updates,
and sale revenue/profit calculations.

The Streamlit sidebar shows:

- The selected database backend
- Database connection health
- The logged-in email in Supabase mode
- The current shop name in Supabase mode

Empty datasets display friendly guidance instead of empty grids. Configuration
and connection failures include actionable messages without exposing secrets.

## Environment variables

Configuration is read from operating-system environment variables and from a
local `.env` file. Existing operating-system variables take priority over
values in `.env`.

```text
DATABASE_BACKEND=sqlite
APP_URL=http://localhost:8501
SUPABASE_URL=your_supabase_url_here
SUPABASE_ANON_KEY=your_supabase_anon_key_here
```

- `DATABASE_BACKEND` supports `sqlite` and `supabase`. SQLite provides the full
  local MVP; Supabase currently provides authentication, onboarding, product
  management, customer debt management, and restock management.
- `APP_URL` is the URL users return to after confirming their email. Use
  `http://localhost:8501` locally and the deployed Streamlit URL in production.
- `SUPABASE_URL` is required only when `DATABASE_BACKEND=supabase`.
- `SUPABASE_ANON_KEY` is required only when `DATABASE_BACKEND=supabase`.

Supabase mode requires valid configuration and authentication. Products,
sales history, dashboard analytics, customer debts, and restocks use
shop-scoped Supabase data. Sale recording still remains on the SQLite backend
until its atomic stock-update transaction is migrated.

## Supabase client setup

The project includes `supabase_client.py` and the official Supabase Python
dependency. This prepares client creation without replacing the current SQLite
data layer.

1. Create a Supabase project.
2. Run `supabase_schema.sql` in the Supabase SQL Editor.
3. Copy `.env.example` to `.env`.
4. Add the project URL and public anonymous key:

```text
DATABASE_BACKEND=sqlite
APP_URL=http://localhost:8501
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-public-anon-key
```

If the tables were created before restock support was added, do not rerun the
entire first-install schema. In the Supabase SQL Editor, run only the
`create or replace function public.record_restock(...)` block and its following
`revoke` and `grant` statements from `supabase_schema.sql`.

Keep `DATABASE_BACKEND=sqlite` while the application still uses the SQLite
repository. The Supabase client can be checked independently:

```python
from supabase_client import get_supabase_client, is_supabase_configured

if is_supabase_configured():
    supabase = get_supabase_client()
```

Use only the public anonymous key in the application. Never use or expose a
Supabase `service_role` key in Streamlit, `.env.example`, source code, browser
output, or logs.

## Supabase authentication

When `DATABASE_BACKEND=sqlite`, the local demo keeps its current behavior and
does not require login.

When `DATABASE_BACKEND=supabase`, the app:

- Requires email and password login
- Supports email and password signup
- Handles projects that require email confirmation
- Stores the active user session in Streamlit session state
- Restores refreshed access and refresh tokens during the session
- Supports logout
- Checks for the user's profile
- Asks new users to create a shop and owner profile

The Supabase business-data repository supports products, sales history,
dashboard analytics, customer debts, and restocks for the authenticated shop.
Sale recording remains disabled in Supabase mode until its stock update and
sales insert are migrated as one atomic database transaction.

## Deploy to Streamlit Community Cloud

1. Push the project to a private or public GitHub repository.
2. Create a Supabase project.
3. Open the Supabase SQL Editor and run `supabase_schema.sql`.
4. In Streamlit Community Cloud, create a new app from the GitHub repository.
5. Set the app entry point to `app.py`.
6. Open the app's **Advanced settings** or **Secrets** section and add the
   required secrets shown below.
7. Deploy the app and confirm that the sidebar reports:
   - `Database backend: supabase`
   - `Database connected`
   - The logged-in user and current shop after authentication

### Required Streamlit secrets

Add these values to the Streamlit Community Cloud secrets editor:

```toml
DATABASE_BACKEND = "supabase"
APP_URL = "https://your-app.streamlit.app"
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_ANON_KEY = "your-public-anon-key"
```

### Public demo without login

To let anyone test the app without creating an account, use this Streamlit
secret:

```toml
DATABASE_BACKEND = "sqlite"
```

The app automatically loads demo products, sales, debts, and restocks when the
cloud database is empty. Public demo data is shared between visitors and may
reset when Streamlit restarts the app, so it must not contain real customer
information.

Use the Supabase project URL and public anonymous key from the Supabase API
settings. Never use a `service_role` key in Streamlit.

In Supabase Dashboard, open **Authentication → URL Configuration** and set:

- **Site URL:** the exact deployed Streamlit URL
- **Redirect URLs:** the same deployed Streamlit URL

This prevents confirmation emails from redirecting users to
`http://localhost:3000`.

Root-level Streamlit secrets are made available to the app as environment
variables, which are read by `config.py`.

Do not create or commit `.streamlit/secrets.toml`. Real secrets must exist only
in the Streamlit Community Cloud secrets editor or in a local ignored `.env`
file.

The cloud deployment uses Supabase rather than `data/hanout.db`. The local
SQLite database is intentionally excluded from Git.

## Database adapter

`db_adapter.py` is now the application-facing database layer:

- In SQLite mode, it delegates to the preserved functions in `database.py`.
- In Supabase mode, product functions require the authenticated profile's
  `shop_id`.
- Supabase product list, create, update, and delete operations are implemented.
- Supabase customer creation/reuse, debts, payments, balances, and transaction
  history are implemented.
- Supabase restocks atomically increase product stock, optionally update the
  buy price, and save supplier history through the `record_restock` database
  function in `supabase_schema.sql`.
- Supabase sales history is returned in the same Pandas DataFrame format as
  SQLite and supports CSV export.
- Dashboard metrics, weekly reports, restocking recommendations, and assistant
  answers work with either backend.
- Every Supabase product query includes `shop_id`, with Row Level Security as
  the final enforcement layer.
- Every Supabase customer and debt query is scoped to `shop_id`.
- Every Supabase restock and product lookup query is scoped to `shop_id`.
- Sale recording still returns a clear "not available yet" error in Supabase
  mode until its stock update and sales insert can be migrated atomically.

The Streamlit production interface exposes Dashboard, Products, Sales history,
Customer Debts, and Restock after onboarding. All production reads are scoped
to the authenticated profile's `shop_id`.

**Never commit `.env`, `.streamlit/secrets.toml`, database files, or real
credentials.** These files are excluded by `.gitignore`. Keep only safe
placeholders in `.env.example`.

For a future Streamlit Community Cloud deployment, store real values in the
app's Streamlit secrets settings instead of the repository.

## Using the app

- **Dashboard:** Review today's metrics, the weekly report, low stock, best
  sellers, and ask the rule-based assistant a supported question.
- **Products:** Add, edit, delete, view, and export products.
- **Sales:** Record a sale, review sales history, and export sales. Stock is
  decreased automatically, and overselling is blocked.
- **Customer Debts:** Add a debt, record a customer payment, review balances,
  see total unpaid debt, and export the transaction ledger.
- **Restock:** Add supplier stock, optionally update the product's buy price,
  review recommendations and restock history, and export restocks.

The assistant supports questions such as:

- `What should I restock?`
- `What are my best products?`
- `How much profit today?`
- `How much profit this week?`
- `Who owes me money?`
- `What is my total unpaid debt?`
- `Show low stock products`

## Project structure

```text
7anoutiAi/
|-- app.py
|-- analytics.py
|-- auth.py
|-- config.py
|-- db_adapter.py
|-- database.py
|-- seed_data.py
|-- supabase_client.py
|-- supabase_schema.sql
|-- .env.example
|-- .gitignore
|-- .streamlit/
|   `-- config.toml
|-- requirements.txt
|-- README.md
|-- MVP_SPEC.md
|-- tests/
|   `-- test_core_business_rules.py
`-- data/
    `-- hanout.db
```
