# Chaos

Behaviour when a dependency fails: the network down or slow, a run that dies, a server
restart mid-request, a corrupt or unwritable file. The app fails safely and loses nothing.

Bad files on disk landed with #50 (`api/`, `e2e/`). The rest of the suite lands with #64.
