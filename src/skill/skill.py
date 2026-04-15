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
        is_symlink = self.skill_file_path.is_symlink()
        is_legacy_command = self.command_file_path.exists()

        if is_skill_installed:
            install_label = "✅ Installed (global, symlinked)" if is_symlink else "✅ Installed (global, copy — run install to upgrade)"
        else:
            install_label = None

        if install_label and is_legacy_command:
            return f"{install_label} ⚠️ legacy command file present — run uninstall+install to clean"
        elif install_label:
            return install_label
        elif is_legacy_command:
            return "🟡 Legacy command-only install — run install to upgrade"
        else:
            return "❌ Not Installed"

    def _source_has_frontmatter(self) -> bool:
        """Returns True if the source file already begins with YAML frontmatter."""
        try:
            return self.file_path.read_text().startswith("---\n")
        except Exception:
            return False

    def _build_frontmatter(self) -> str:
        """Build the YAML frontmatter block (without source body)."""
        desc = self.description.replace("\n", " ").strip()
        desc = desc.replace("---", "—")
        return f"---\nname: {self.skill_dir_name}\ndescription: {desc}\n---\n\n"

    def _ensure_source_has_frontmatter(self):
        """
        Write YAML frontmatter into the source file if not already present.

        Called once at install time so the symlinked SKILL.md carries the
        frontmatter Claude Code needs for global skill discovery.
        """
        if not self._source_has_frontmatter():
            content = self._build_frontmatter() + self.file_path.read_text()
            self.file_path.write_text(content)
            print(f"  Added frontmatter to source: {self.file_path.name}")

    def install(self):
        """
        Installs the skill by symlinking SKILL.md -> source file.

        Creates ~/.claude/skills/<name>/SKILL.md as a symlink to the absolute
        path of the source workflow-skills/*.md file.  Edits to either location
        are immediately reflected — no manual re-install needed after content
        changes.  pskill install only needs to be re-run when adding a brand-new
        skill for the first time.

        On first install the source file is updated with YAML frontmatter (required
        by Claude Code for global skill discovery).  Subsequent installs are
        idempotent: if the symlink already points to the correct source it is left
        unchanged.
        """
        try:
            self.skill_dir_path.mkdir(parents=True, exist_ok=True)

            # Ensure source file carries frontmatter (one-time migration)
            self._ensure_source_has_frontmatter()

            target = self.file_path.resolve()

            # If already a correct symlink, nothing to do
            if self.skill_file_path.is_symlink() and self.skill_file_path.resolve() == target:
                print(f"  Already linked:  {self.skill_file_path.name} -> {self.file_path.name}")
                return True

            # Remove stale copy or wrong symlink
            if self.skill_file_path.exists() or self.skill_file_path.is_symlink():
                self.skill_file_path.unlink()

            self.skill_file_path.symlink_to(target)
            print(f"  Linked skill:    {self.skill_file_path} -> {target}")
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
