# Example: Code Refactoring Loop

Delegates a refactor to the `coder` specialist and stops the moment a stop
condition -- "the test suite passes" -- is met, not after a fixed number of
turns.

```bash
pip install -e ../..
python run.py
```

Swap `MockProvider` for `AnthropicProvider()` (needs `ANTHROPIC_API_KEY`) to
run for real.
