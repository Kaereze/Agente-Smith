"""O Painel por dentro: o servidor, as rotas da API e o que cada tela precisa.

Mexa aqui quando uma TELA precisa de um número novo, uma rota nova ou um jeito novo de contar (resumo do dia, equipe, saúde, rede entre PCs).
A tela em si (o que aparece) fica em `app_ui/`. O servidor que liga tudo é `src/app_servidor.py`.

estado_correio, estado_envio, estado_rede, estado_sistema = as quatro partes do `Estado` (e-mail, envio de NF, rede entre PCs, versão e saúde). rotas_api = a lista de endereços da API. painel_metricas, relatorio_semana, contagem_painel = números das telas. demo = os dados FICTÍCIOS do modo demonstração.

Mapa de todas as pastas: COMECE_AQUI.md (na raiz do projeto).
"""
