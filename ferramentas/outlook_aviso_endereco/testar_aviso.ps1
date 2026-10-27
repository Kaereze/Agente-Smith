# Teste do aviso de endereços do Outlook (so le; nao muda nada). Veja o LEIAME.txt.
# Mostra o remetente do e-mail mais novo da Caixa de Entrada. Se a regra estiver certa, nenhuma janela de aviso aparece.
$ErrorActionPreference = "Stop"
try {
    $ol = New-Object -ComObject Outlook.Application
    $item = $ol.GetNamespace("MAPI").GetDefaultFolder(6).Items.GetFirst()
    if (-not $item) { "Caixa de Entrada vazia: nao deu para testar."; exit }
    "Remetente lido: " + $item.SenderEmailAddress
    "RESULTADO BOM se nenhuma janela de aviso apareceu."
} catch {
    "ACESSO NEGADO ou erro: " + $_.Exception.Message
    "Se for acesso negado, rode o desfazer_aviso_endereco.reg e nao aplique nos outros PCs."
}
