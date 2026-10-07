# Сборка и установка русификатора Super Robot Wars V (PC/Steam).
# Требования: Python 3.x + pycryptodome (pip install pycryptodome).
#
#   .\build.ps1 -GameDir "D:\games\SUPER ROBOT WARS V"            # собрать и установить
#   .\build.ps1 -GameDir "..." -NoInstall                          # только собрать в .\out
#   .\build.ps1 -GameDir "..." -Restore                            # откат на оригиналы из .bak
param(
    [Parameter(Mandatory)][string]$GameDir,
    [switch]$NoInstall,
    [switch]$Restore
)
$ErrorActionPreference = "Stop"
$T = "$PSScriptRoot\tools"
$TR = "$PSScriptRoot\translations"
$OUT = "$PSScriptRoot\out"

$SysCpk  = Join-Path $GameDir "Data\AIDDATA\EN\SysText.cpk"
$LtCpk   = Join-Path $GameDir "CommonData\ShiroData\LanguageData\EN\LT00_EN.cpk"
$FontCpk = Join-Path $GameDir "Data\AIDDATA\EN\FontInfo.cpk"

if ($Restore) {
    foreach ($f in $SysCpk, $LtCpk, $FontCpk) {
        if (Test-Path "$f.bak") { Copy-Item "$f.bak" $f -Force; Write-Host "restored: $f" }
        else { Write-Host "no backup for $f" }
    }
    return
}

foreach ($f in $SysCpk, $LtCpk, $FontCpk) {
    if (-not (Test-Path $f)) { throw "Не найден файл игры: $f" }
}
New-Item -ItemType Directory -Force $OUT, "$OUT\work" | Out-Null

function Build-TextCpk($origCpk, $ruJson, $name) {
    # оригинальный BLTU нужен парсеру как референс: распаковать и расшифровать
    python "$T\cpk_extract.py" $origCpk "$OUT\work\$name" | Out-Null
    python "$T\srwv_decrypt.py" "$OUT\work\$name" "$OUT\work\${name}_dec" | Out-Null
    python "$T\bltu_parser.py" rebuild "$OUT\work\${name}_dec\00000000.dat" $ruJson "$OUT\work\$name.dat"
    if ($LASTEXITCODE) { throw "bltu rebuild failed: $name" }
    python "$T\srwv_encrypt.py" "$OUT\work\$name.dat" "$OUT\work\${name}_enc.dat" | Out-Null
    python "$T\ru_cpk_patch.py" $origCpk "$OUT\$name.cpk" "0=$OUT\work\${name}_enc.dat"
    if ($LASTEXITCODE) { throw "cpk patch failed: $name" }
}

$origSys  = if (Test-Path "$SysCpk.bak")  { "$SysCpk.bak" }  else { $SysCpk }
$origLt   = if (Test-Path "$LtCpk.bak")   { "$LtCpk.bak" }   else { $LtCpk }
$origFont = if (Test-Path "$FontCpk.bak") { "$FontCpk.bak" } else { $FontCpk }

Build-TextCpk $origSys "$TR\SysText_RU.json" "SysText_RU"
Build-TextCpk $origLt  "$TR\LT00_RU.json"    "LT00_RU"

# шрифт: исправление метрик кириллицы (файл id=3 внутри FontInfo.cpk)
python "$T\cpk_extract.py" $origFont "$OUT\work\Font" | Out-Null
python "$T\srwv_decrypt.py" "$OUT\work\Font" "$OUT\work\Font_dec" | Out-Null
python "$T\ru_font_metrics.py" "$OUT\work\Font_dec\00000003.dat" "$OUT\work\font3_RU.dat"
if ($LASTEXITCODE) { throw "font metrics patch failed" }
python "$T\srwv_encrypt.py" "$OUT\work\font3_RU.dat" "$OUT\work\font3_RU_enc.dat" | Out-Null
python "$T\ru_cpk_patch.py" $origFont "$OUT\FontInfo_RU.cpk" "3=$OUT\work\font3_RU_enc.dat"
if ($LASTEXITCODE) { throw "cpk patch failed: FontInfo" }

Write-Host "`nСобрано в $OUT"
if ($NoInstall) { return }

foreach ($pair in @(@($SysCpk, "SysText_RU.cpk"), @($LtCpk, "LT00_RU.cpk"), @($FontCpk, "FontInfo_RU.cpk"))) {
    $dst, $src = $pair
    if (-not (Test-Path "$dst.bak")) { Copy-Item $dst "$dst.bak" }
    Copy-Item "$OUT\$src" $dst -Force
    Write-Host "installed: $dst"
}
Write-Host "Готово. Откат: .\build.ps1 -GameDir `"$GameDir`" -Restore"
