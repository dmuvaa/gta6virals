-- Hypecut schema. Run once in Supabase → SQL Editor (or `supabase db push`).
-- The Python API and worker connect as the database owner and bypass RLS;
-- the browser/Next.js only ever reads through RLS policies (own rows only).

-- ---------------------------------------------------------------- profiles
create table if not exists public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  name text not null default '',
  plan text not null default 'free' check (plan in ('free', 'creator', 'pro')),
  plan_status text not null default '',
  billing_customer text,
  billing_subscription text,
  created_at timestamptz not null default now()
);
create index if not exists profiles_billing_customer on public.profiles (billing_customer);

-- Create a profile row whenever someone signs up.
create or replace function public.handle_new_user() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  insert into public.profiles (id, name)
  values (new.id, coalesce(new.raw_user_meta_data ->> 'name', new.raw_user_meta_data ->> 'full_name', ''))
  on conflict (id) do nothing;
  return new;
end $$;
drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created after insert on auth.users
  for each row execute function public.handle_new_user();

-- ---------------------------------------------------------------- usage
create table if not exists public.usage (
  user_id uuid not null references public.profiles (id) on delete cascade,
  period text not null,                       -- YYYY-MM (UTC)
  seconds_scanned double precision not null default 0,
  exports integer not null default 0,
  primary key (user_id, period)
);

-- ---------------------------------------------------------------- projects
create table if not exists public.projects (
  id text primary key,
  user_id uuid not null references public.profiles (id) on delete cascade,
  url text not null,
  title text not null default '',
  platform text not null default '',
  uploader text not null default '',
  thumbnail text,
  duration double precision not null default 0,
  stage text not null default 'queued',       -- queued|probing|downloading|analyzing|review|done|error|cancelled
  progress double precision not null default 0,
  message text not null default '',
  error text,
  mode text not null default '',
  settings jsonb not null default '{}',       -- format, captions, facecam, clip_len, range, watermark …
  window_start double precision not null default 0,
  window_end double precision not null default 0,
  timeline jsonb not null default '[]',
  notes jsonb not null default '[]',
  facecam jsonb,                              -- {rect, source}
  overlay jsonb,                              -- detected webcam box for gameplay checks
  internal jsonb not null default '{}',       -- worker bookkeeping (scan file key, offsets)
  cancelled boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists projects_user on public.projects (user_id, created_at desc);

-- ---------------------------------------------------------------- moments
create table if not exists public.moments (
  project_id text not null references public.projects (id) on delete cascade,
  id text not null,
  rank integer not null,
  start_s double precision not null,          -- window time
  end_s double precision not null,
  peak_s double precision not null,
  score double precision not null default 0,
  reason text not null default '',
  label text not null default '',
  source_start double precision not null default 0,
  source_end double precision not null default 0,
  state text not null default 'new' check (state in ('new', 'kept', 'discarded')),
  status text not null default 'idle',        -- idle|queued|downloading|captioning|rendering|done|error
  flag text,                                  -- static|camera|null
  format text,
  preview_key text, pv_start double precision, pv_end double precision,
  file_key text, thumb_key text,
  captioned boolean not null default false,
  error text,
  internal jsonb not null default '{}',       -- motion/face/overlay scores, source offsets
  updated_at timestamptz not null default now(),
  primary key (project_id, id)
);
create index if not exists moments_state on public.moments (project_id, state);

-- ---------------------------------------------------------------- tasks (job queue)
create table if not exists public.tasks (
  id bigserial primary key,
  project_id text not null references public.projects (id) on delete cascade,
  kind text not null,                         -- scan|prefetch|preview|render
  moment_id text,
  payload jsonb not null default '{}',
  priority integer not null default 100,      -- lower runs first (previews the user is waiting on = 10)
  status text not null default 'queued' check (status in ('queued', 'running', 'done', 'failed')),
  attempts integer not null default 0,
  worker text,
  error text,
  created_at timestamptz not null default now(),
  started_at timestamptz,
  finished_at timestamptz
);
create index if not exists tasks_ready on public.tasks (status, priority, id) where status = 'queued';
create index if not exists tasks_project on public.tasks (project_id);

-- ---------------------------------------------------------------- row-level security
alter table public.profiles enable row level security;
alter table public.usage    enable row level security;
alter table public.projects enable row level security;
alter table public.moments  enable row level security;
alter table public.tasks    enable row level security;

drop policy if exists "own profile" on public.profiles;
create policy "own profile" on public.profiles for select using ((select auth.uid()) = id);
drop policy if exists "own usage" on public.usage;
create policy "own usage" on public.usage for select using ((select auth.uid()) = user_id);
drop policy if exists "own projects" on public.projects;
create policy "own projects" on public.projects for select using ((select auth.uid()) = user_id);
drop policy if exists "own moments" on public.moments;
create policy "own moments" on public.moments for select using (
  exists (select 1 from public.projects p where p.id = project_id and p.user_id = (select auth.uid())));
-- tasks: no policies = no access from the browser (backend only).
