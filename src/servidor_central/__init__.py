"""O servidor central (API) do Painel Fiscal: um PC guarda os dados e atende os outros.

Mexa aqui quando o assunto é o servidor da API: como ele guarda as abas, a porta, o token, a cópia de segurança.

armazem = guarda as abas num arquivo SQLite. servidor = atende os PCs pela rede (porta 8770, com token). backup = cópia diária do banco. O cliente que os PCs usam está em central/backend_api.py. Plano e etapas: Segundo Cérebro/6 Documentos/Plano da API central.md.
"""
