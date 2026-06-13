# 7anoutiAI Production v1 Plan

## Purpose

Move the working local 7anoutiAI MVP to a low-cost hosted architecture using
Streamlit Community Cloud, Supabase PostgreSQL, and Supabase Auth.

The migration should preserve the current features while adding secure user
accounts, multi-shop data isolation, cloud storage, and public deployment.

## 1. Current MVP Architecture

The current MVP is a local, single-shop application.

### Application

- Python application built with Streamlit
- Five main sections:
  - Dashboard
  - Products
  - Sales
  - Customer Debts
  - Restock
- Rule-based assistant using local database data
- CSV exports generated through Streamlit

### Data and Analytics

- SQLite database stored at `data/hanout.db`
- Python `sqlite3` module for database access
- Pandas for dashboard, weekly report, product rankings, debt totals, and
  restocking recommendations
- SQL transactions for sales, payments, and restocks

### Main Files

- `app.py`: Streamlit interface and assistant
- `database.py`: SQLite schema and data-access functions
- `analytics.py`: Pandas calculations and reports
- `seed_data.py`: Local demo data
- `requirements.txt`: Python dependencies

## 2. Current Limitations

### SQLite Local Database

- Data is stored on one computer.
- SQLite is unsuitable for multiple concurrent hosted users.
- Streamlit Community Cloud storage is not guaranteed to be permanent.

### No Authentication

- Anyone who can open the app can access all shop data.
- There is no user identity or secure session.

### No Multi-Shop Support

- All products, sales, debts, and restocks belong to one implicit shop.
- Records do not currently contain a `shop_id`.

### No Cloud Backups

- The SQLite file is the only persistent copy unless it is backed up manually.
- Hardware failure or accidental deletion could cause data loss.

### No User Permissions

- There are no owner, manager, or employee roles.
- Every user would have the same access.

### Not Deployed Publicly

- The application currently runs on `localhost`.
- It has no stable public URL or managed deployment workflow.

## 3. Target Production v1 Architecture

### Streamlit Frontend

- Keep Streamlit as the user interface.
- Host the app on Streamlit Community Cloud.
- Keep existing forms, dashboards, reports, recommendations, and CSV exports.
- Replace direct SQLite access with a Supabase/PostgreSQL data layer.

### Supabase PostgreSQL Database

- Store all production data in Supabase PostgreSQL.
- Use UUID primary keys for new production records.
- Use foreign keys, constraints, timestamps, and database indexes.
- Use PostgreSQL transactions or Supabase database functions for operations
  that must update several records atomically.

### Supabase Auth

- Require sign-up or sign-in before accessing shop data.
- Use Supabase Auth user IDs as the identity source.
- Store application-specific user data in the `profiles` table.
- Keep authentication session state in Streamlit during the active session.

### Multi-Shop Support

- Create a `shops` table.
- Add `shop_id` to every shop-owned business table.
- Connect each profile to a shop for Production v1.
- Filter all application reads and writes by the signed-in user's `shop_id`.

Production v1 should initially support one shop per user profile. A separate
shop-membership table can be introduced later if users need access to multiple
shops.

### Environment Variables and Secrets

- Store local development configuration in a `.env` file.
- Store hosted configuration in Streamlit Community Cloud secrets.
- Never commit credentials or service keys.

Expected configuration:

```text
SUPABASE_URL
SUPABASE_ANON_KEY
```

The Supabase service-role key must not be exposed to the Streamlit client
application. Production user operations should use the authenticated user's
token and Row Level Security.

### Streamlit Community Cloud

- Deploy from a GitHub repository.
- Use `app.py` as the Streamlit entry point.
- Configure Supabase credentials through the Streamlit secrets interface.
- Use Supabase as the permanent data store instead of the deployment
  filesystem.

## 4. Production Database Tables

All tables should use timezone-aware creation and update timestamps. Business
tables should include `shop_id`.

### `shops`

Suggested fields:

- `id` UUID primary key
- `name` text
- `owner_user_id` UUID referencing the authenticated user
- `created_at` timestamp with time zone
- `updated_at` timestamp with time zone

### `profiles`

Suggested fields:

- `id` UUID primary key referencing the Supabase Auth user
- `shop_id` UUID referencing `shops.id`
- `full_name` text
- `role` text with an allowed value such as `owner`, `manager`, or `employee`
- `created_at` timestamp with time zone
- `updated_at` timestamp with time zone

Production v1 can initially create owner profiles only while preserving the
role field for later permission work.

### `products`

Suggested fields:

