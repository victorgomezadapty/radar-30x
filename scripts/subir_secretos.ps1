# Copia las claves de tu .env a los secretos del repositorio de GitHub (las usa GitHub Actions).
# Las claves no se muestran en pantalla. Uso, desde la carpeta JEV:
#   powershell -ExecutionPolicy Bypass -File .\scripts\subir_secretos.ps1
# (Solo caracteres ASCII: Windows PowerShell 5.1 lee mal los acentos en archivos UTF-8.)
$nombres = @("TYPESAFE_API_KEY", "YOUTUBE_API_KEY", "DEEPSEEK_API_KEY", "TAVILY_API_KEY",
             "REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "IG_USER_ID", "IG_ACCESS_TOKEN")
$valores = @{}
foreach ($linea in Get-Content ".env" -Encoding UTF8) {
    if ($linea -match '^\s*([A-Z_]+)\s*=\s*(.*?)\s*$') { $valores[$Matches[1]] = $Matches[2] }
}
foreach ($n in $nombres) {
    $v = $valores[$n]
    if ([string]::IsNullOrWhiteSpace($v)) { Write-Host "  $n esta vacio en .env, se omite"; continue }
    gh secret set $n --body $v --repo victorgomezadapty/radar-30x
    if ($LASTEXITCODE -eq 0) { Write-Host "  $n subido" } else { Write-Host "  $n NO se pudo subir" }
}
