param(
    [string]$ImageTag = "",
    [string]$TerraformDir = "infra/terraform",
    [string]$Region = "",
    [switch]$SkipImageCheck,
    [switch]$SkipTerraformInit
)

$ErrorActionPreference = "Stop"

function Invoke-External {
    param(
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command,
        [Parameter(Mandatory = $true)]
        [string]$ErrorMessage
    )

    $output = & $Command
    if ($LASTEXITCODE -ne 0) {
        throw $ErrorMessage
    }

    return $output
}

function Resolve-RepoRoot {
    $candidates = @()

    if ($PSScriptRoot) {
        $candidates += $PSScriptRoot
    }
    if ($MyInvocation.MyCommand.Path) {
        $candidates += (Split-Path -Parent $MyInvocation.MyCommand.Path)
    }

    $cwd = (Get-Location).Path
    $candidates += $cwd
    $candidates += (Join-Path $cwd "scripts")

    foreach ($candidate in $candidates | Select-Object -Unique) {
        if (-not $candidate) {
            continue
        }

        $directInfra = Join-Path $candidate "infra/terraform"
        $directApp = Join-Path $candidate "app"
        if ((Test-Path $directInfra) -and (Test-Path $directApp)) {
            return (Resolve-Path $candidate).Path
        }

        $parent = Split-Path -Parent $candidate
        if (-not $parent) {
            continue
        }

        $parentInfra = Join-Path $parent "infra/terraform"
        $parentApp = Join-Path $parent "app"
        if ((Test-Path $parentInfra) -and (Test-Path $parentApp)) {
            return (Resolve-Path $parent).Path
        }
    }

    throw "Could not determine repository root. Run the script from the repository root or the scripts directory."
}

$repoRoot = Resolve-RepoRoot
$terraformDirPath = (Resolve-Path (Join-Path $repoRoot $TerraformDir)).Path
$terraformExePath = Join-Path $terraformDirPath "terraform.exe"
$terraformExe = if (Test-Path $terraformExePath) {
    $terraformExePath
} else {
    "terraform"
}

if (-not $ImageTag) {
    $ImageTag = (
        Invoke-External {
            git -C $repoRoot rev-parse --short=12 HEAD
        } "Failed to determine the current git commit SHA."
    ).Trim()
}

if (-not $Region) {
    $tfvarsPath = Join-Path $terraformDirPath "terraform.tfvars"
    if (Test-Path $tfvarsPath) {
        $regionMatch = Select-String -Path $tfvarsPath -Pattern '^\s*aws_region\s*=\s*"([^"]+)"' | Select-Object -First 1
        if ($regionMatch) {
            $Region = $regionMatch.Matches[0].Groups[1].Value
        }
    }
}

if (-not $Region) {
    $Region = "eu-north-1"
}

Push-Location $terraformDirPath
try {
    if (-not $SkipTerraformInit) {
        Invoke-External {
            & $terraformExe init -input=false -no-color
        } "terraform init failed."
    }

    $ecrRepositoryUrl = (
        Invoke-External {
            & $terraformExe output -raw ecr_repository_url
        } "Failed to read Terraform output ecr_repository_url."
    ).Trim()

    $workerTaskDefinitionBefore = (
        Invoke-External {
            & $terraformExe output -raw worker_task_definition_arn
        } "Failed to read Terraform output worker_task_definition_arn."
    ).Trim()

    $webhookLambdaName = (
        Invoke-External {
            & $terraformExe output -raw webhook_lambda_name
        } "Failed to read Terraform output webhook_lambda_name."
    ).Trim()
}
finally {
    Pop-Location
}

$repositoryName = ($ecrRepositoryUrl -split "/")[-1]
$imageUri = "${ecrRepositoryUrl}:${ImageTag}"
$deployVarsPath = Join-Path $terraformDirPath "deploy.auto.tfvars.json"

if (-not $SkipImageCheck) {
    Invoke-External {
        aws ecr describe-images `
            --region $Region `
            --repository-name $repositoryName `
            --image-ids "imageTag=$ImageTag" `
            --output json
    } "ECR image tag '$ImageTag' was not found in repository '$repositoryName'."
}

@{
    container_image = $imageUri
} | ConvertTo-Json | Set-Content -Path $deployVarsPath -Encoding ascii

Push-Location $terraformDirPath
try {
    Invoke-External {
        & $terraformExe apply -input=false -auto-approve -no-color "-var-file=$deployVarsPath"
    } "terraform apply failed."

    $workerTaskDefinitionAfter = (
        Invoke-External {
            & $terraformExe output -raw worker_task_definition_arn
        } "Failed to read updated Terraform output worker_task_definition_arn."
    ).Trim()
}
finally {
    Pop-Location
}

$lambdaTaskDefinition = (
    Invoke-External {
        aws lambda get-function-configuration `
            --function-name $webhookLambdaName `
            --region $Region `
            --query "Environment.Variables.ECS_TASK_DEFINITION" `
            --output text
    } "Failed to read the Lambda webhook environment."
).Trim()

if ($lambdaTaskDefinition -ne $workerTaskDefinitionAfter) {
    throw "Lambda webhook still points to '$lambdaTaskDefinition' instead of '$workerTaskDefinitionAfter'."
}

[pscustomobject]@{
    Region = $Region
    ImageTag = $ImageTag
    ImageUri = $imageUri
    DeployVarsFile = $deployVarsPath
    WorkerTaskDefinitionBefore = $workerTaskDefinitionBefore
    WorkerTaskDefinitionAfter = $workerTaskDefinitionAfter
    LambdaFunction = $webhookLambdaName
    LambdaTaskDefinition = $lambdaTaskDefinition
} | ConvertTo-Json -Depth 3
