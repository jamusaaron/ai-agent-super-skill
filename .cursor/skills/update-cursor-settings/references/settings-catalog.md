# Cursor / VS Code settings catalog

Load this file when the requested setting is not in the short table in `SKILL.md`.

## Editor

| Setting | Type | Notes |
|---------|------|-------|
| `editor.fontSize` | number | Editor font size in px |
| `editor.fontFamily` | string | Font stack |
| `editor.tabSize` | number | Spaces per tab |
| `editor.insertSpaces` | boolean | Insert spaces when pressing Tab |
| `editor.detectIndentation` | boolean | Infer tab size from the file |
| `editor.wordWrap` | `"off"` \| `"on"` \| `"wordWrapColumn"` \| `"bounded"` | |
| `editor.formatOnSave` | boolean | |
| `editor.formatOnPaste` | boolean | |
| `editor.minimap.enabled` | boolean | |
| `editor.lineNumbers` | `"on"` \| `"off"` \| `"relative"` \| `"interval"` | |
| `editor.rulers` | number[] | Vertical rulers |
| `editor.bracketPairColorization.enabled` | boolean | |
| `editor.cursorStyle` | `"line"` \| `"block"` \| `"underline"` \| `"line-thin"` \| `"block-outline"` \| `"underline-thin"` | |
| `editor.smoothScrolling` | boolean | |
| `editor.renderWhitespace` | `"none"` \| `"boundary"` \| `"selection"` \| `"trailing"` \| `"all"` | |
| `editor.linkedEditing` | boolean | Rename paired tags together |

## Workbench / files / terminal

| Setting | Type | Notes |
|---------|------|-------|
| `workbench.colorTheme` | string | Theme id, e.g. `Default Dark Modern` |
| `workbench.iconTheme` | string | |
| `workbench.sideBar.location` | `"left"` \| `"right"` | |
| `workbench.startupEditor` | string | |
| `window.zoomLevel` | number | Scales the whole UI, including Agent |
| `files.autoSave` | `"off"` \| `"afterDelay"` \| `"onFocusChange"` \| `"onWindowChange"` | |
| `files.exclude` | object | Hide files in the explorer |
| `files.associations` | object | Map glob → language id |
| `files.insertFinalNewline` | boolean | |
| `files.trimTrailingWhitespace` | boolean | |
| `terminal.integrated.fontSize` | number | |
| `terminal.integrated.fontFamily` | string | |
| `terminal.integrated.defaultProfile.linux` | string | |

## Cursor-specific (settings.json)

These keys are consumed by the Cursor IDE. Names and availability can change across Cursor versions.

| Setting | Type | Notes |
|---------|------|-------|
| `cursor.composer.textSizeScale` | number | Scales Agent/Composer chat text. `1.0` is default; `1.15`–`1.3` is a common accessibility bump |
| `cursor.agents.textSize` | string | UI enum such as `"default"`, `"large"`, `"extraLarge"` |

If a Cursor-specific setting does not apply after save:

1. Reload Window
2. Confirm the key is in **user** settings, not only workspace settings
3. As a fallback for chat readability, use `window.zoomLevel` (this scales the entire IDE)

## Language overrides

Use `[languageId]` blocks for per-language settings:

```json
{
  "[python]": {
    "editor.tabSize": 4,
    "editor.formatOnSave": true
  },
  "[markdown]": {
    "editor.wordWrap": "on",
    "editor.quickSuggestions": {
      "other": true,
      "comments": false,
      "strings": false
    }
  }
}
```

## CLI config (not settings.json)

Path: `~/.cursor/cli-config.json` (Windows: `%USERPROFILE%\.cursor\cli-config.json`).

Pure JSON, no comments. Project-level permissions only: `.cursor/cli.json`.

| Field | Notes |
|-------|-------|
| `editor.vimMode` | CLI Vim keybindings |
| `permissions.allow` / `permissions.deny` | CLI tool permissions |
| `approvalMode` | `allowlist`, `auto-review`, or `unrestricted` |
| `attribution.attributeCommitsToAgent` | CLI commit trailer |
| `attribution.attributePRsToAgent` | CLI PR footer |
| `network.useHttp1ForAgent` | HTTP/1.1 fallback for enterprise proxies |

See https://cursor.com/docs/cli/reference/configuration.md

## Files that are not settings.json

Do not treat these as editor settings:

| File | Purpose |
|------|---------|
| `.cursor/mcp.json` | Project MCP servers |
| `~/.cursor/mcp.json` | User MCP servers |
| `.cursor/rules/*.mdc` | Project rules |
| `AGENTS.md` | Simple agent instructions |
| `.cursor/hooks.json` | Agent lifecycle hooks |
| `.cursor/sandbox.json` | Workspace sandbox policy |
| `.cursor/environment.json` | Cloud Agent environment |
