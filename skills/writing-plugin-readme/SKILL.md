---
name: writing-plugin-readme
description: Use when writing, structuring, or updating a comprehensive, professional README document for this plugin or its individual tools and resources.
---

# Writing Plugin README

## Overview
A guide for writing clear, readable, and highly professional README documents for plugins, tools, and sub-resources within this repository. 

## When to Use
- You need to write or update the main repository `README.md` for this plugin.
- You are documenting a new script, tool, or reference catalog.
- You want to ensure the README has consistent structure, copy-pasteable commands, and clear setup guidelines.

## Essential README Checklist
A professional README for a tool or plugin must include these sections:

1. **Header/Title**: Clear title and a 1-2 sentence high-level summary of what the plugin/tool does.
2. **Features**: Bulleted list of key features or capabilities.
3. **Prerequisites & Installation**: Explicit dependencies (e.g., Python packages, `yt-dlp`, SQLite3) and command-line instructions to set up.
4. **Usage Guide**: Real-world CLI examples with expected input/output.
5. **Directory / Architecture Map**: Visual chart or list mapping key files and directories.
6. **Contributing & License**: Basic contribution rules and license terms.

## Core Templates

### 1. Main Plugin README Template
```markdown
# Plugin Name

A brief 1-2 sentence description explaining the purpose of this plugin and who it is built for.

## Features
- **Feature A**: Description of what Feature A does.
- **Feature B**: Description of what Feature B does.

## Prerequisites & Installation
Ensure you have the following installed on your system:
- Python 3.10+
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) (for media downloads)

Install skills to your agent via the Skills CLI:
```bash
# Install all skills globally
npx skills add zenithth/anibon-stream-synthesis --all -g

# Or install a specific skill (e.g. anibon-timestamper)
npx skills add zenithth/anibon-stream-synthesis --skill anibon-timestamper -g -y
```

## Quick Start & Usage
Provide a simple, copy-pasteable command to get started immediately:

```bash
python3 scripts/run_tool.py --argument value
```

### Options
- `--verbose`: Enable detailed logs.
- `--limit`: Max number of items to process.

## File Structure
- `scripts/`: Python utility scripts.
- `skills/`: Nested agent sub-skills.
- `tests/`: Automated unit and integration tests.

## License
Distributed under the MIT License. See `LICENSE` for details.
```

## Formatting Rules
- **Use Code Blocks**: Always wrap commands, options, and code snippets in fenced code blocks with language tags (`bash`, `python`, `json`).
- **Use Alert Boxes Strategically**: Use GitHub alerts (`> [!NOTE]`, `> [!IMPORTANT]`, `> [!WARNING]`) to highlight environment requirements or licensing constraints.
- **Checklist Formatting**: Use standard markdown checkboxes (`- [ ]`) for installation tasklists or configurations.

## Common Mistakes
- **Vague Commands**: Documenting a command like `python run.py` without specifying the relative path or required arguments. Always write exact paths (e.g., `python3 scripts/run_tool.py`).
- **Missing Prerequisites**: Forgetting to mention external CLI tools (like `ffmpeg` or `yt-dlp`) that are not standard Python libraries.
- **Placeholder Text**: Leaving incomplete sections or placeholder bracket text like `<insert details here>`. Fill in or omit.
