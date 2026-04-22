param(
    [string]$Provider = "heuristic_v1",
    [string]$DataFile = "benchmark_data/official/LoCoMo/data/locomo10.json",
    [string]$OutputDir = "C:/Users/USER/.spark-intelligence/artifacts/locomo-unseen-slice",
    [string]$ArtifactTag = "manual",
    [int]$ConversationLimit = 4,
    [int]$GraphLimit = 4
)

$ErrorActionPreference = "Stop"
$env:PYTHONUNBUFFERED = "1"

$chunkRuns = @(
    @{ Name = "conv41-43"; SampleIds = @("conv-41", "conv-42", "conv-43") },
    @{ Name = "conv44-47"; SampleIds = @("conv-44", "conv-47") },
    @{ Name = "conv48-50"; SampleIds = @("conv-48", "conv-49", "conv-50") }
)

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir | Out-Null
}

Write-Host "[chunked-locomo] provider=$Provider artifact_tag=$ArtifactTag"
Write-Host "[chunked-locomo] repo_root=$repoRoot"
Write-Host "[chunked-locomo] output_dir=$OutputDir"

foreach ($chunk in $chunkRuns) {
    $artifactPath = Join-Path $OutputDir ("fused-{0}-{1}-{2}.json" -f $Provider.Replace(":", "-"), $chunk.Name, $ArtifactTag)
    $args = @(
        "-m", "domain_chip_memory.cli",
        "run-locomo-multi-shadow-eval",
        $DataFile,
        "--provider", $Provider
    )
    foreach ($sampleId in $chunk.SampleIds) {
        $args += @("--sample-id", $sampleId)
    }
    $args += @(
        "--category", "1",
        "--category", "2",
        "--category", "3",
        "--exclude-missing-gold",
        "--fused-family-only",
        "--conversational-limit", "$ConversationLimit",
        "--graph-limit", "$GraphLimit",
        "--write", $artifactPath
    )

    Write-Host "[chunked-locomo] start chunk=$($chunk.Name) artifact=$artifactPath"
    python @args
    if ($LASTEXITCODE -ne 0) {
        throw "[chunked-locomo] failed chunk=$($chunk.Name) exit_code=$LASTEXITCODE"
    }
    if (-not (Test-Path $artifactPath)) {
        throw "[chunked-locomo] missing artifact for chunk=$($chunk.Name): $artifactPath"
    }
    $artifact = Get-Item $artifactPath
    Write-Host "[chunked-locomo] done chunk=$($chunk.Name) bytes=$($artifact.Length)"
}

Write-Host "[chunked-locomo] complete"