- `id` UUID primary key
- `shop_id` UUID referencing `shops.id`
- `name` text
- `category` text
- `buy_price` numeric
- `sell_price` numeric
- `stock_quantity` integer
- `low_stock_threshold` integer
- `created_at` timestamp with time zone
- `updated_at` timestamp with time zone

Add a unique constraint on `(shop_id, lower(name))` or an equivalent
case-insensitive shop-level product name constraint.

### `sales`

Suggested fields:

- `id` UUID primary key
- `shop_id` UUID referencing `shops.id`
- `product_id` UUID referencing `products.id`
- `product_name` text snapshot
- `quantity` integer
- `sale_date` date
- `revenue` numeric
- `profit` numeric
- `created_by` UUID referencing the authenticated user
- `created_at` timestamp with time zone

### `customers`

Suggested fields:

- `id` UUID primary key
- `shop_id` UUID referencing `shops.id`
- `name` text
- `phone` text nullable
- `created_at` timestamp with time zone
- `updated_at` timestamp with time zone

Add a shop-level customer name constraint if duplicate customer names should
remain disallowed.

### `debt_transactions`

Suggested fields:

- `id` UUID primary key
- `shop_id` UUID referencing `shops.id`
- `customer_id` UUID referencing `customers.id`
- `customer_name` text snapshot
- `transaction_type` text restricted to `debt` or `payment`
- `amount` numeric
- `note` text nullable
- `transaction_date` date
- `created_by` UUID referencing the authenticated user
- `created_at` timestamp with time zone

### `restocks`

Suggested fields:

- `id` UUID primary key
- `shop_id` UUID referencing `shops.id`
- `product_id` UUID referencing `products.id`
- `product_name` text snapshot
- `quantity_added` integer
- `supplier_name` text
- `unit_buy_price` numeric
- `restock_date` date
- `updated_buy_price` boolean
- `created_by` UUID referencing the authenticated user
- `created_at` timestamp with time zone

### Recommended Indexes

- Products by `shop_id` and name
- Sales by `shop_id`, date, and product
- Customers by `shop_id` and name
- Debt transactions by `shop_id`, customer, and date
- Restocks by `shop_id`, product, and date

## 5. Security Plan

### No Secrets in Code

- Never place Supabase URLs, keys, passwords, or tokens directly in Python
  files.
- Add `.env` to `.gitignore`.
- Do not commit Streamlit secrets files.
- Rotate any credential that is accidentally committed.

### Local `.env`

Use a local `.env` file:

```text
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
```

Load local values through a configuration helper. The code should fail with a
clear message when required configuration is missing.

### Streamlit Cloud Secrets

Add production values through the Streamlit Community Cloud app settings:

```toml
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_ANON_KEY = "your-anon-key"
```

Do not commit `.streamlit/secrets.toml`.

### Supabase Row Level Security

- Enable Row Level Security on every application table.
- Allow users to read and modify only records belonging to their profile's
  `shop_id`.
- Restrict shop creation and profile creation to controlled onboarding flows.
- Prevent users from changing their `shop_id` or role through ordinary client
  queries.

### Shop Filtering

- Every business query must include the authenticated shop's `shop_id`.
- Do not trust a shop ID supplied by a form or URL.
- Derive `shop_id` from the signed-in user's protected profile.
- Include `shop_id` in inserts, updates, deletes, analytics queries, exports,
  and assistant queries.
- Keep Row Level Security enabled as the final enforcement layer even when the
  application already filters by `shop_id`.

### Transaction Safety

Create PostgreSQL functions for sensitive multi-step operations:

- Record a sale and decrease stock
- Record a restock and increase stock
- Record a customer payment after checking the outstanding balance

These functions should validate `shop_id`, quantities, balances, and ownership
inside one database transaction.

## 6. Migration Plan From SQLite to Supabase

### Phase 1: Preparation

1. Keep the current SQLite version as the working safety checkpoint.
2. Create a Supabase development project.
3. Add the PostgreSQL schema, constraints, indexes, and Row Level Security
   policies through versioned SQL migration files.
4. Create a configuration layer for local and cloud secrets.
5. Add the Supabase Python dependency without removing SQLite yet.

### Phase 2: Authentication and Shop Onboarding

1. Add Supabase sign-up, sign-in, sign-out, and session handling.
2. Create a shop and owner profile during onboarding.
3. Load the authenticated profile and protected `shop_id` before rendering
   business pages.
4. Block application access when authentication or profile loading fails.

### Phase 3: Database Abstraction

1. Preserve the public function responsibilities currently exposed by
   `database.py`.
