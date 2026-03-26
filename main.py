"""
Context Collector — CustomTkinter GUI.
"""

import customtkinter as ctk
import threading
import os
import sys
import logging
from tkinter import filedialog, messagebox
from datetime import datetime
from config import AppConfig, get_config_dir, DEFAULT_EXTENSIONS, DEFAULT_EXCLUDED_DIRS
from scanner import ProjectScanner
from formatter import format_context


# ─── Логирование в файл ───

def get_log_path() -> str:
    return os.path.join(get_config_dir(), 'last_scan.log')


def setup_logger() -> logging.Logger:
    logger = logging.getLogger('context_collector')
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    path = get_log_path()
    handler = logging.FileHandler(path, mode='w', encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s  %(message)s', datefmt='%H:%M:%S'))
    logger.addHandler(handler)
    return logger


def refresh_logger():
    """Обновляет логгер (очищает handlers и создаёт новый файл)."""
    global log
    for handler in log.handlers[:]:
        handler.close()
        log.removeHandler(handler)

    path = get_log_path()
    handler = logging.FileHandler(path, mode='w', encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s  %(message)s', datefmt='%H:%M:%S'))
    log.addHandler(handler)


log = setup_logger()


# ═══════════════════════════════════════════════════════════
#   Главное окно приложения
# ═══════════════════════════════════════════════════════════

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.cfg = AppConfig.load()
        self.cancelled = False
        self.running = False
        self.title('Context Collector')
        self.geometry('400x340')
        self.resizable(False, False)
        appearance = self.cfg.appearance
        ctk.set_appearance_mode(appearance.capitalize())
        self._build_ui()

        # Сохранение при закрытии
        self.protocol('WM_DELETE_WINDOW', self._on_close)

    # ──────────────────────────────────────────────────────
    #   Построение интерфейса
    # ──────────────────────────────────────────────────────

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        PX = 16  # горизонтальный отступ

        # ─── Папка проекта ───
        lbl_path = ctk.CTkLabel(self, text='Папка проекта', anchor='w')
        lbl_path.grid(row=0, column=0, sticky='w', padx=PX, pady=(0, 0))

        frame_path = ctk.CTkFrame(self, fg_color='transparent')
        frame_path.grid(row=1, column=0, sticky='ew', padx=PX, pady=(0, 0))
        frame_path.grid_columnconfigure(0, weight=1)

        initial_path = self.cfg.last_folder if os.path.isdir(self.cfg.last_folder or '') else ''
        self.input_path = ctk.CTkEntry(
            frame_path,
            placeholder_text='Выберите папку с проектом...',
            height=36,
        )
        self.input_path.grid(row=0, column=0, sticky='ew', padx=(0, 8))
        if initial_path:
            self.input_path.insert(0, initial_path)

        self.btn_browse = ctk.CTkButton(
            frame_path, text='Обзор...', width=90, height=36,
            command=self._browse_folder,
        )
        self.btn_browse.grid(row=0, column=1)

        # ─── Разделитель ───
        sep = ctk.CTkFrame(self, height=2, fg_color=('gray75', 'gray35'))
        sep.grid(row=2, column=0, sticky='ew', padx=PX, pady=10)

        # ─── Опции — формат ───
        frame_format = ctk.CTkFrame(self, fg_color='transparent')
        frame_format.grid(row=3, column=0, sticky='w', padx=PX, pady=(0, 0))

        ctk.CTkLabel(frame_format, text='Формат:').pack(side='left')

        self.format_var = ctk.StringVar(
            value='md' if self.cfg.output_format == 'md' else 'txt'
        )
        self.radio_txt = ctk.CTkRadioButton(
            frame_format, text='txt', variable=self.format_var,
            value='txt', width=50, radiobutton_width=18, radiobutton_height=18,
        )
        self.radio_txt.pack(side='left', padx=(8, 2))
        self.radio_md = ctk.CTkRadioButton(
            frame_format, text='md', variable=self.format_var,
            value='md', width=50, radiobutton_width=18, radiobutton_height=18,
        )
        self.radio_md.pack(side='left', padx=(2, 0))

        # ─── Опции — макс. размер (новая строка) ───
        frame_maxsize = ctk.CTkFrame(self, fg_color='transparent')
        frame_maxsize.grid(row=4, column=0, sticky='w', padx=PX, pady=(6, 0))

        ctk.CTkLabel(frame_maxsize, text='Макс. размер (KB):').pack(side='left')

        self.input_max_size = ctk.CTkEntry(
            frame_maxsize, width=80, height=30,
        )
        self.input_max_size.pack(side='left', padx=(8, 0))
        self.input_max_size.insert(0, str(self.cfg.max_file_size_kb))

               # ─── Опции — чекбоксы ───
        frame_checks = ctk.CTkFrame(self, fg_color='transparent')
        frame_checks.grid(row=5, column=0, sticky='w', padx=PX, pady=(0, 0))

        self.chk_gitignore_var = ctk.BooleanVar(value=self.cfg.use_gitignore)
        ctk.CTkCheckBox(
            frame_checks, text='Учитывать .gitignore',
            variable=self.chk_gitignore_var,
        ).grid(row=0, column=0, sticky='w', pady=2)

        self.chk_tree_var = ctk.BooleanVar(value=self.cfg.show_tree)
        ctk.CTkCheckBox(
            frame_checks, text='Дерево файлов',
            variable=self.chk_tree_var,
        ).grid(row=1, column=0, sticky='w', pady=2)

        self.chk_clipboard_var = ctk.BooleanVar(value=self.cfg.copy_to_clipboard)
        ctk.CTkCheckBox(
            frame_checks, text='Копировать в буфер',
            variable=self.chk_clipboard_var,
        ).grid(row=2, column=0, sticky='w', pady=2)

        # ─── Кнопки ───
        frame_btns = ctk.CTkFrame(self, fg_color='transparent')
        frame_btns.grid(row=6, column=0, sticky='w', padx=PX, pady=(14, 0))

        self.btn_filters = ctk.CTkButton(
            frame_btns, text='Фильтры', width=100, height=36,
            fg_color=('gray70', 'gray30'),
            hover_color=('gray60', 'gray40'),
            command=self._open_filters_dialog,
        )
        self.btn_filters.pack(side='left', padx=(0, 10))

        self.btn_start = ctk.CTkButton(
            frame_btns, text='Собрать', width=120, height=36,
            fg_color='#2ecc71', hover_color='#27ae60',
            text_color='white',
            command=self._start_scan,
        )
        self.btn_start.pack(side='left')

        # ─── Прогресс-бар ───
        self.progress_bar = ctk.CTkProgressBar(self, height=10)
        self.progress_bar.grid(row=7, column=0, sticky='ew', padx=PX, pady=(14, 0))
        self.progress_bar.set(0)

        # ─── Статусная строка ───
        self.status_label = ctk.CTkLabel(
            self, text='', anchor='w',
            text_color=('gray40', 'gray60'),
            font=ctk.CTkFont(size=12),
        )
        self.status_label.grid(row=8, column=0, sticky='w', padx=PX, pady=(4, 10))

    # ──────────────────────────────────────────────────────
    #   Колбэки
    # ──────────────────────────────────────────────────────

    def _browse_folder(self):
        initial = self.input_path.get().strip() or os.path.expanduser('~')
        folder = filedialog.askdirectory(
            title='Выберите папку проекта',
            initialdir=initial,
        )
        if folder:
            self.input_path.delete(0, 'end')
            self.input_path.insert(0, folder)

    def _open_filters_dialog(self):
        FilterDialog(self, self.cfg)

    def _save_ui_to_cfg(self):
        self.cfg.last_folder = self.input_path.get().strip()
        self.cfg.output_format = self.format_var.get()
        try:
            self.cfg.max_file_size_kb = int(self.input_max_size.get())
        except (ValueError, TypeError):
            self.cfg.max_file_size_kb = 1024
        self.cfg.use_gitignore = self.chk_gitignore_var.get()
        self.cfg.show_tree = self.chk_tree_var.get()
        self.cfg.copy_to_clipboard = self.chk_clipboard_var.get()
        self.cfg.save()

    def _start_scan(self):
        if self.running:
            self.cancelled = True
            self._set_status('Отмена...')
            log.info('Отмена...')
            return

        path = self.input_path.get().strip()
        if not path:
            messagebox.showwarning('Внимание', 'Укажите папку проекта')
            return
        if not os.path.isdir(path):
            messagebox.showerror('Ошибка', f'Папка не найдена:\n{path}')
            return

        self.cancelled = False
        self.running = True
        self.btn_start.configure(text='Отмена')
        self.progress_bar.set(0)
        self._set_status('Сканирование...')
        self._save_ui_to_cfg()

        refresh_logger()

        thread = threading.Thread(target=self._scan_worker, args=(path,), daemon=True)
        thread.start()

    def _scan_worker(self, path: str):
        try:
            cfg = self.cfg
            extensions = cfg.get_all_extensions()

            log.info(f'Сканирование: {path}')
            log.info(f'Расширений в фильтре: {len(extensions)}')
            log.info(f'Учёт .gitignore: {"да" if cfg.use_gitignore else "нет"}')

            scanner = ProjectScanner(
                root_dir=path,
                extensions=extensions,
                excluded_dirs=set(cfg.excluded_dirs),
                use_gitignore=cfg.use_gitignore,
                max_file_size_kb=cfg.max_file_size_kb,
                progress_callback=self._on_progress,
                cancel_check=lambda: self.cancelled,
            )

            tree = ''
            if cfg.show_tree:
                log.info('Построение дерева...')
                tree = scanner.get_tree_structure()

            log.info('Чтение файлов...')
            results = scanner.scan()

            if self.cancelled:
                log.info('Отменено пользователем')
                self.after(0, self._finish, None)
                return

            for w in scanner.warnings:
                log.warning(w)

            log.info('Форматирование...')
            output = format_context(
                project_path=path, tree=tree, results=results,
                warnings=scanner.warnings,
                show_tree=cfg.show_tree, output_format=cfg.output_format,
            )

            included = sum(1 for r in results if r.content is not None)
            skipped = sum(1 for r in results if r.skipped_reason)
            log.info(f'Готово! Файлов: {included}, пропущено: {skipped}, '
                     f'размер: {len(output) / 1024:.1f} KB')

            self.after(0, self._finish, output)

        except Exception as e:
            log.error(f'Ошибка: {e}', exc_info=True)
            self.after(0, self._finish, None)

    def _on_progress(self, filename: str, current: int, total: int):
        if total > 0:
            value = current / total
            self.after(0, self.progress_bar.set, value)
            self.after(0, self._set_status, f'[{current}/{total}] {filename}')

    def _finish(self, output):
        self.running = False
        self.btn_start.configure(text='Собрать')

        if output is None:
            self.progress_bar.set(0)
            self._set_status('Отменено')
            return

        self.progress_bar.set(1.0)
        self._set_status('Готово!')

        if self.cfg.copy_to_clipboard:
            self._copy_to_clipboard(output)

        self._save_output(output)

    def _save_output(self, output: str):
        fmt = self.cfg.output_format
        ext = '.md' if fmt == 'md' else '.txt'
        if fmt == 'md':
            filetypes = [('Markdown', '*.md'), ('Текст', '*.txt'), ('Все', '*.*')]
        else:
            filetypes = [('Текст', '*.txt'), ('Markdown', '*.md'), ('Все', '*.*')]

        project_name = os.path.basename(self.input_path.get().strip().rstrip('/\\'))
        default_name = f'{project_name}_context{ext}'

        filepath = filedialog.asksaveasfilename(
            parent=self,
            title='Сохранить контекст',
            initialdir=self.input_path.get().strip(),
            initialfile=default_name,
            defaultextension=ext,
            filetypes=filetypes,
        )

        if filepath:
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(output)
                log.info(f'Сохранено: {filepath}')
                self._set_status(f'Сохранено: {filepath}')
                if messagebox.askyesno(
                    'Готово',
                    f'Сохранено:\n{filepath}\n\nОткрыть папку?',
                    parent=self,
                ):
                    self._open_folder(os.path.dirname(filepath))
            except Exception as e:
                messagebox.showerror('Ошибка', f'Не удалось сохранить:\n{e}', parent=self)
        else:
            if not self.cfg.copy_to_clipboard:
                if messagebox.askyesno(
                    'Скопировать?',
                    'Файл не сохранён.\nСкопировать результат в буфер обмена?',
                    parent=self,
                ):
                    self._copy_to_clipboard(output)
                    messagebox.showinfo('Готово', 'Скопировано в буфер обмена!', parent=self)

    def _copy_to_clipboard(self, text: str):
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.update()
            log.info('Скопировано в буфер обмена')
            self._set_status('Скопировано в буфер обмена')
        except Exception as e:
            log.error(f'Буфер обмена: {e}')

    def _set_status(self, text: str):
        self.status_label.configure(text=text)

    @staticmethod
    def _open_folder(path: str):
        try:
            if sys.platform == 'win32':
                os.startfile(path)
            elif sys.platform == 'darwin':
                os.system(f'open "{path}"')
            else:
                os.system(f'xdg-open "{path}"')
        except Exception:
            pass

    def _on_close(self):
        self._save_ui_to_cfg()
        self.destroy()


# ═══════════════════════════════════════════════════════════
#   Диалог настройки фильтров
# ═══════════════════════════════════════════════════════════

class FilterDialog(ctk.CTkToplevel):
    def __init__(self, parent: App, cfg: AppConfig):
        super().__init__(parent)
        self.cfg = cfg
        self.parent_app = parent

        self.title('Настройка фильтров')
        self.geometry('720x700')
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()
        self._build_ui()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(4, weight=1)
        PX = 16
        
        # ─── Расширения ───
        ctk.CTkLabel(
            self,
            text='Включить в контекст — расширения файлов',
            font=ctk.CTkFont(size=14, weight='bold'),
            anchor='w',
        ).grid(row=0, column=0, sticky='w', padx=PX, pady=(14, 4))

        self.ext_textbox = ctk.CTkTextbox(self, height=220)
        self.ext_textbox.grid(row=1, column=0, sticky='nsew', padx=PX, pady=(0, 0))
        self.ext_textbox.insert('1.0', '\n'.join(sorted(self.cfg.extensions)))

        # ─── Исключённые папки ───
        ctk.CTkLabel(
            self,
            text='Исключить из сканирования — папки',
            font=ctk.CTkFont(size=14, weight='bold'),
            anchor='w',
        ).grid(row=3, column=0, sticky='w', padx=PX, pady=(14, 4))

        self.dirs_textbox = ctk.CTkTextbox(self, height=180)
        self.dirs_textbox.grid(row=4, column=0, sticky='nsew', padx=PX, pady=(0, 0))
        self.dirs_textbox.insert('1.0', '\n'.join(sorted(self.cfg.excluded_dirs)))

        # ─── Кнопки ───
        frame_btns = ctk.CTkFrame(self, fg_color='transparent')
        frame_btns.grid(row=5, column=0, sticky='ew', padx=PX, pady=(14, 14))

        ctk.CTkButton(
            frame_btns, text='Сбросить к стандартным', width=200,
            fg_color=('gray70', 'gray30'),
            hover_color=('gray60', 'gray40'),
            command=self._reset_filters,
        ).pack(side='left')

        ctk.CTkButton(
            frame_btns, text='Сохранить', width=120,
            fg_color='#2ecc71', hover_color='#27ae60',
            text_color='white',
            command=self._save_filters,
        ).pack(side='right')

        ctk.CTkButton(
            frame_btns, text='Отмена', width=100,
            fg_color=('gray70', 'gray30'),
            hover_color=('gray60', 'gray40'),
            command=self.destroy,
        ).pack(side='right', padx=(0, 10))

    def _reset_filters(self):
        self.ext_textbox.delete('1.0', 'end')
        self.ext_textbox.insert('1.0', '\n'.join(sorted(DEFAULT_EXTENSIONS)))
        self.dirs_textbox.delete('1.0', 'end')
        self.dirs_textbox.insert('1.0', '\n'.join(sorted(DEFAULT_EXCLUDED_DIRS)))

    def _save_filters(self):
        raw_ext = self.ext_textbox.get('1.0', 'end').strip()
        exts = []
        for line in raw_ext.split('\n'):
            line = line.strip()
            if line:
                if not line.startswith('.'):
                    line = '.' + line
                exts.append(line.lower())
        self.cfg.extensions = sorted(set(exts))

        raw_dirs = self.dirs_textbox.get('1.0', 'end').strip()
        dirs = [line.strip() for line in raw_dirs.split('\n') if line.strip()]
        self.cfg.excluded_dirs = sorted(set(dirs))

        self.cfg.save()
        log.info('Фильтры обновлены')
        self.destroy()

def main():
    app = App()
    app.mainloop()


if __name__ == '__main__':
    main()