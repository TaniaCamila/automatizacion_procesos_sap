#Requires -Version 5.1
<#
.SYNOPSIS
  Registra la tarea \Automatizacion_FBL1N_Diaria (lun–vie 09:00) DISABLED por defecto.

.DESCRIPTION
  - LogonType Interactive (solo con sesión iniciada)
  - RunLevel Limited
  - MultipleInstances IgnoreNew
  - StartWhenAvailable
  - ExecutionTimeLimit 3 horas
  - No sobrescribe sin -Replace
  - -Enable ejecuta prechecks antes de habilitar

.PARAMETER ProjectRoot
  Raíz del proyecto Automatizacion_FBL1N.

.PARAMETER Enable
  Habilita la tarea tras prechecks.

.PARAMETER Replace
  Permite sobrescribir una tarea existente.

.PARAMETER ShowDefinition
  Solo muestra la definición planificada (JSON) sin registrar.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\instalar_tarea_diaria.ps1 -ProjectRoot C:\Ruta\Proyecto\Automatizacion_FBL1N

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\instalar_tarea_diaria.ps1 -ProjectRoot C:\Ruta\Proyecto\Automatizacion_FBL1N -Enable
#>
param(
  [Parameter(Mandatory = $true)]
  [string]$ProjectRoot,
  [switch]$Enable,
  [switch]$Replace,
  [switch]$ShowDefinition
)

$ErrorActionPreference = 'Stop'
$taskName = 'Automatizacion_FBL1N_Diaria'
$taskPath = '\'

function Get-DotEnvValue {
  param([string]$EnvFile, [string]$Key)
  if (-not (Test-Path -LiteralPath $EnvFile)) { return '' }
  foreach ($line in Get-Content -LiteralPath $EnvFile -Encoding UTF8) {
    $t = $line.Trim()
    if (-not $t -or $t.StartsWith('#')) { continue }
    if ($t -notmatch '=') { continue }
    $k, $v = $t.Split('=', 2)
    if ($k.Trim() -eq $Key) {
      return ($v.Trim().Trim('"').Trim("'"))
    }
  }
  return ''
}

function Invoke-Prechecks {
  param([string]$Root)
  $python = Join-Path $Root '.venv\Scripts\python.exe'
  $script = Join-Path $Root 'scripts\run_diario.py'
  $pipeline = Join-Path $Root 'scripts\run_actualizacion_automatica.py'
  $envFile = Join-Path $Root '.env'

  if (-not (Test-Path -LiteralPath $python)) {
    throw "Precheck: no existe $python"
  }
  if (-not (Test-Path -LiteralPath $script)) {
    throw "Precheck: no existe $script"
  }
  if (-not (Test-Path -LiteralPath $pipeline)) {
    throw "Precheck: no existe $pipeline"
  }
  if (-not (Test-Path -LiteralPath $envFile)) {
    throw "Precheck: no existe .env en $Root"
  }

  $futureEnabled = (Get-DotEnvValue -EnvFile $envFile -Key 'FBL1N_FUTURE_ENABLED').ToLowerInvariant()
  if ($futureEnabled -notin @('true', '1', 'yes', 'on')) {
    throw 'Precheck: FBL1N_FUTURE_ENABLED debe ser true'
  }
  $cutoff = Get-DotEnvValue -EnvFile $envFile -Key 'FBL1N_COMPENSATION_CUTOFF'
  if (-not $cutoff -or $cutoff -notmatch '^\d{4}-\d{2}-\d{2}$') {
    throw 'Precheck: FBL1N_COMPENSATION_CUTOFF inválida (YYYY-MM-DD)'
  }
  $vbs = Get-DotEnvValue -EnvFile $envFile -Key 'SAP_FBL1N_VBS_PATH'
  if (-not $vbs) {
    throw 'Precheck: SAP_FBL1N_VBS_PATH ausente en .env'
  }
  if (-not (Test-Path -LiteralPath $vbs)) {
    throw "Precheck: SAP_FBL1N_VBS_PATH no existe: $vbs"
  }
  $future = Get-DotEnvValue -EnvFile $envFile -Key 'FBL1N_FUTURE_PATH'
  if (-not $future) {
    throw 'Precheck: FBL1N_FUTURE_PATH ausente en .env'
  }
  $futureParent = Split-Path -Parent $future
  if (-not (Test-Path -LiteralPath $future) -and -not (Test-Path -LiteralPath $futureParent)) {
    throw "Precheck: FBL1N_FUTURE_PATH y carpeta padre inexistentes: $future"
  }
  Write-Host 'PRECHECKS=OK'
}

