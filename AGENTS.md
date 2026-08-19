# Repository workflow

- After completing an in-scope code or documentation update, run the relevant tests.
- If the tests pass, create a focused Git commit for the completed update and push it to `origin/main`.
- Report the commit hash and test result to the user.
- Never commit local configuration, SQLite caches, Python caches, logs, credentials, or generated runtime state.
- Preserve unrelated user changes and keep commit messages concise and descriptive.
