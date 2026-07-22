-- Supabase schema for Content Studio (Phase 6 / Section 9 of implementation-guide.md).
-- Run once against the Supabase project's Postgres via the SQL editor or `supabase db push`.

create table if not exists brand_kit (
    id uuid primary key default gen_random_uuid(),
    brand_name text not null,
    handle text not null,
    masthead_short text not null,
    niche text not null,
    audience text not null,
    voice_traits jsonb not null,
    voice_samples_poetic jsonb not null,
    voice_samples_direct jsonb not null,
    forbidden jsonb not null default '[]',
    mood_palettes jsonb not null,
    text_color text not null,
    background_color text not null,
    font_heading text not null,
    font_script text not null,
    font_body text not null,
    default_tone jsonb not null,
    signature_cta text,
    updated_at timestamptz not null default now()
);

-- Structural safeguard, not just a "the code should behave" hope (logbook #35):
-- db.upsert_brand_kit()'s original #9 implementation upserted with no `id` in the
-- payload, which -- the first time a caller other than the seed-on-empty path ever
-- ran it (routes/export.py's voice-compounding write) -- silently INSERTed a second
-- row instead of updating the existing one, confirmed live. upsert_brand_kit() is
-- fixed to look up and update the existing row's id explicitly, but this unique
-- expression index makes a second row structurally impossible regardless of what
-- application code does going forward -- every row's `(true)` collides with every
-- other row's, so only one can ever exist.
create unique index if not exists brand_kit_singleton_idx on brand_kit ((true));

create table if not exists memory (
    id text primary key,
    date date not null,
    topic_id text not null,
    category text not null,
    angle text not null,
    approach text not null,
    format text not null,
    mood text not null,
    hook text not null,
    fingerprint text not null,
    source_ids jsonb not null default '[]',
    status text not null,
    created_at timestamptz not null default now(),
    -- Added for export-confirmation (logbook #35, #31/#33): real content + a real
    -- exported timestamp, instead of only the 80-char truncated `hook`. `slides` is
    -- the same discriminated-union shape (template_id + template fields) as
    -- GeneratedPost.slides / models/post.py -- validated through that union at write
    -- time (routes/export.py), not stored as opaque JSON.
    caption text not null default '',
    slides jsonb not null default '[]',
    exported_at timestamptz,
    -- NULL means voice training hasn't successfully completed yet -- same
    -- meaningful-null pattern as exported_at. Deliberately decoupled from `status`
    -- (logbook #35 fix): a training failure must not permanently strand the record
    -- with no way to retry just the training half, which is what a single shared
    -- idempotency guard on status alone caused before this column existed.
    voice_trained_at timestamptz,
    -- Added for the carousel direct-write port (logbook #43): the model's own
    -- freely-chosen anchor (e.g. "ha-ha wall", "Plimsoll line"), read back by
    -- engine/angle_engine.py::assemble_carousel_context() as this topic's
    -- recent-anchors avoid-list. Empty for every pre-existing record and for
    -- single_image's unchanged sample_cell/generate_angle path, which has no
    -- equivalent concept -- same optional-by-default shape as caption/slides
    -- above, not a required field.
    anchor text not null default ''
);

-- `create table if not exists` above is a no-op against the already-live
-- production table -- this explicit, idempotent ALTER is what actually adds
-- the column there when this file is re-run (same gap this file has always
-- had for every column added after initial launch; made explicit here rather
-- than silently relying on a manual dashboard edit).
alter table memory add column if not exists anchor text not null default '';

create index if not exists memory_category_status_idx on memory (category, status);
create index if not exists memory_fingerprint_idx on memory (fingerprint);

create table if not exists image_cache (
    cache_key text primary key,
    keyword text not null,
    shadow_hex text not null,
    highlight_hex text not null,
    storage_url text not null,
    created_at timestamptz not null default now()
);

-- Storage bucket for duotoned hero images (Section 9). Public read since hero images
-- are embedded directly in rendered slides; storage.buckets policies are managed via
-- the Supabase dashboard/CLI, not this SQL file's DDL grants.
insert into storage.buckets (id, name, public)
values ('heroes', 'heroes', true)
on conflict (id) do nothing;

-- Row Level Security: the backend talks to these tables via the service_role key,
-- which bypasses RLS entirely (a role property, unaffected by anything below), so
-- this only ever governed the anon/authenticated keys that ship in the frontend
-- bundle. Originally: any authenticated session got full read/write access, anon got
-- none. Tightened (logbook #34) after an investigation (#30, #33) found the
-- "authenticated_full_access" policy below was FOR ALL / using(true) / with
-- check(true) -- fully open -- and a production brand_kit value changed with no
-- identified writer in application code. Frontend/backend code review (Step 1 of
-- #34) confirmed nothing legitimate needs direct authenticated access to any of
-- these three tables -- the frontend Supabase client is auth-only (no `.from(...)`
-- calls at all), and every backend read/write goes through db/supabase.py's single
-- service_role-keyed client. So authenticated is now locked out entirely, same as
-- anon already was.
alter table brand_kit enable row level security;
alter table memory enable row level security;
alter table image_cache enable row level security;

revoke select, insert, update, delete on brand_kit, memory, image_cache from authenticated;

drop policy if exists "authenticated_full_access" on brand_kit;
drop policy if exists "authenticated_full_access" on memory;
drop policy if exists "authenticated_full_access" on image_cache;

-- No replacement policies: RLS stays enabled with zero policies for either anon or
-- authenticated, so both get 0 rows on read and every write rejected at the object-
-- permission layer (confirmed live: 403 `permission denied`, before RLS is even
-- evaluated). service_role is unaffected, per the note above.

-- Audit trail (logbook #34): records every insert/update/delete on brand_kit and
-- memory, through any path (app, dashboard, direct API/SQL) -- independent of the
-- RLS tightening above, so a future out-of-band write is visible even if some other
-- access path is ever opened back up by mistake. Append-only in practice: locked
-- down the same way as the three tables above -- both RLS (enabled, no policies for
-- anon/authenticated) AND an explicit revoke of the base grants Supabase applies by
-- default to new public-schema tables (confirmed live: without the revoke below,
-- authenticated could still SELECT and get 200/[] rather than a 403 -- RLS alone
-- filtered every row but didn't deny the query itself; the revoke closes that gap
-- the same way the other three tables are already closed). Only the security-
-- definer trigger function below (which runs as its owner, exempt from RLS as
-- owner) can write into it.
create table if not exists audit_log (
    id bigint generated always as identity primary key,
    table_name text not null,
    operation text not null,
    row_id text,
    old_value jsonb,
    new_value jsonb,
    changed_at timestamptz not null default now(),
    db_user text not null default current_user,
    auth_role text default auth.role(),
    auth_uid uuid default auth.uid()
);

alter table audit_log enable row level security;

revoke select, insert, update, delete on audit_log from authenticated, anon;

create or replace function audit_row_change() returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
    v_row_id text;
begin
    if tg_op = 'DELETE' then
        v_row_id := (row_to_json(old)->>'id');
    else
        v_row_id := (row_to_json(new)->>'id');
    end if;

    insert into audit_log (table_name, operation, row_id, old_value, new_value, db_user, auth_role, auth_uid)
    values (
        tg_table_name,
        tg_op,
        v_row_id,
        case when tg_op in ('UPDATE', 'DELETE') then to_jsonb(old) else null end,
        case when tg_op in ('INSERT', 'UPDATE') then to_jsonb(new) else null end,
        current_user,
        auth.role(),
        auth.uid()
    );

    if tg_op = 'DELETE' then
        return old;
    end if;
    return new;
end;
$$;

drop trigger if exists audit_brand_kit on brand_kit;
create trigger audit_brand_kit
    after insert or update or delete on brand_kit
    for each row execute function audit_row_change();

drop trigger if exists audit_memory on memory;
create trigger audit_memory
    after insert or update or delete on memory
    for each row execute function audit_row_change();
