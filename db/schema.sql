-- Run this in your Supabase SQL editor to set up all tables.

create table if not exists topics (
    id          uuid primary key default gen_random_uuid(),
    topic       text not null,
    source      text,
    virality_score integer,
    hook_type   text,
    created_at  timestamptz default now()
);

create table if not exists scripts (
    id              uuid primary key default gen_random_uuid(),
    topic_id        uuid references topics(id),
    title           text,
    hook            text,
    full_script     text,
    description     text,
    hashtags        text[],
    thumbnail_prompt text,
    visual_prompts  text[],
    model_used      text,
    created_at      timestamptz default now()
);

create table if not exists videos (
    id                  text primary key,
    topic               text,
    virality_score      integer,
    title               text,
    youtube_url         text,
    youtube_video_id    text,
    tiktok_url          text,
    status              text default 'pending',
    views_48h           integer,
    retention_pct       float,
    created_at          timestamptz default now()
);

create table if not exists analytics (
    id              uuid primary key default gen_random_uuid(),
    video_id        text references videos(id),
    platform        text,
    views           integer,
    likes           integer,
    comments        integer,
    shares          integer,
    retention_pct   float,
    revenue_usd     float,
    fetched_at      timestamptz default now()
);
