# Stress

Behaviour at and past the limits: API load, concurrent edits, the biggest realistic canvas,
bulk writes. Each test asserts an explicit budget kept in `src/research_canvas/config.py`.

The suite lands with #63. Until then `make test-stress` collects nothing and passes.
