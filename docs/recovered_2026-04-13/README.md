# Recovered Docs (Best-Effort)

This folder contains best-effort recovered copies for mojibake/corrupted markdown files.

Notes:
- Original files in `docs/` are kept unchanged.
- Original backups are stored in `docs/_encoding_backup_2026-04-13/`.
- Recovery method: reinterpret likely GB18030-mojibake text back to UTF-8 per line.
- Some characters were already lost before recovery (shown as `?` in recovered files) and require manual proofreading.

Suggested workflow:
1. Open the original and recovered files side by side.
2. Copy readable paragraphs from recovered files.
3. Manually fix remaining `?` placeholders.
4. Save final clean version in `docs/`.
