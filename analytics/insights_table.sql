-- Optional: lets `python -m analytics --upload` save insights to Supabase, and the app read them from there.
-- Paste into Supabase: SQL Editor -> New query -> Run. Safe to run again.
-- It only creates a new table called "insights" and never touches other tables.

create table if not exists public.insights (
  id          text primary key,          -- "latest"
  data        jsonb not null,            -- the same JSON as frontend/public/insights.json
  updated_at  timestamptz not null default now()
);

alter table public.insights enable row level security;
drop policy if exists "read insights" on public.insights;
create policy "read insights" on public.insights for select to anon, authenticated using (true);
-- Writes need the service_role key (the analytics script), so the browser can only read.
