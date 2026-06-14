-- 7anoutiAI Production v1 Supabase schema
--
-- How to run:
-- 1. Create or open a Supabase project.
-- 2. In the Supabase dashboard, open SQL Editor.
-- 3. Create a new query, paste this entire file, and click Run.
-- 4. Run this first in a development project before applying it to production.
--
-- This migration creates the Production v1 tables, constraints, indexes, and
-- Row Level Security policies. Application queries should still include
-- shop_id filters; RLS is the final database-level protection.

begin;

create table public.shops (
    id uuid primary key default gen_random_uuid(),
    name text not null check (length(trim(name)) > 0),
    owner_id uuid not null references auth.users(id) on delete restrict,
    created_at timestamptz not null default now()
);

create table public.profiles (
    id uuid primary key references auth.users(id) on delete cascade,
    shop_id uuid not null references public.shops(id) on delete restrict,
    full_name text,
    role text not null default 'owner',
    created_at timestamptz not null default now()
);

create table public.products (
    id uuid primary key default gen_random_uuid(),
    shop_id uuid not null references public.shops(id) on delete cascade,
    name text not null check (length(trim(name)) > 0),
    category text not null check (length(trim(category)) > 0),
    buy_price numeric(12, 2) not null check (buy_price >= 0),
    sell_price numeric(12, 2) not null check (sell_price >= 0),
    stock_quantity integer not null check (stock_quantity >= 0),
    low_stock_threshold integer not null check (low_stock_threshold >= 0),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (shop_id, name),
    unique (id, shop_id)
);

create table public.sales (
    id uuid primary key default gen_random_uuid(),
    shop_id uuid not null references public.shops(id) on delete cascade,
    product_id uuid,
    quantity integer not null check (quantity > 0),
    sale_date date not null,
    revenue numeric(12, 2) not null check (revenue >= 0),
    profit numeric(12, 2) not null,
    created_at timestamptz not null default now(),
    foreign key (product_id, shop_id)
        references public.products(id, shop_id)
        on delete set null (product_id)
);

create table public.customers (
    id uuid primary key default gen_random_uuid(),
    shop_id uuid not null references public.shops(id) on delete cascade,
    name text not null check (length(trim(name)) > 0),
    phone text,
    created_at timestamptz not null default now(),
    unique (id, shop_id)
);

create table public.debt_transactions (
    id uuid primary key default gen_random_uuid(),
    shop_id uuid not null references public.shops(id) on delete cascade,
    customer_id uuid not null,
    transaction_type text not null
        check (transaction_type in ('debt', 'payment')),
    amount numeric(12, 2) not null check (amount > 0),
    note text,
    transaction_date date not null,
    created_at timestamptz not null default now(),
    foreign key (customer_id, shop_id)
        references public.customers(id, shop_id)
        on delete cascade
);

create table public.restocks (
    id uuid primary key default gen_random_uuid(),
    shop_id uuid not null references public.shops(id) on delete cascade,
    product_id uuid,
    quantity_added integer not null check (quantity_added > 0),
    supplier_name text,
    unit_buy_price numeric(12, 2) not null check (unit_buy_price >= 0),
    restock_date date not null,
    updated_buy_price boolean not null default false,
    created_at timestamptz not null default now(),
    foreign key (product_id, shop_id)
        references public.products(id, shop_id)
        on delete set null (product_id)
);

create index idx_products_shop_id
    on public.products(shop_id);

create index idx_sales_shop_id_sale_date
    on public.sales(shop_id, sale_date);

create index idx_customers_shop_id
    on public.customers(shop_id);

create index idx_debt_transactions_shop_id_transaction_date
    on public.debt_transactions(shop_id, transaction_date);

create index idx_restocks_shop_id_restock_date
    on public.restocks(shop_id, restock_date);

create index idx_profiles_shop_id
    on public.profiles(shop_id);

create index idx_sales_product_id
    on public.sales(product_id);

create index idx_debt_transactions_customer_id
    on public.debt_transactions(customer_id);

create index idx_restocks_product_id
    on public.restocks(product_id);

-- SECURITY DEFINER avoids recursive RLS evaluation when policies need the
-- signed-in user's profile to determine their shop.
create or replace function public.current_shop_id()
returns uuid
language sql
stable
security definer
set search_path = public
as $$
    select shop_id
    from public.profiles
    where id = auth.uid()
    limit 1
$$;

revoke all on function public.current_shop_id() from public;
grant execute on function public.current_shop_id() to authenticated;

