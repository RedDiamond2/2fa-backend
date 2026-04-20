# cd C:\BioIR\RedDiamond_TAGIR\frontend\src
# .\Tree.ps1
# Show-DevTree -Path "C:\BioIR\RedDiamond_TAGIR\frontend\src"
# cd C:\BioIR\RedDiamond_TAGIR\backend\app
# .\Tree.ps1
# Show-DevTree -Path "C:\BioIR\RedDiamond_TAGIR\backend\app"

function Show-DevTree {
    param (
        [string]$Path = ".",
        [string]$Prefix = "",
        [string]$OutputFile = $null
    )

    $IgnoreDirs = @(
        "__pycache__",
        "node_modules",
        "dist",
        "assets",
        "build",
        ".git"
    )

    $IgnoreFiles = @(
        "*.pyc",
        "*.log",
        "*.tmp"
    )

    $items = Get-ChildItem -LiteralPath $Path | Where-Object {
        if ($_.PSIsContainer) {
            return $IgnoreDirs -notcontains $_.Name
        }

        foreach ($pattern in $IgnoreFiles) {
            if ($_.Name -like $pattern) {
                return $false
            }
        }

        return $true
    }

    $count = $items.Count

    for ($i = 0; $i -lt $count; $i++) {
        $item = $items[$i]

        $isLast = ($i -eq $count - 1)
        $connector = if ($isLast) { "\-- " } else { "|-- " }

        $line = "$Prefix$connector$($item.Name)"

        if ($OutputFile) {
            Add-Content -Path $OutputFile -Value $line
        } else {
            Write-Output $line
        }

        if ($item.PSIsContainer) {
            $newPrefix = if ($isLast) { "$Prefix    " } else { "$Prefix|   " }
            Show-DevTree -Path $item.FullName -Prefix $newPrefix -OutputFile $OutputFile
        }
    }
}