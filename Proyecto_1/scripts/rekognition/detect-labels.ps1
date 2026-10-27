param(
  [string]$Bucket = $env:IMAGES_BUCKET_NAME,
  [string[]]$Keys = @(
    'Fotos_Publicadas/examples/labels-example-1.jpg',
    'Fotos_Publicadas/examples/labels-example-2.jpg'
  ),
  [switch]$Execute
)

$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($Bucket)) {
  $Bucket = 'semisocial-g15-images-581117996165'
}

Write-Output "Region: us-east-1"
Write-Output "Bucket: $Bucket"
Write-Output "MaxLabels: 20 | MinConfidence: 80"

foreach ($key in $Keys) {
  $request = @{
    Image = @{ S3Object = @{ Bucket = $Bucket; Name = $key } }
    MaxLabels = 20
    MinConfidence = 80
  } | ConvertTo-Json -Compress -Depth 5

  if (-not $Execute) {
    Write-Output "DRY-RUN $key"
    Write-Output $request
    continue
  }

  # Explicit opt-in: AWS CLI credentials must come from the instance profile
  # or the user's configured profile; no credentials are accepted as arguments.
  $response = aws rekognition detect-labels --region us-east-1 --cli-input-json $request | ConvertFrom-Json
  $labels = @($response.Labels | Where-Object { $_.Name -and $_.Confidence -ge 80 } | ForEach-Object {
    [ordered]@{
      name = $_.Name.Trim().ToLowerInvariant()
      confidence = [math]::Round([double]$_.Confidence, 2)
      sourceName = $_.Name
    }
  })
  [ordered]@{ imageKey = $key; labels = $labels; model = 'rekognition-detect-labels'; region = 'us-east-1' } |
    ConvertTo-Json -Depth 6
}
