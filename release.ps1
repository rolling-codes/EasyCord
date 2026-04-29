param(
    [Parameter(Mandatory = $true)]
    [string]$Version
)

if ($Version -match '^v') {
    $Tag = $Version
} else {
    $Tag = "v$Version"
}

if ($Tag -notmatch '^v\d+\.\d+\.\d+$') {
    throw "Version must be in X.Y.Z format (or vX.Y.Z)."
}

git tag $Tag
git push origin $Tag
