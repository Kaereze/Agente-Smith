' SOLICITACOES NF - roda um .bat sem NENHUMA janela aparecer na tela

Dim argumentos, caminhoBat, shell, codigoSaida

Set argumentos = WScript.Arguments
If argumentos.Count < 1 Then
    WScript.Quit 1
End If
caminhoBat = argumentos(0)

Set shell = CreateObject("WScript.Shell")
codigoSaida = shell.Run(Chr(34) & caminhoBat & Chr(34), 0, True)
WScript.Quit codigoSaida
