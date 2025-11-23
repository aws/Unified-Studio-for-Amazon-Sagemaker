# AI Assistant Rules

**CRITICAL: Never commit code without explicit request from user.**

**CRITICAL: Never push changes to remote repository without explicit approval from user.**

**CRITICAL: For non-trivial changes (beyond syntax errors or simple fixes), request approval before making significant flow or architectural changes.**

## Q Task Tracking

Task progress and context are tracked in the `q-tasks/` folder:
- Location: `experimental/SMUS-CICD-pipeline-cli/q-tasks/`
- Files: `q-task-*.txt` (e.g., `q-task-build-ml-workflow.txt`)
- Purpose: Track progress, environment setup, debugging steps, and next actions
- Note: This folder is git-ignored for local development tracking only

## Approval Protocol

**Q Must Ask Before (Require Explicit Approval):**
- ✋ Committing code changes
- ✋ **Pushing to remote repository (NEVER without explicit approval)**
- ✋ Triggering workflows
- ✋ Deleting files or branches
- ✋ Merging branches

**Q Can Do Without Asking:**
- ✅ Reading files
- ✅ Analyzing logs
- ✅ Running local tests
- ✅ Checking git status
- ✅ Monitoring workflow status
- ✅ Suggesting fixes

**Approval Keywords:**
- "yes" / "ok" / "do it" / "fix" / "apply" → Proceed
- "no" / "wait" / "stop" / "don't" → Do not proceed
- "show me" / "what would" / "options" → Explain without doing
