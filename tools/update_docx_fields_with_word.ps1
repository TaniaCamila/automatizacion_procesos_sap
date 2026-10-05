param(
    [Parameter(Mandatory = $true)]
    [string]$InputDocx
)

$word = $null
$document = $null
try {
    $resolvedInput = (Resolve-Path -LiteralPath $InputDocx).Path
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $document = $word.Documents.Open($resolvedInput, $false, $false)
    foreach ($toc in $document.TablesOfContents) {
        $toc.Update()
    }
    $document.Fields.Update() | Out-Null
    foreach ($section in $document.Sections) {
        foreach ($header in $section.Headers) {
            $header.Range.Fields.Update() | Out-Null
        }
        foreach ($footer in $section.Footers) {
            $footer.Range.Fields.Update() | Out-Null
        }
    }
    $document.Save()
    Write-Output $resolvedInput
}
finally {
    if ($null -ne $document) {
        try { $document.Close($false) } catch { }
        try { [System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($document) | Out-Null } catch { }
    }
    if ($null -ne $word) {
        try { $word.Quit() } catch { }
        try { [System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($word) | Out-Null } catch { }
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
