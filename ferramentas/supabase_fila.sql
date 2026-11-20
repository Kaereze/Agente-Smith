-- Fila de envio no Supabase, COM SEGURANÇA (Painel Fiscal, 20/11/2026).
-- Como usar: SQL Editor > New query > cole TUDO > Run. Pode rodar de novo sem problema.
--
-- Diferença para o teste (supabase_tabelas.sql): aqui a fila leva e-mail do destinatário e assunto dos envios (dado de hóspede).
-- Por isso NINGUÉM entra só com a chave publicável. Cada PC entra com a sua credencial (usuário do Supabase Auth) e só vale
-- se o e-mail dele estiver na lista `pcs_autorizados`, que só o administrador (você, pelo painel do Supabase) consegue mexer.
--
-- Depois de rodar este arquivo, para CADA PC (casa e os 4 do trabalho):
--   1) Authentication > Users > Add user > "Create new user": e-mail (ex.: painel-casa@example.com), senha forte,
--      marque "Auto Confirm User".
--   2) Rode no SQL Editor:  insert into pcs_autorizados (email, pc) values ('painel-casa@example.com', 'CASA') on conflict do nothing;
--   3) No PC, o arquivo chave-supabase.json ganha "email" e "senha" (ferramentas/testar_supabase.py confere).
-- E desligue o cadastro aberto: Authentication > Sign In / Providers > desmarque "Allow new users to sign up".
-- (Mesmo que alguém se cadastrasse, não estaria na lista e não veria nada.)

create table if not exists pcs_autorizados (
  email text primary key,
  pc    text
);

create table if not exists aba_linhas (
  id      bigint generated always as identity primary key,   -- a ordem de chegada: quem tem id menor foi primeiro
  aba     text  not null,
  valores jsonb not null,                                    -- a linha da planilha, coluna por coluna (texto)
  criado  timestamptz not null default now()
);
create index if not exists aba_linhas_aba_id on aba_linhas (aba, id);
create index if not exists aba_linhas_criado on aba_linhas (criado);

-- Função que diz "este PC está na lista". Roda com o poder do dono para conseguir ler a lista,
-- mas só responde sim ou não (não devolve nada da lista) e não está liberada para ninguém sem entrar.
create or replace function public.pc_autorizado() returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.pcs_autorizados p where p.email = (select auth.jwt() ->> 'email'));
$$;
revoke all on function public.pc_autorizado() from public, anon;
grant execute on function public.pc_autorizado() to authenticated;

alter table pcs_autorizados enable row level security;   -- sem regra nenhuma: só o administrador mexe
alter table aba_linhas      enable row level security;

drop policy if exists "pcs_autorizados_leem_e_gravam" on aba_linhas;
create policy "pcs_autorizados_leem_e_gravam" on aba_linhas
  for all to authenticated
  using (public.pc_autorizado())
  with check (public.pc_autorizado());

-- As tabelas de teste e o sinal de vida (supabase_tabelas.sql) passam a valer só para PCs autorizados: some a regra aberta para
-- quem tem só a chave publicável. (Depois disto, o teste ferramentas/testar_supabase.py exige 'email' e 'senha' no arquivo da chave.)
create table if not exists painel_teste (id text primary key, pc text, valor text, quando timestamptz not null default now());
create table if not exists painel_sinal (pc text primary key, quando timestamptz not null default now(), versao text);
alter table painel_teste enable row level security;
alter table painel_sinal enable row level security;

drop policy if exists "teste_publico" on painel_teste;
drop policy if exists "sinal_publico" on painel_sinal;
drop policy if exists "teste_pcs_autorizados" on painel_teste;
drop policy if exists "sinal_pcs_autorizados" on painel_sinal;
create policy "teste_pcs_autorizados" on painel_teste for all to authenticated using (public.pc_autorizado()) with check (public.pc_autorizado());
create policy "sinal_pcs_autorizados" on painel_sinal for all to authenticated using (public.pc_autorizado()) with check (public.pc_autorizado());
