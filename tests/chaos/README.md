# Chaos

Behaviour when a dependency fails: the network down or slow, a run that dies, a server
restart mid-request, a corrupt or unwritable file. The app fails safely and loses nothing.

Specs that need a browser live in `e2e/` and need the e2e session server, so `make test-chaos`
starts it. See the Chaos section of `tests/README.md` for what each file covers.
