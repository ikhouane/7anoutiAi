-- Fix 7anoutiAI shop onboarding in an existing Supabase project.
--
-- Run this file once in Supabase Dashboard -> SQL Editor. It is safe to rerun.
-- The function creates or recovers the authenticated user's shop and profile
-- atomically, avoiding the circular Row Level Security check during signup.

begin;

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

commit;
