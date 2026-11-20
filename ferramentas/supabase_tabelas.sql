-- Tabelas do Supabase para o TESTE de conexão do Painel Fiscal (20/11/2026).
-- Como usar: no site do Supabase, abra o projeto > "SQL Editor" > "New query", cole TUDO isto e clique em "Run".
-- Pode rodar de novo sem problema (não apaga nada que já existe).
--
-- Só tem dado FICTÍCIO de teste e o "sinal de vida" de cada PC (nome do PC e hora). Nada de hóspede.
-- A segurança (RLS) fica ligada: a chave publicável só consegue mexer nestas duas tabelas.

create table if not exists painel_teste (
  id     text primary key,
  pc     text,
  valor  text,
  quando timestamptz not null default now()
);

create table if not exists painel_sinal (
  pc     text primary key,
  quando timestamptz not null default now(),
  versao text
);

alter table painel_teste enable row level security;
alter table painel_sinal enable row level security;

drop policy if exists "teste_publico" on painel_teste;
create policy "teste_publico" on painel_teste for all to anon using (true) with check (true);

drop policy if exists "sinal_publico" on painel_sinal;
create policy "sinal_publico" on painel_sinal for all to anon using (true) with check (true);
