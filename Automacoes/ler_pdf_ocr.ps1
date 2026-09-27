# SOLICITACOES NF - le o texto de um PDF que e IMAGEM (nota escaneada)
param([Parameter(Mandatory = $true)][string]$Caminho, [int]$MaxPaginas = 3)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Runtime.WindowsRuntime

$metodos = [System.WindowsRuntimeSystemExtensions].GetMethods()
$asTaskOperacao = ($metodos | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
$asTaskAcao = ($metodos | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncAction' })[0]

function Esperar($operacao, [Type]$tipo) {
    $tarefa = $asTaskOperacao.MakeGenericMethod($tipo).Invoke($null, @($operacao))
    $tarefa.Wait(-1) | Out-Null
    $tarefa.Result
}
function EsperarAcao($acao) {
    $tarefa = $asTaskAcao.Invoke($null, @($acao))
    $tarefa.Wait(-1) | Out-Null
}

[Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Pdf.PdfDocument, Windows.Data.Pdf, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Pdf.PdfPageRenderOptions, Windows.Data.Pdf, ContentType = WindowsRuntime] | Out-Null
[Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics, ContentType = WindowsRuntime] | Out-Null
[Windows.Storage.Streams.InMemoryRandomAccessStream, Windows.Storage.Streams, ContentType = WindowsRuntime] | Out-Null

$arquivo = Esperar ([Windows.Storage.StorageFile]::GetFileFromPathAsync((Resolve-Path $Caminho).Path)) ([Windows.Storage.StorageFile])
$pdf = Esperar ([Windows.Data.Pdf.PdfDocument]::LoadFromFileAsync($arquivo)) ([Windows.Data.Pdf.PdfDocument])
$motor = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if ($null -eq $motor) { throw "OCR do Windows indisponivel (nenhum idioma com reconhecimento de texto instalado)." }

$paginas = [Math]::Min([int]$pdf.PageCount, $MaxPaginas)
for ($i = 0; $i -lt $paginas; $i++) {
    $pagina = $pdf.GetPage([uint32]$i)
    $fluxo = New-Object Windows.Storage.Streams.InMemoryRandomAccessStream
    $opcoes = New-Object Windows.Data.Pdf.PdfPageRenderOptions
    $opcoes.DestinationWidth = 2200
    EsperarAcao ($pagina.RenderToStreamAsync($fluxo, $opcoes))
    $decodificador = Esperar ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($fluxo)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $imagem = Esperar ($decodificador.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
    $resultado = Esperar ($motor.RecognizeAsync($imagem)) ([Windows.Media.Ocr.OcrResult])
    foreach ($linha in $resultado.Lines) { $linha.Text }
}
