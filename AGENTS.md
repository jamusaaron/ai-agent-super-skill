# Agent instructions

This repository is an **AI Agent Builder Super-Skill**: a portable `SKILL.md` plus Cursor project skills.

## What to change

- Keep the root `SKILL.md` as the canonical long-form reference.
- Keep Cursor-specific slash workflows under `.cursor/skills/<skill-name>/SKILL.md`.
- Keep `README.md` in sync with the table of contents and sources list.
- Preserve YAML frontmatter: quoted `version`, trigger-oriented `description`, `name` matching the parent folder for nested skills.

## Cursor settings

When the user asks to change editor, theme, font, format-on-save, or other `settings.json` values, follow `.cursor/skills/update-cursor-settings/SKILL.md`.

- Shared repo defaults belong in `.vscode/settings.json`.
- Personal IDE defaults belong in the user `settings.json` on their machine, not in this repo.
- CLI attribution and permissions belong in `~/.cursor/cli-config.json` or `.cursor/cli.json`, not `settings.json`.
