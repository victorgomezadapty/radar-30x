# Copia las claves de tu .env a los secretos del repositorio de GitHub (las usa GitHub Actions).
# Las claves no se muestran en pantalla ni quedan en el historial. Uso, desde la carpeta JEV:
#   powershell -ExecutionPolicy Bypass -File scripts\subir_secretos.ps1
$nombres = @("TYPESAFE_API_KEY", "YOUTUBE_API_KEY", "DEEPSEEK_API_KEY", "TAVILY_API_KEY",
             "REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "IG_USER_ID", "IG_ACCESS_TOKEN")
$valores = @{}
foreach ($linea in Get-Content ".env" -Encoding UTF8) {
    if ($linea -match '^\s*([A-Z_]+)\s*=\s*(.*)\s*$') { $valores[$Matches[1]] = $Matches[2] }
}
foreach ($n in $nombres) {
    $v = $valores[$n]
    if ([string]::IsNullOrWhiteSpace($v)) { Write-Host "  $n vacío, se omite"; continue }
    $v | gh secret set $n
    if ($LASTEXITCODE -eq 0) { Write-Host "  $n subido" } else { Write-Host "  $n FALLÓ" }
}