2. Implement a Supabase-backed repository with equivalent operations.
3. Pass authenticated user and shop context into every operation.
4. Update analytics to consume shop-scoped query results.
5. Keep UI changes small by retaining compatible DataFrame columns where
   practical.

### Phase 4: Data Export From SQLite

1. Make a backup copy of `data/hanout.db`.
2. Export products, sales, customers, debt transactions, and restocks.
3. Add one production shop record.
4. Map SQLite integer IDs to new PostgreSQL UUIDs.
5. Attach the new `shop_id` to every imported record.
6. Preserve dates, prices, quantities, names, and historical snapshots.

### Phase 5: Data Import

Import in foreign-key order:

1. `shops`
2. `profiles`
3. `products`
4. `customers`
5. `sales`
6. `debt_transactions`
7. `restocks`

Use a one-time migration script with explicit validation and error reporting.
Do not use the production service-role key in the deployed Streamlit app.

### Phase 6: Validation

Compare SQLite and Supabase:

- Record counts by table
- Product stock quantities
- Total revenue and profit
- Weekly report totals
- Customer debt balances
- Total unpaid debt
- Restock counts
- Recommendation outputs

Test sales, restocks, and payments against a non-production Supabase project.

### Phase 7: Cutover

1. Stop writing new data to SQLite.
2. Run the final migration.
3. Repeat validation.
4. Deploy the Supabase-backed version.
5. Retain the SQLite backup as a read-only recovery artifact.
6. Remove SQLite from the production request path only after successful
   verification.

## 7. Deployment Steps

### Supabase

1. Create a Supabase project in an appropriate region.
2. Run versioned SQL migrations.
3. Enable and test Row Level Security.
4. Configure Auth providers, initially email and password.
5. Set production URL and email redirect settings.
6. Test sign-up, sign-in, sign-out, and session recovery.
7. Create and test transaction functions for sales, restocks, and payments.
8. Migrate and validate existing data if required.

### GitHub

1. Store the application in a private or public GitHub repository.
2. Add `.env`, `.streamlit/secrets.toml`, local databases, logs, and caches to
   `.gitignore`.
3. Commit schema migrations and a safe `.env.example`.
4. Keep credentials out of the repository and commit history.

### Streamlit Community Cloud

1. Connect Streamlit Community Cloud to the GitHub repository.
2. Select the production branch.
3. Set `app.py` as the entry point.
4. Add `SUPABASE_URL` and `SUPABASE_ANON_KEY` in app secrets.
5. Deploy the application.
6. Verify authentication, data isolation, and every Production v1 workflow.
7. Configure the Supabase Auth site URL and redirect URLs for the deployed
   Streamlit domain.

### Production Verification

- A new owner can create an account and shop.
- A signed-out visitor cannot access shop data.
- Two test shops cannot see or modify each other's records.
- Product, sale, debt, payment, and restock operations work.
- Stock updates remain atomic.
- Dashboard and weekly reports are shop-scoped.
- Recommendations and assistant answers are shop-scoped.
- CSV exports contain only the signed-in shop's data.
- No credentials appear in source code, browser output, or logs.

## 8. Features to Keep for Production v1

- Dashboard with today's revenue, profit, stock value, and low-stock count
- Weekly revenue, profit, sale count, top products, and highest-profit products
- Product add, view, edit, and delete
- Sales recording with automatic stock reduction
- Insufficient-stock protection
- Sales history
- Customer debt recording
- Customer payment recording and overpayment protection
- Customer balances and total unpaid debt
- Debt transaction history
- Restock recording with automatic stock increase
- Optional product buy-price update during restock
- Restock history
- Seven-day restocking recommendations
- Rule-based assistant
- CSV exports for products, sales, debts, and restocks
- Moroccan dirham display
- Demo or onboarding sample data as an optional per-shop action

Production v1 also adds:

- User authentication
- Shop onboarding
- Multi-shop data separation
- Cloud PostgreSQL storage
- Row Level Security

## 9. Features to Delay

These features should remain outside Production v1:

- Barcode scanner
- WhatsApp integration
- Darija voice input
- Mobile app
- Payment system
- Advanced AI chatbot

They should be considered only after the hosted core workflows, authentication,
data isolation, backups, and operational reliability are proven.

## Recommended Implementation Order

1. Supabase schema and Row Level Security
2. Authentication and shop onboarding
3. Supabase data-access layer
4. Transaction functions
5. SQLite migration tool
6. Full feature validation
7. Streamlit Community Cloud deployment
8. Controlled production cutover