$root = (Resolve-Path -LiteralPath $ProjectRoot).Path
$python = Join-Path $root '.venv\Scripts\python.exe'
$script = Join-Path $root 'scripts\run_diario.py'

if (-not (Test-Path -LiteralPath $python)) {
  throw "No existe el intérprete: $python"
}
if (-not (Test-Path -LiteralPath $script)) {
  throw "No existe el wrapper: $script"
}

$definition = [ordered]@{
  TaskName              = $taskName
  TaskPath              = $taskPath
  Execute               = $python
  Arguments             = "`"$script`""
  WorkingDirectory      = $root
  DaysOfWeek            = @('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday')
  At                    = '09:00'
  LogonType             = 'Interactive'
  RunLevel              = 'Limited'
  MultipleInstances     = 'IgnoreNew'
  StartWhenAvailable    = $true
  ExecutionTimeLimitHours = 3
  InitialState          = 'Disabled'
  UserId                = $env:USERNAME
}

if ($ShowDefinition) {
  $definition | ConvertTo-Json -Depth 5
  exit 0
}

$existing = Get-ScheduledTask -TaskName $taskName -TaskPath $taskPath -ErrorAction SilentlyContinue
if ($existing -and -not $Replace) {
  throw "La tarea $taskPath$taskName ya existe. Use -Replace para sobrescribir o elimine la tarea manualmente."
}

$action = New-ScheduledTaskAction -Execute $python -Argument "`"$script`"" -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday, Tuesday, Wednesday, Thursday, Friday -At 09:00
$settings = New-ScheduledTaskSettingsSet `
  -StartWhenAvailable `
  -MultipleInstances IgnoreNew `
  -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries `
  -ExecutionTimeLimit (New-TimeSpan -Hours 3)
$principal = New-ScheduledTaskPrincipal `
  -UserId $env:USERNAME `
  -LogonType Interactive `
  -RunLevel Limited

try {
  if ($existing -and $Replace) {
    Unregister-ScheduledTask -TaskName $taskName -TaskPath $taskPath -Confirm:$false
  }
  Register-ScheduledTask `
    -TaskName $taskName `
    -TaskPath $taskPath `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal | Out-Null
} catch {
  throw ("No se pudo registrar la tarea (¿permisos insuficientes para el usuario actual?): " + $_.Exception.Message)
}

# Siempre queda Disabled tras el registro, salvo -Enable con prechecks.
Disable-ScheduledTask -TaskName $taskName -TaskPath $taskPath | Out-Null

if ($Enable) {
  Invoke-Prechecks -Root $root
  Enable-ScheduledTask -TaskName $taskName -TaskPath $taskPath | Out-Null
  Write-Host "TASK=$taskPath$taskName Enabled=True"
} else {
  Write-Host "TASK=$taskPath$taskName Enabled=False (usar -Enable tras pruebas)"
}

$t = Get-ScheduledTask -TaskName $taskName -TaskPath $taskPath
$info = Get-ScheduledTaskInfo -InputObject $t
Write-Host ("Command={0} {1}" -f $python, $script)
Write-Host ("User={0}" -f $env:USERNAME)
Write-Host 'Days=Monday,Tuesday,Wednesday,Thursday,Friday At=09:00'
Write-Host 'LogonType=Interactive RunLevel=Limited MultipleInstances=IgnoreNew StartWhenAvailable=True ExecutionTimeLimit=3h'
Write-Host ("State={0} Enabled={1}" -f $t.State, ($t.Settings.Enabled))
Write-Host ("NextRunTime={0}" -f $info.NextRunTime)