-- Create or recover a user's shop and profile in one transaction. This uses a
-- SECURITY DEFINER function because profile RLS cannot identify the user's
-- shop until the profile itself exists.
create or replace function public.onboard_shop(
    p_shop_name text,
    p_full_name text default null
)
returns table (
    id uuid,
    shop_id uuid,
    full_name text,
    role text,
    shop_name text
)
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_user_id uuid := auth.uid();
    v_shop public.shops%rowtype;
    v_profile public.profiles%rowtype;
begin
    if v_user_id is null then
        raise exception 'Authentication is required to create a shop';
    end if;
    if length(trim(coalesce(p_shop_name, ''))) = 0 then
        raise exception 'Shop name is required';
    end if;

    select *
    into v_profile
    from public.profiles
    where profiles.id = v_user_id;

    if found then
        select *
        into v_shop
        from public.shops
        where shops.id = v_profile.shop_id;

        return query
        select
            v_profile.id,
            v_profile.shop_id,
            v_profile.full_name,
            v_profile.role,
            v_shop.name;
        return;
    end if;

    -- Reuse a shop left behind by an earlier interrupted onboarding attempt.
    select *
    into v_shop
    from public.shops
    where shops.owner_id = v_user_id
    order by shops.created_at desc
    limit 1;

    if found then
        update public.shops
        set name = trim(p_shop_name)
        where shops.id = v_shop.id
        returning * into v_shop;
    else
        insert into public.shops (name, owner_id)
        values (trim(p_shop_name), v_user_id)
        returning * into v_shop;
    end if;

    insert into public.profiles (id, shop_id, full_name, role)
    values (
        v_user_id,
        v_shop.id,
        nullif(trim(coalesce(p_full_name, '')), ''),
        'owner'
    )
    returning * into v_profile;

    return query
    select
        v_profile.id,
        v_profile.shop_id,
        v_profile.full_name,
        v_profile.role,
        v_shop.name;
end;
$$;

revoke all on function public.onboard_shop(text, text) from public;
grant execute on function public.onboard_shop(text, text) to authenticated;

-- Atomically increase stock and save the matching restock transaction.
create or replace function public.record_restock(
    p_shop_id uuid,
    p_product_id uuid,
    p_quantity_added integer,
    p_supplier_name text,
    p_unit_buy_price numeric,
    p_restock_date date,
    p_update_buy_price boolean default false
)
returns uuid
language plpgsql
security invoker
set search_path = public
as $$
declare
    v_restock_id uuid;
begin
    if p_shop_id is distinct from public.current_shop_id() then
        raise exception 'The requested shop does not match the authenticated user';
    end if;
    if p_quantity_added <= 0 then
        raise exception 'Restock quantity must be greater than zero';
    end if;
    if length(trim(coalesce(p_supplier_name, ''))) = 0 then
        raise exception 'Supplier name is required';
    end if;
    if p_unit_buy_price < 0 then
        raise exception 'Unit buy price cannot be negative';
    end if;

    update public.products
    set stock_quantity = stock_quantity + p_quantity_added,
        buy_price = case
            when p_update_buy_price then p_unit_buy_price
            else buy_price
        end,
        updated_at = now()
    where id = p_product_id
      and shop_id = p_shop_id;

    if not found then
        raise exception 'Product not found in your shop';
    end if;

    insert into public.restocks (
        shop_id,
        product_id,
        quantity_added,
        supplier_name,
        unit_buy_price,
        restock_date,
        updated_buy_price
    )
    values (
        p_shop_id,
        p_product_id,
        p_quantity_added,
        trim(p_supplier_name),
        p_unit_buy_price,
        p_restock_date,
        p_update_buy_price
    )
    returning id into v_restock_id;

    return v_restock_id;
end;
$$;

revoke all on function public.record_restock(
    uuid, uuid, integer, text, numeric, date, boolean
) from public;
grant execute on function public.record_restock(
    uuid, uuid, integer, text, numeric, date, boolean
) to authenticated;

alter table public.shops enable row level security;
alter table public.profiles enable row level security;
alter table public.products enable row level security;
alter table public.sales enable row level security;
alter table public.customers enable row level security;
alter table public.debt_transactions enable row level security;
alter table public.restocks enable row level security;

grant usage on schema public to authenticated;
grant select, insert, update, delete on public.shops to authenticated;
grant select, insert, update, delete on public.profiles to authenticated;
grant select, insert, update, delete on public.products to authenticated;
grant select, insert, update, delete on public.sales to authenticated;
grant select, insert, update, delete on public.customers to authenticated;
grant select, insert, update, delete on public.debt_transactions to authenticated;
grant select, insert, update, delete on public.restocks to authenticated;

