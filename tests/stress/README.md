# Stress

Behaviour at and past the limits: concurrent writes on one canvas, more streams than run
slots, racing merges, the biggest inputs, and latency budgets on the hot endpoints. Each test
asserts an explicit budget kept in `src/research_canvas/config.py`.

Run with `make test-stress`. The summary of each spec is in `tests/README.md`, under Stress.
