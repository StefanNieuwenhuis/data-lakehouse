# Broken internal link

This fixture links to [a file that does not exist](./does-not-exist.md).
`make test-fixtures` must reject it. The case is listed in
`tests/fixtures/conventions/links-invalid.txt`.
