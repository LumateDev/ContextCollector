"""
Сканирование директорий с фильтрацией и .gitignore.
"""

import os
import re
from typing import List, Set, Optional, Callable
from dataclasses import dataclass
from config import DEFAULT_INCLUDED_FILENAMES, SELF_EXCLUDED_FILES, SELF_OUTPUT_PATTERNS


@dataclass
class ScanResult:
    relative_path: str
    absolute_path: str
    size: int
    error: Optional[str] = None
    content: Optional[str] = None
    skipped_reason: Optional[str] = None


class GitignoreParser:
    def __init__(self):
        self.patterns: List[tuple] = []

    def parse_file(self, gitignore_path: str, base_dir: str):
        try:
            with open(gitignore_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.rstrip('\n\r')
                    if not line.strip() or line.strip().startswith('#'):
                        continue
                    self._add_pattern(line.strip(), base_dir)
        except Exception:
            pass

    def _add_pattern(self, pattern: str, base_dir: str):
        is_negation = pattern.startswith('!')
        if is_negation:
            pattern = pattern[1:]
        is_dir_only = pattern.endswith('/')
        if is_dir_only:
            pattern = pattern.rstrip('/')
        if pattern.startswith('/'):
            pattern = pattern[1:]
            regex = self._glob_to_regex(pattern)
        else:
            regex = r'(?:.*/)?' + self._glob_to_regex(pattern)
        try:
            compiled = re.compile('^' + regex + '$')
            self.patterns.append((compiled, is_negation, is_dir_only))
        except re.error:
            pass

    def _glob_to_regex(self, pattern: str) -> str:
        result = ''
        i = 0
        while i < len(pattern):
            c = pattern[i]
            if c == '*':
                if i + 1 < len(pattern) and pattern[i + 1] == '*':
                    if i + 2 < len(pattern) and pattern[i + 2] == '/':
                        result += '(?:.*/)?'
                        i += 3
                        continue
                    else:
                        result += '.*'
                        i += 2
                        continue
                else:
                    result += '[^/]*'
            elif c == '?':
                result += '[^/]'
            elif c in r'\.^$+{}()|':
                result += '\\' + c
            else:
                result += c
            i += 1
        return result

    def is_ignored(self, relative_path: str, is_dir: bool = False) -> bool:
        path = relative_path.replace('\\', '/')
        ignored = False
        for regex, is_negation, is_dir_only in self.patterns:
            if is_dir_only and not is_dir:
                continue
            if regex.match(path):
                ignored = not is_negation
        return ignored


class ProjectScanner:
    def __init__(
        self,
        root_dir: str,
        extensions: Set[str],
        excluded_dirs: Set[str],
        use_gitignore: bool = True,
        max_file_size_kb: int = 1024,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ):
        self.root_dir = os.path.abspath(root_dir)
        self.extensions = {ext.lower() for ext in extensions}
        self.excluded_dirs = {d.lower() for d in excluded_dirs}
        self.use_gitignore = use_gitignore
        self.max_file_size = max_file_size_kb * 1024
        self.progress_callback = progress_callback
        self.cancel_check = cancel_check
        self.gitignore = GitignoreParser()
        self.warnings: List[str] = []

        if use_gitignore:
            gi = os.path.join(root_dir, '.gitignore')
            if os.path.exists(gi):
                self.gitignore.parse_file(gi, root_dir)

    def _is_self_file(self, filename: str) -> bool:
        name_lower = filename.lower()
        if name_lower in SELF_EXCLUDED_FILES:
            return True
        for pattern in SELF_OUTPUT_PATTERNS:
            if name_lower.endswith(pattern):
                return True
        return False

    def _should_include_file(self, filename: str) -> bool:
        if self._is_self_file(filename):
            return False
        if filename in DEFAULT_INCLUDED_FILENAMES:
            return True
        _, ext = os.path.splitext(filename)
        return ext.lower() in self.extensions

    def _is_binary(self, filepath: str) -> bool:
        try:
            with open(filepath, 'rb') as f:
                chunk = f.read(8192)
            return b'\x00' in chunk
        except Exception:
            return True

    def _read_file(self, filepath: str) -> tuple:
        for enc in ['utf-8', 'utf-8-sig', 'cp1251', 'latin-1']:
            try:
                with open(filepath, 'r', encoding=enc) as f:
                    return f.read(), None
            except UnicodeDecodeError:
                continue
            except Exception as e:
                return None, str(e)
        return None, 'Не удалось определить кодировку'

    def collect_files(self) -> List[str]:
        files = []
        for dirpath, dirnames, filenames in os.walk(self.root_dir):
            dirnames[:] = [
                d for d in dirnames
                if d.lower() not in self.excluded_dirs and not d.startswith('.')
            ]
            if self.use_gitignore:
                rel_dir = os.path.relpath(dirpath, self.root_dir)
                dirnames[:] = [
                    d for d in dirnames
                    if not self.gitignore.is_ignored(
                        (os.path.join(rel_dir, d) if rel_dir != '.' else d),
                        is_dir=True
                    )
                ]
            dirnames.sort()
            filenames.sort()
            for fn in filenames:
                if not self._should_include_file(fn):
                    continue
                rel = os.path.relpath(os.path.join(dirpath, fn), self.root_dir)
                if self.use_gitignore and self.gitignore.is_ignored(rel):
                    continue
                files.append(rel)
        return files

    def scan(self) -> List[ScanResult]:
        file_list = self.collect_files()
        total = len(file_list)
        results = []
        for i, rel_path in enumerate(file_list):
            if self.cancel_check and self.cancel_check():
                self.warnings.append('Отменено пользователем')
                break
            abs_path = os.path.join(self.root_dir, rel_path)
            if self.progress_callback:
                self.progress_callback(rel_path, i + 1, total)
            try:
                size = os.path.getsize(abs_path)
            except OSError as e:
                results.append(ScanResult(rel_path, abs_path, 0,
                               error=str(e), skipped_reason='ошибка доступа'))
                continue
            if size > self.max_file_size:
                self.warnings.append(f'Пропущен (>{self.max_file_size // 1024}KB): {rel_path}')
                results.append(ScanResult(rel_path, abs_path, size,
                               skipped_reason=f'слишком большой ({size // 1024}KB)'))
                continue
            if self._is_binary(abs_path):
                self.warnings.append(f'Пропущен (бинарный): {rel_path}')
                results.append(ScanResult(rel_path, abs_path, size,
                               skipped_reason='бинарный'))
                continue
            content, error = self._read_file(abs_path)
            if error:
                self.warnings.append(f'Ошибка: {rel_path}: {error}')
            results.append(ScanResult(rel_path, abs_path, size,
                           content=content, error=error))
        return results

    def get_tree_structure(self) -> str:
        files = self.collect_files()
        if not files:
            return '(пусто)\n'
        tree = {}
        for f in files:
            parts = f.replace('\\', '/').split('/')
            node = tree
            for p in parts:
                node = node.setdefault(p, {})
        lines = [os.path.basename(self.root_dir) + '/']
        self._render(tree, '', lines)
        return '\n'.join(lines) + '\n'

    def _render(self, node: dict, prefix: str, lines: list):
        entries = sorted(node.keys())
        for i, name in enumerate(entries):
            last = i == len(entries) - 1
            conn = '└── ' if last else '├── '
            child = node[name]
            suffix = '/' if child else ''
            lines.append(f'{prefix}{conn}{name}{suffix}')
            if child:
                ext = '    ' if last else '│   '
                self._render(child, prefix + ext, lines)