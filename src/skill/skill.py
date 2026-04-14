#!/usr/bin/env python3
"""
Defines the Skill class, which represents a workflow skill.
"""

import re
import shutil
from pathlib import Path
from typing import List, Optional


# Path configuration - use absolute paths based on project structure
SCRIPT_DIR = Path(__file__).parent.resolve()  # src/skill/
SRC_DIR = SCRIPT_DIR.parent  # src/
PROJECT_ROOT = SRC_DIR.parent  # ProteinMCP root


class Skill:
    """Represents a workflow skill defined in a markdown file."""

    def __init__(
        self,
        name: str,
        file_path: Path,
        description: Optional[str] = None,
        required_mcps: Optional[List[str]] = None,
    ):
        """
        Initializes a Skill instance.

        Args:
            name: The name of the skill, derived from the filename.
            file_path: The path to the skill's markdown file.
            description: Optional description from config (overrides file parsing).
            required_mcps: Optional list of required MCPs from config.
        """
        self.name = name
        self.file_path = file_path
        self._description = description
        self._required_mcps = required_mcps

        # Derive command name from skill name
        command_name_base = self.name.replace("_", "-")
        if "modeling" in command_name_base:
            self.command_name = command_name_base.replace("modeling", "model")
        else:
            self.command_name = command_name_base

        # Install to GLOBAL ~/.claude/ so skills are discoverable from any working directory
        # (was PROJECT_ROOT/.claude which trapped skills inside the ProteinMCP repo).
        self.claude_commands_dir = Path.home() / ".claude" / "commands"
        self.claude_skills_dir = Path.home() / ".claude" / "skills"

        # Slash command stays as a flat .md file in commands/
        self.command_file_path = self.claude_commands_dir / f"{self.command_name}.md"

        # Global skills use directory-with-SKILL.md format (matches biopython, adaptyv:*, etc.)
        self.skill_dir_name = self.name.replace("_", "-")
        self.skill_dir_path = self.claude_skills_dir / self.skill_dir_name
        self.skill_file_path = self.skill_dir_path / "SKILL.md"

    @property
    def description(self) -> str:
        """Returns description from config or extracts from skill file."""
        # Use config description if available
        if self._description:
            return self._description

        # Fall back to parsing from file
        try:
            content = self.file_path.read_text()
            # Find first non-empty line after the title
            lines = content.splitlines()
            for i, line in enumerate(lines):
                if line.strip().startswith("#"):  # title
                    for desc_line in lines[i + 1 :]:
                        if desc_line.strip():
                            return desc_line.strip()
            return "No description found."
        except Exception:
            return "Could not read description."

    def get_required_mcps(self) -> List[str]:
        """Returns required MCPs from config or parses from skill file."""
        # Use config MCPs if available
        if self._required_mcps is not None:
            return self._required_mcps

        # Fall back to parsing from file
        try:
            content = self.file_path.read_text()
            matches = re.findall(r"pmcp install ([\w_]+)", content)
            return sorted(list(set(matches)))
        except Exception:
            return []

    def get_cleanup_mcps(self) -> List[str]:
        """Returns MCPs to cleanup (same as required_mcps)."""
        # Cleanup MCPs are the same as required MCPs
        return self.get_required_mcps()

    def get_status(self) -> str:
        """Checks if the skill is installed at the global location."""
        is_skill_installed = self.skill_file_path.exists()
        is_legacy_command = self.command_file_path.exists()

        if is_skill_installed and is_legacy_command:
            return "✅ Installed (global) ⚠️ legacy command file present — run uninstall+install to clean"
        elif is_skill_installed:
            return "✅ Installed (global)"
        elif is_legacy_command:
            return "🟡 Legacy command-only install — run install to upgrade"
        else:
            return "❌ Not Installed"

    def _build_skill_md_with_frontmatter(self) -> str:
        """
        Build SKILL.md content by prepending YAML frontmatter to the source body.

        Claude Code's global skill discovery requires `name` and `description` in
        YAML frontmatter. Source workflow-skills/*.md files don't carry frontmatter,
        so we synthesize it from configs.yaml at install time (single source of truth
        for description, no duplication in source files).
        """
        body = self.file_path.read_text()
        # Description is required; fall back to first non-title line if config missing.
        desc = self.description.replace("\n", " ").strip()
        # Escape any frontmatter delimiter accidentally in description.
        desc = desc.replace("---", "—")
        frontmatter = (
            "---\n"
            f"name: {self.skill_dir_name}\n"
            f"description: {desc}\n"
            "---\n\n"
        )
        return frontmatter + body

    def install(self):
        """
        Installs the skill globally so it's discoverable from any working directory.

        Writes only ~/.claude/skills/<name>/SKILL.md (directory + SKILL.md format
        with synthesized YAML frontmatter). Does NOT write to ~/.claude/commands/
        because Claude Code indexes commands/*.md as skills too, which would create
        a duplicate entry (one from skills/ with proper frontmatter, one from
        commands/ falling back to the H1 title).
        """
        try:
            self.skill_dir_path.mkdir(parents=True, exist_ok=True)

            # Global skill: write SKILL.md with synthesized YAML frontmatter
            self.skill_file_path.write_text(self._build_skill_md_with_frontmatter())

            print(f"  Installed skill to: {self.skill_file_path}")
            return True
        except Exception as e:
            print(f"  Error installing skill '{self.name}': {e}")
            return False

    def uninstall(self):
        """
        Uninstalls the skill by removing the global SKILL.md.

        Removes the SKILL.md file and the skill directory (only if empty — protects
        any user-added files like references/, notes/, etc.). Also removes any
        legacy command file from ~/.claude/commands/ for backwards compatibility
        with previous installs.
        """
        removed = False
        try:
            # Legacy cleanup: previous versions wrote to commands/ which caused
            # duplicate skill registrations. Remove if present.
            if self.command_file_path.exists():
                self.command_file_path.unlink()
                print(f"  Removed legacy command: {self.command_file_path}")
                removed = True
            if self.skill_file_path.exists():
                self.skill_file_path.unlink()
                print(f"  Removed skill: {self.skill_file_path}")
                removed = True
            # Remove the skill directory only if it's empty (don't nuke user additions)
            if self.skill_dir_path.exists() and not any(self.skill_dir_path.iterdir()):
                self.skill_dir_path.rmdir()
                print(f"  Removed dir:   {self.skill_dir_path}")

            if not removed:
                print("  Skill not found, nothing to remove.")
            return True
        except Exception as e:
            print(f"  Error uninstalling skill '{self.name}': {e}")
            return False

    def get_execution_steps(self):
        """Parses the skill file for execution steps (prompts)."""
        content = self.file_path.read_text()
        steps = re.split(r"\n(?:---\n|## Step \d+)", content)

        prompts = []
        for step in steps:
            if "**Prompt:**" in step:
                prompt_text = step.split("**Prompt:**")[1].strip()
                
                # clean up prompt text
                prompt_lines = [line.strip(">").strip() for line in prompt_text.split("\n")]
                cleaned_prompt = "\n".join(line for line in prompt_lines if line)

                title_match = re.search(r"^\s*##\s*(.*)", step, re.MULTILINE)
                title = title_match.group(1).strip() if title_match else "Unnamed Step"
                
                prompts.append({"title": title, "prompt": cleaned_prompt})
        return prompts
