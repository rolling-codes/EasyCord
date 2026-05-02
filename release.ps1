param(
    [Parameter(Mandatory = $true)]
    [string]$Version
)

if ($Version -match '^v') {
    $Tag = $Version
} else {
    $Tag = "v$Version"
}

if ($Tag -notmatch '^v\d+\.\d+\.\d+(-[\w.]+)?$') {
    throw "Version must be in X.Y.Z or X.Y.Z-prerelease format (or vX.Y.Z, vX.Y.Z-beta.1, etc)."
}

git tag $Tag
git push origin $Tag
