---
name: precision-editing
description: "Trigger: exact edit failure, Could not find the exact text, whitespace mismatch, editing existing files, or patching code. Apply a read-verify-edit workflow that prevents repeated exact-replacement failures."
license: Apache-2.0
metadata:
  author: el-gentleman
  version: "1.0"
---

# Precision Editing

## Activation Contract

Use this skill before editing an existing repository file when an exact replacement may fail, especially after an `edit` tool mismatch.

## Hard Rules

- Read the target file immediately before editing; never trust a stale excerpt.
- Match the smallest unique block. Verify uniqueness with search or a short script before calling `edit`.
- Preserve the file's existing indentation, line endings, quoting, and encoding.
- After any mismatch, stop and re-read the file. Do not retry the same replacement or guess whitespace.
- Do not use broad replacements when two nearby changes can be one atomic edit.
- Keep writes single-threaded and run `git diff --check` after edits.

## Decision Gates

1. **Known exact block:** use `edit` with the exact read-back text.
2. **Mismatch:** inspect `repr()`/line numbers, check symlink/path identity, then build a new exact block.
3. **Repeated or generated text:** use a narrowly scoped script or rewrite only after confirming the target count is exactly one; preserve a backup when the operation is destructive.
4. **Ambiguous match:** stop and ask for a scope decision; never choose a random occurrence.

## Execution Steps

1. Resolve the canonical repository path and target file.
2. Read the relevant region and search the target phrase.
3. Confirm the old block occurs exactly once and identify whitespace/line-ending details.
4. Apply one focused edit.
5. Re-read the changed region, run syntax/tests appropriate to the file, and run `git diff --check`.
6. Report the path, verification, and any remaining ambiguity.

## Output Contract

Report changed paths, whether the replacement was unique, verification results, and any mismatch recovery performed. Never claim an edit succeeded without fresh read-back evidence.
