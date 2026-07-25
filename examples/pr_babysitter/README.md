# Example: PR Babysitter Loop

Polls a pull request's CI/review state (via the `git`/`shell` tools) and
takes action -- fix, re-push, wait -- until it's mergeable. A realistic
"long-running background loop" shape.

```bash
pip install -e ../..
python run.py
```
