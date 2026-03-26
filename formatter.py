"""
Форматирование результата в текст/markdown.
Markdown валидный по markdownlint.
"""

from datetime import datetime
from typing import List
from scanner import ScanResult


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(len(text.split()), len(text) // 4)


def format_context(
    project_path: str,
    tree: str,
    results: List[ScanResult],
    warnings: List[str],
    show_tree: bool = True,
    output_format: str = 'txt',
) -> str:
    parts = []
    sep = '─' * 60
    included = [r for r in results if r.content is not None]
    skipped = [r for r in results if r.skipped_reason]
    total_size = sum(r.size for r in included)
    all_content = '\n'.join(r.content for r in included if r.content)
    tokens = estimate_tokens(all_content)

    if output_format == 'md':
        parts.append('# Контекст проекта')
        parts.append('')
        parts.append(f'- **Путь:** `{project_path}`')
        parts.append(f'- **Дата:** {datetime.now():%Y-%m-%d %H:%M:%S}')
        parts.append(f'- **Файлов:** {len(included)} (пропущено: {len(skipped)})')
        parts.append(f'- **Размер:** {total_size / 1024:.1f} KB')
        parts.append(f'- **Токенов:** ~{tokens:,}')
        parts.append('')
    else:
        parts.append('═' * 60)
        parts.append('  КОНТЕКСТ ПРОЕКТА')
        parts.append('═' * 60)
        parts.append(f'  Путь:      {project_path}')
        parts.append(f'  Дата:      {datetime.now():%Y-%m-%d %H:%M:%S}')
        parts.append(f'  Файлов:    {len(included)} (пропущено: {len(skipped)})')
        parts.append(f'  Размер:    {total_size / 1024:.1f} KB')
        parts.append(f'  Токенов:   ~{tokens:,}')
        parts.append('═' * 60)
        parts.append('')

    if warnings:
        if output_format == 'md':
            parts.append('## Предупреждения')
            parts.append('')
            for w in warnings:
                parts.append(f'- {w}')
            parts.append('')
        else:
            parts += [sep, '  ПРЕДУПРЕЖДЕНИЯ', sep]
            parts += [f'  ⚠ {w}' for w in warnings]
            parts.append('')

    if show_tree and tree:
        if output_format == 'md':
            parts.append('## Структура проекта')
            parts.append('')
            parts.append('```text')
            parts.append(tree.rstrip())
            parts.append('```')
            parts.append('')
        else:
            parts += [sep, '  СТРУКТУРА ПРОЕКТА', sep, tree.rstrip()]
            parts.append('')

    if output_format == 'md':
        parts.append('## Содержимое файлов')
        parts.append('')
    else:
        parts += [sep, '  СОДЕРЖИМОЕ ФАЙЛОВ', sep, '']

    for r in included:
        rel = r.relative_path.replace('\\', '/')
        if output_format == 'md':
            lang = _lang(rel)
            # Если язык не определён — ставим text чтобы не было MD040
            if not lang:
                lang = 'text'
            parts.append(f'### `{rel}`')
            parts.append('')
            parts.append(f'```{lang}')
            parts.append(r.content.rstrip())
            parts.append('```')
            parts.append('')
        else:
            parts += [sep, f'  Файл: {rel}', sep, r.content.rstrip(), '', '']

    if output_format == 'md':
        parts.append('---')
        parts.append('')
        parts.append('Context Collector v1.0')
        parts.append('')  # MD047: trailing newline
    else:
        parts += ['═' * 60,
                  f'  Конец | {len(included)} файлов | ~{tokens:,} токенов',
                  '═' * 60, '']

    return '\n'.join(parts)


def _lang(path: str) -> str:
    m = {
        '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
        '.jsx': 'jsx', '.tsx': 'tsx', '.cs': 'csharp', '.java': 'java',
        '.go': 'go', '.rs': 'rust', '.rb': 'ruby', '.php': 'php',
        '.html': 'html', '.css': 'css', '.scss': 'scss',
        '.json': 'json', '.yaml': 'yaml', '.yml': 'yaml',
        '.xml': 'xml', '.toml': 'toml', '.sql': 'sql',
        '.sh': 'bash', '.bat': 'batch', '.md': 'markdown',
        '.c': 'c', '.h': 'c', '.cpp': 'cpp', '.hpp': 'cpp',
        '.kt': 'kotlin', '.vue': 'vue', '.svelte': 'svelte',
        '.txt': 'text', '.cfg': 'ini', '.ini': 'ini',
        '.conf': 'text', '.env': 'bash', '.rst': 'rst',
        '.ps1': 'powershell', '.dockerfile': 'dockerfile',
        '.gitignore': 'text', '.editorconfig': 'ini',
    }
    # Для файлов вроде Dockerfile, Makefile
    basename = path.rsplit('/', 1)[-1] if '/' in path else path
    basename_map = {
        'Dockerfile': 'dockerfile',
        'Makefile': 'makefile',
        'Gemfile': 'ruby',
        'Rakefile': 'ruby',
    }
    if basename in basename_map:
        return basename_map[basename]

    ext = '.' + path.rsplit('.', 1)[-1] if '.' in path else ''
    return m.get(ext.lower(), 'text')