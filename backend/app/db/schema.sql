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
    created_at timestamptz not null default now()
);

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
