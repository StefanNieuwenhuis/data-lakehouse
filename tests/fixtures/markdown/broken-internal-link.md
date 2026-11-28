# Broken internal link

This fixture links to [a file that does not exist](./does-not-exist.md).
`make lint-links` must reject it. The test is in
`tests/conventions/test_link_check.py`.
