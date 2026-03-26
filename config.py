"""
Конфигурация — хранит настройки в %APPDATA%/ContextCollector/.
"""

import json
import os
import platform
from dataclasses import dataclass, field, asdict
from typing import Set


def get_config_dir() -> str:
    system = platform.system()
    if system == 'Windows':
        base = os.environ.get('APPDATA', os.path.expanduser('~'))
    elif system == 'Darwin':
        base = os.path.join(os.path.expanduser('~'), 'Library', 'Application Support')
    else:
        base = os.environ.get('XDG_CONFIG_HOME',
                              os.path.join(os.path.expanduser('~'), '.config'))
    config_dir = os.path.join(base, 'ContextCollector')
    os.makedirs(config_dir, exist_ok=True)
    return config_dir


def get_config_path() -> str:
    return os.path.join(get_config_dir(), 'settings.json')


DEFAULT_EXTENSIONS: Set[str] = {
    '.cs', '.csproj', '.sln', '.config', '.xaml', '.razor',
    '.py', '.pyw', '.pyi',
    '.js', '.ts', '.jsx', '.tsx', '.html', '.css', '.scss',
    '.less', '.vue', '.svelte',
    '.json', '.yaml', '.yml', '.xml', '.toml', '.ini',
    '.cfg', '.conf',
    '.md', '.txt', '.rst',
    '.sql', '.sh', '.bat', '.ps1', '.dockerfile',
    '.gitignore', '.editorconfig',
    '.go', '.rs', '.java', '.kt', '.kts', '.gradle',
    '.rb', '.php',
    '.c', '.h', '.cpp', '.hpp', '.cc',
}

DEFAULT_EXCLUDED_DIRS: Set[str] = {
    'node_modules', '.git', '__pycache__', '.idea', '.vscode',
    'bin', 'obj', 'dist', 'build', '.next', '.nuxt',
    'venv', '.venv', 'env', '.env', '.tox',
    'target', '.gradle', '.mvn',
    'vendor', 'packages',
    '.cache', '.parcel-cache',
    'coverage', '.nyc_output',
    'egg-info', '.eggs',
}

DEFAULT_INCLUDED_FILENAMES: Set[str] = {
    'Dockerfile', 'Makefile', 'Procfile', 'Gemfile',
    'Rakefile', 'Vagrantfile',
    '.gitignore', '.dockerignore', '.editorconfig',
}

SELF_EXCLUDED_FILES: Set[str] = {
    'context_collector_settings.json',
    'contextcollector.exe',
    'contextcollector',
}

SELF_OUTPUT_PATTERNS: list = [
    '_context.txt',
    '_context.md',
]


@dataclass
class AppConfig:
    last_folder: str = ''
    use_gitignore: bool = True
    show_tree: bool = True
    max_file_size_kb: int = 1024
    extensions: list = field(default_factory=lambda: sorted(DEFAULT_EXTENSIONS))
    excluded_dirs: list = field(default_factory=lambda: sorted(DEFAULT_EXCLUDED_DIRS))
    output_format: str = 'txt'
    copy_to_clipboard: bool = False
    appearance: str = 'dark'  # dark / light / system

    def get_all_extensions(self) -> Set[str]:
        return set(self.extensions)

    def save(self):
        try:
            with open(get_config_path(), 'w', encoding='utf-8') as f:
                json.dump(asdict(self), f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    @classmethod
    def load(cls) -> 'AppConfig':
        path = get_config_path()
        if not os.path.exists(path):
            return cls()
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return cls(**{k: v for k, v in data.items()
                        if k in cls.__dataclass_fields__})
        except Exception:
            return cls()