-- Shop onboarding: an authenticated user may create a shop only for themselves.
create policy "shops_select_own"
on public.shops
for select
to authenticated
using (
    owner_id = auth.uid()
    or id = public.current_shop_id()
);

create policy "shops_insert_own"
on public.shops
for insert
to authenticated
with check (owner_id = auth.uid());

create policy "shops_update_own"
on public.shops
for update
to authenticated
using (
    owner_id = auth.uid()
    and id = public.current_shop_id()
)
with check (
    owner_id = auth.uid()
    and id = public.current_shop_id()
);

create policy "shops_delete_own"
on public.shops
for delete
to authenticated
using (
    owner_id = auth.uid()
    and id = public.current_shop_id()
);

-- Users can read and maintain only their own profile. Profile creation must
-- link the signed-in user to a shop that they own.
create policy "profiles_select_own"
on public.profiles
for select
to authenticated
using (
    id = auth.uid()
    and shop_id = public.current_shop_id()
);

create policy "profiles_insert_own"
on public.profiles
for insert
to authenticated
with check (
    id = auth.uid()
    and role = 'owner'
    and exists (
        select 1
        from public.shops
        where shops.id = profiles.shop_id
          and shops.owner_id = auth.uid()
    )
);

create policy "profiles_update_own"
on public.profiles
for update
to authenticated
using (
    id = auth.uid()
    and shop_id = public.current_shop_id()
)
with check (
    id = auth.uid()
    and shop_id = public.current_shop_id()
);

create policy "profiles_delete_own"
on public.profiles
for delete
to authenticated
using (
    id = auth.uid()
    and shop_id = public.current_shop_id()
);

create policy "products_select_shop"
on public.products
for select
to authenticated
using (shop_id = public.current_shop_id());

create policy "products_insert_shop"
on public.products
for insert
to authenticated
with check (shop_id = public.current_shop_id());

create policy "products_update_shop"
on public.products
for update
to authenticated
using (shop_id = public.current_shop_id())
with check (shop_id = public.current_shop_id());

create policy "products_delete_shop"
on public.products
for delete
to authenticated
using (shop_id = public.current_shop_id());

create policy "sales_select_shop"
on public.sales
for select
to authenticated
using (shop_id = public.current_shop_id());

create policy "sales_insert_shop"
on public.sales
for insert
to authenticated
with check (shop_id = public.current_shop_id());

create policy "sales_update_shop"
on public.sales
for update
to authenticated
using (shop_id = public.current_shop_id())
with check (shop_id = public.current_shop_id());

create policy "sales_delete_shop"
on public.sales
for delete
to authenticated
using (shop_id = public.current_shop_id());

create policy "customers_select_shop"
on public.customers
for select
to authenticated
using (shop_id = public.current_shop_id());

create policy "customers_insert_shop"
on public.customers
for insert
to authenticated
with check (shop_id = public.current_shop_id());

create policy "customers_update_shop"
on public.customers
for update
to authenticated
using (shop_id = public.current_shop_id())
with check (shop_id = public.current_shop_id());

create policy "customers_delete_shop"
on public.customers
for delete
to authenticated
using (shop_id = public.current_shop_id());

create policy "debt_transactions_select_shop"
on public.debt_transactions
for select
to authenticated
using (shop_id = public.current_shop_id());

create policy "debt_transactions_insert_shop"
on public.debt_transactions
for insert
to authenticated
with check (shop_id = public.current_shop_id());

create policy "debt_transactions_update_shop"
on public.debt_transactions
for update
to authenticated
using (shop_id = public.current_shop_id())
with check (shop_id = public.current_shop_id());

create policy "debt_transactions_delete_shop"
on public.debt_transactions
for delete
to authenticated
using (shop_id = public.current_shop_id());

create policy "restocks_select_shop"
on public.restocks
for select
to authenticated
using (shop_id = public.current_shop_id());

create policy "restocks_insert_shop"
on public.restocks
for insert
to authenticated
with check (shop_id = public.current_shop_id());

create policy "restocks_update_shop"
on public.restocks
for update
to authenticated
using (shop_id = public.current_shop_id())
with check (shop_id = public.current_shop_id());

create policy "restocks_delete_shop"
on public.restocks
for delete
to authenticated
using (shop_id = public.current_shop_id());

commit;
