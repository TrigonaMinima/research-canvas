# Chaos

Behaviour when a dependency fails: the network down or slow, a run that dies, a server
restart mid-request, a corrupt or unwritable file. The app fails safely and loses nothing.

The suite lands with #64. Until then `make test-chaos` collects nothing and passes.
