---
description: One-time setup for the architect-team plugin. Checks for and installs required dependencies (openspec CLI, Python test tools, Playwright + browsers) and verifies prerequisite plugins (superpowers, cartographer, ralph-loop) are installed.
argument-hint: "[--check-only] [--force-reinstall]"
allowed-tools: ["Bash(python3:*)", "Bash(${CLAUDE_PLUGIN_ROOT}/scripts/setup/setup.py:*)"]
---

# Architect-Team Setup

Run the idempotent setup script. It detects each dependency, installs only what's missing, and reports what it did.

```!
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/setup/setup.py" $ARGUMENTS || python "${CLAUDE_PLUGIN_ROOT}/scripts/setup/setup.py" $ARGUMENTS
```

The `|| python ...` fallback handles default Windows python.org installs where only `python` is on PATH (`python3` triggers the Microsoft Store shim there); on Unix the first form succeeds and the fallback never fires.

After the script finishes, summarize:
- Dependencies installed or already present
- Plugins required but missing (with the exact `/plugin install` command to run)
- Any failures and how to remediate them

If `cartographer`, `ralph-loop`, or `superpowers` are missing, instruct the user to run the corresponding `/plugin install <name>@<marketplace>` commands. The setup script cannot install plugins on the user's behalf.
