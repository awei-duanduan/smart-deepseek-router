# Security

DeepSeek Harness agents can execute commands with the permissions of the host process. Git worktrees, path audits, patch review, and the credential proxy reduce common mistakes; they are not an operating-system sandbox.

Use this skill only with trusted repositories and reviewed task contracts. Use a restricted virtual machine or container when the repository or generated commands are not fully trusted. Never commit API keys, `.env` files, encrypted credential blobs, capability caches, or private run logs.

Report a vulnerability through GitHub's private vulnerability reporting feature when it is enabled for the repository. Avoid including live credentials, private source code, or exploit data from systems you do not own.
