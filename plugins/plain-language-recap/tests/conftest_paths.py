"""Locate the hooks inside this plugin, wherever it is checked out."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
HOOKS_DIR = PLUGIN_ROOT / "hooks"
CLAUDE_HOOK = HOOKS_DIR / "claude_stop_hook.py"
CODEX_HOOK = HOOKS_DIR / "codex_stop_hook.py"
CONFIGS_DIR = PLUGIN_ROOT / "configs"
DEFAULT_CONFIG = CONFIGS_DIR / "hebrew.json"
ENGLISH_CONFIG = CONFIGS_DIR / "english.json"
USE_LANGUAGE_SCRIPT = PLUGIN_ROOT / "scripts" / "use-language.sh"


def load_module(name: str, path: Path):
    if str(HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(HOOKS_DIR))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
