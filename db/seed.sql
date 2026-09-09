create schema if not exists triage;

create table if not exists triage.rules (
  id bigint generated always as identity primary key,
  name text not null,
  description text,
  field text not null,
  operator text not null check (operator in ('equals','in','contains_any','gte','lte')),
  value jsonb not null,
  points int not null,
  enabled boolean not null default true,
  updated_at timestamptz not null default now()
);

create table if not exists triage.settings (
  key text primary key,
  value jsonb not null,
  updated_at timestamptz not null default now()
);

create table if not exists triage.decisions (
  id bigint generated always as identity primary key,
  lead_snapshot jsonb not null,
  score int not null,
  matched_rules jsonb not null,
  source text not null check (source in ('rules','ai','fallback')),
  priority text not null check (priority in ('P1','P2','P3')),
  confidence numeric,
  rationale text,
  needs_review boolean not null default false,
  reviewed_priority text,
  created_at timestamptz not null default now()
);

-- rules v1 (see app/seed_rules.py - single source of truth, kept in sync)
truncate table triage.rules restart identity;
insert into triage.rules (name, field, operator, value, points) values ('Channel: referral', 'channel', 'equals', '"referral"'::jsonb, 30);
insert into triage.rules (name, field, operator, value, points) values ('Channel: warm/inbound', 'channel', 'equals', '"warm"'::jsonb, 20);
insert into triage.rules (name, field, operator, value, points) values ('Channel: LinkedIn cold outreach', 'channel', 'equals', '"linkedin"'::jsonb, 10);
insert into triage.rules (name, field, operator, value, points) values ('Channel: Upwork', 'channel', 'equals', '"upwork"'::jsonb, 5);
insert into triage.rules (name, field, operator, value, points) values ('Company size: 50-300 (sweet spot)', 'company_size_bucket', 'equals', '"50-300"'::jsonb, 20);
insert into triage.rules (name, field, operator, value, points) values ('Company size: 301-500', 'company_size_bucket', 'equals', '"301-500"'::jsonb, 10);
insert into triage.rules (name, field, operator, value, points) values ('Company size: 1-49', 'company_size_bucket', 'equals', '"1-49"'::jsonb, 5);
insert into triage.rules (name, field, operator, value, points) values ('Company size: 500+', 'company_size_bucket', 'equals', '"500+"'::jsonb, 0);
insert into triage.rules (name, field, operator, value, points) values ('Role: target buyer (COO/Ops Manager/Finance Director)', 'role', 'in', '["COO", "Operations Manager", "Finance Director"]'::jsonb, 20);
insert into triage.rules (name, field, operator, value, points) values ('Urgency keyword in message/notes', 'message_or_notes', 'contains_any', '["urgent", "asap", "this month"]'::jsonb, 15);
insert into triage.rules (name, field, operator, value, points) values ('Country in target list (PLACEHOLDER pending sign-off)', 'country', 'in', '["United States", "Canada"]'::jsonb, 10);

-- settings
truncate table triage.settings;
insert into triage.settings (key, value) values ('band_low', '40'::jsonb);
insert into triage.settings (key, value) values ('band_high', '70'::jsonb);
insert into triage.settings (key, value) values ('confidence_threshold', '0.7'::jsonb);
insert into triage.settings (key, value) values ('ai_enabled', 'true'::jsonb);
insert into triage.settings (key, value) values ('ai_daily_cap', '15'::jsonb);
