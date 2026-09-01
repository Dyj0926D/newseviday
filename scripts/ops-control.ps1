[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'High')]
param(
  [ValidateSet('Status', 'Archive', 'ContentTrial', 'WeeklyOnly')]
  [string]$Mode = 'Status',

  [string]$EndDate,

  [switch]$AllowModel,

  [switch]$AutoPublish,

  [string]$Repository = 'Dyj0926D/newseviday'
)

$ErrorActionPreference = 'Stop'
$TrackedVariables = @(
  'DAILY_REFRESH_ENABLED',
  'DAILY_REFRESH_END_DATE',
  'DAILY_REFRESH_ALLOW_MODEL',
  'DAILY_REFRESH_AUTO_MERGE',
  'WEEKLY_BRIEF_ENABLED',
  'WEEKLY_REFRESH_AUTO_MERGE'
)

function Assert-GitHubCli {
  if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw '未找到 GitHub CLI（gh）。请先安装并执行 gh auth login。'
  }
  $null = gh auth status 2>$null
  if ($LASTEXITCODE -ne 0) {
    throw 'GitHub CLI 尚未登录。请先执行 gh auth login。'
  }
}

function Set-RepositoryVariable {
  param(
    [Parameter(Mandatory = $true)][string]$Name,
    [Parameter(Mandatory = $true)][string]$Value
  )
  gh variable set $Name --body $Value --repo $Repository
  if ($LASTEXITCODE -ne 0) {
    throw "设置仓库变量 $Name 失败。"
  }
}

function Remove-RepositoryVariableIfPresent {
  param([Parameter(Mandatory = $true)][string]$Name)
  $null = gh variable get $Name --repo $Repository 2>$null
  if ($LASTEXITCODE -eq 0) {
    gh variable delete $Name --repo $Repository
    if ($LASTEXITCODE -ne 0) {
      throw "删除仓库变量 $Name 失败。"
    }
  }
}

function Show-ControlStatus {
  $rows = gh variable list --repo $Repository
  if ($LASTEXITCODE -ne 0) {
    throw '读取仓库变量失败。'
  }
  $rows | Where-Object {
    $name = ($_ -split "`t")[0]
    $TrackedVariables -contains $name
  }
}

Assert-GitHubCli

if ($Mode -eq 'Status') {
  Show-ControlStatus
  exit 0
}

$targetDescription = switch ($Mode) {
  'Archive' { '关闭日报与周报，并清理日报截止日期' }
  'WeeklyOnly' { '关闭日报，只保留周报' }
  'ContentTrial' { '开启有截止日期的日报与周报受控运行' }
}

if (-not $PSCmdlet.ShouldProcess($Repository, $targetDescription)) {
  exit 0
}

switch ($Mode) {
  'Archive' {
    Set-RepositoryVariable 'DAILY_REFRESH_ENABLED' 'false'
    Set-RepositoryVariable 'WEEKLY_BRIEF_ENABLED' 'false'
    Set-RepositoryVariable 'DAILY_REFRESH_ALLOW_MODEL' 'false'
    Set-RepositoryVariable 'DAILY_REFRESH_AUTO_MERGE' 'false'
    Set-RepositoryVariable 'WEEKLY_REFRESH_AUTO_MERGE' 'false'
    Remove-RepositoryVariableIfPresent 'DAILY_REFRESH_END_DATE'
  }
  'WeeklyOnly' {
    Set-RepositoryVariable 'DAILY_REFRESH_ENABLED' 'false'
    Set-RepositoryVariable 'WEEKLY_BRIEF_ENABLED' 'true'
    Set-RepositoryVariable 'DAILY_REFRESH_ALLOW_MODEL' 'false'
    Set-RepositoryVariable 'DAILY_REFRESH_AUTO_MERGE' 'false'
    Set-RepositoryVariable 'WEEKLY_REFRESH_AUTO_MERGE' 'false'
    Remove-RepositoryVariableIfPresent 'DAILY_REFRESH_END_DATE'
  }
  'ContentTrial' {
    if ([string]::IsNullOrWhiteSpace($EndDate)) {
      throw 'ContentTrial 模式必须通过 -EndDate 指定截止日期，例如 2026-09-07。'
    }
    $parsedEndDate = [datetime]::MinValue
    if (-not [datetime]::TryParseExact(
        $EndDate,
        'yyyy-MM-dd',
        [Globalization.CultureInfo]::InvariantCulture,
        [Globalization.DateTimeStyles]::None,
        [ref]$parsedEndDate
      )) {
      throw 'EndDate 必须使用 yyyy-MM-dd 格式。'
    }
    try {
      $chinaTimeZone = [TimeZoneInfo]::FindSystemTimeZoneById('China Standard Time')
    }
    catch {
      $chinaTimeZone = [TimeZoneInfo]::FindSystemTimeZoneById('Asia/Shanghai')
    }
    $today = [TimeZoneInfo]::ConvertTime((Get-Date), $chinaTimeZone).Date
    if ($parsedEndDate -lt $today) {
      throw 'EndDate 不能早于今天。'
    }
    if ($parsedEndDate -gt $today.AddDays(31)) {
      throw '单次受控运行最长 31 天，请缩短 EndDate。'
    }

    Set-RepositoryVariable 'DAILY_REFRESH_END_DATE' $EndDate
    Set-RepositoryVariable 'DAILY_REFRESH_ALLOW_MODEL' $AllowModel.IsPresent.ToString().ToLowerInvariant()
    Set-RepositoryVariable 'DAILY_REFRESH_AUTO_MERGE' $AutoPublish.IsPresent.ToString().ToLowerInvariant()
    Set-RepositoryVariable 'WEEKLY_REFRESH_AUTO_MERGE' $AutoPublish.IsPresent.ToString().ToLowerInvariant()
    Set-RepositoryVariable 'DAILY_REFRESH_ENABLED' 'true'
    Set-RepositoryVariable 'WEEKLY_BRIEF_ENABLED' 'true'
  }
}

Write-Host "已应用 $Mode 模式。当前开关："
Show-ControlStatus
