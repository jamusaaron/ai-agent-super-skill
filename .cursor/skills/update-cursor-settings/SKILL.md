---
name: update-cursor-settings
description: Modify Cursor/VS Code user or workspace settings in settings.json. Use when changing editor settings, preferences, themes, font size, tab size, format on save, auto save, keybindings, agent text size, commit attribution, or any settings.json values.
license: MIT
metadata:
  author: jamusazza
  version: '1.0'
icon: settings
color: cyan
---

# Updating Cursor Settings

Modify Cursor/VS Code settings in `settings.json`. Use this when the user wants to change editor settings, preferences, configuration, themes, keybindings, or any `settings.json` values.

## Settings file location

| OS | User settings path |
|----|--------------------|
| macOS | `~/Library/Application Support/Cursor/User/settings.json` |
| Linux | `~/.config/Cursor/User/settings.json` |
| Windows | `%APPDATA%\Cursor\User\settings.json` |

Workspace settings live in `.vscode/settings.json` at the project root and apply only to that project.

## Before modifying settings

1. **Read the existing settings file** to understand current configuration
2. **Preserve existing settings** — only add or modify what the user requested
3. **Validate JSON syntax** before writing to avoid breaking the editor
4. **Choose the right file** — user settings are global; workspace settings are project-scoped

## Workflow

1. Identify whether the change is **user** (global) or **workspace** (this repo)
2. Read the target `settings.json`
3. Parse JSON (Cursor/VS Code settings support comments: `//` and `/* */`)
4. Add or update only the requested keys
5. Preserve all other existing settings and comments when possible
6. Write back with 2-space indentation
7. Tell the user what changed and whether a reload is needed

## User vs workspace vs Cursor-native config

| Kind | Path | Scope | Use for |
|------|------|-------|---------|
| User settings | OS path in the table above | All projects | Theme, font, agent chat text size, personal editor prefs |
| Workspace settings | `.vscode/settings.json` | This repo | Shared formatter, tab size, file associations |
| CLI config | `~/.cursor/cli-config.json` | Cursor CLI globally | Permissions, Vim mode, commit/PR attribution |
| Project CLI permissions | `.cursor/cli.json` | This repo, CLI only | Extra allow/deny rules for the CLI agent |
| MCP servers | `.cursor/mcp.json` or `~/.cursor/mcp.json` | Project or user | Tools the agent can call |
| Rules | `.cursor/rules/*.mdc` | Project | Persistent agent instructions |
| Skills | `.cursor/skills/<name>/SKILL.md` | Project | Domain workflows the agent can load |

Do **not** put editor `settings.json` keys into `cli-config.json`, and do **not** put CLI permissions into `settings.json`.

## Commit attribution

When the user asks about commit attribution, clarify whether they want the **CLI agent** or the **IDE agent**:

- **CLI agent:** edit `~/.cursor/cli-config.json` (`attribution.attributeCommitsToAgent`, `attribution.attributePRsToAgent`)
- **IDE agent:** controlled from **Cursor Settings > Agent > Attribution**, not `settings.json`

## Common requests → settings

| User request | Setting | Typical value |
|--------------|---------|---------------|
| bigger/smaller font | `editor.fontSize` | `16` |
| change tab size | `editor.tabSize` | `2` or `4` |
| format on save | `editor.formatOnSave` | `true` |
| word wrap | `editor.wordWrap` | `"on"` |
| change theme | `workbench.colorTheme` | `"Default Dark Modern"` |
| hide minimap | `editor.minimap.enabled` | `false` |
| auto save | `files.autoSave` | `"afterDelay"` |
| line numbers | `editor.lineNumbers` | `"on"` |
| bracket matching | `editor.bracketPairColorization.enabled` | `true` |
| cursor style | `editor.cursorStyle` | `"line"` |
| smooth scrolling | `editor.smoothScrolling` | `true` |
| agent chat text size | `cursor.composer.textSizeScale` | `1.15`–`1.3` |
| agent text size enum | `cursor.agents.textSize` | `"large"` or `"extraLarge"` |
| window zoom | `window.zoomLevel` | `1` |

See [references/settings-catalog.md](references/settings-catalog.md) for a longer catalog, including Cursor-specific keys.

## Important notes

1. **JSON with comments:** `settings.json` may contain `//` and `/* */`. Preserve comments if possible. Do not use a strict JSON parser that drops them unless you have no other option.
2. **Restart may be required:** some settings apply immediately; others need Reload Window. Tell the user.
3. **Backup:** for significant changes, mention undo via Ctrl/Cmd+Z in the settings file, or git revert if the file is tracked.
4. **Cloud / remote agents:** editing `~/.config/Cursor/User/settings.json` on a cloud VM does **not** change the user's local IDE. For cloud work, put shared defaults in `.vscode/settings.json` and commit them.

## Safety

- Never overwrite the whole file with only the new key
- Never store secrets, API keys, or tokens in settings files
- If the file is missing, create `{ }` then add the requested keys
- If JSON is invalid, stop and report rather than inventing a rewrite
