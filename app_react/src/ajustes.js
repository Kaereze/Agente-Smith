// Tempos e limites da tela que o administrador pode mudar no ajustes.json (grupos tela, filtro e recarregar).
// O servidor entrega em /ajustes.js (window.aj); sem ele, vale o valor de fábrica escrito aqui, que precisa ser IGUAL ao da
// tabela (src/sistema/ajustes_tabela.py; test_ajustes.py confere). Uso: aj("tela.k_volta_segundos", 5)
export function aj(chave, padrao) {
  try {
    const v = window.aj?.(chave);
    return typeof v === typeof padrao ? v : padrao;
  } catch {
    return padrao;
  }
}
