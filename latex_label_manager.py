# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import codecs
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
import re
import sys
from typing import Iterable


REF_COMMANDS = {
    "ref",
    "eqref",
    "pageref",
    "autoref",
    "nameref",
    "cref",
    "Cref",
    "vref",
    "Vref",
    "subref",
}

SECTION_COMMANDS = {"chapter", "section", "subsection"}
SECTION_ORDER = ("chapter", "section", "subsection")
SECTION_CATEGORY_NAMES = {
    "chapter": "chapter",
    "section": "section",
    "subsection": "subsection",
}

IGNORED_ENVIRONMENTS = {
    "document",
    "center",
    "flushleft",
    "flushright",
    "minipage",
    "tabular",
    "tabular*",
    "tabularx",
    "array",
    "small",
    "scriptsize",
    "footnotesize",
    "quote",
    "quotation",
    "itemize",
    "enumerate",
    "description",
}

COMMAND_RE = re.compile(r"\\([A-Za-z@]+)(\*)?")
INCLUDE_RE = re.compile(r"\\(?:include|input)\s*\{([^{}]+)\}")


@dataclass
class Heading:
    path: Path
    line: int
    command: str
    title: str


@dataclass
class Chapter:
    path: Path
    title: str

    @property
    def display_name(self) -> str:
        return f"{self.path.stem} - {self.title}" if self.title else self.path.stem


@dataclass
class Occurrence:
    label: str
    path: Path
    line: int
    column: int
    start: int
    end: int
    command: str
    kind: str
    category: str
    chapter_file: Path | None = None


@dataclass
class LabelInfo:
    name: str
    definitions: list[Occurrence] = field(default_factory=list)
    references: list[Occurrence] = field(default_factory=list)

    @property
    def total_count(self) -> int:
        return len(self.definitions) + len(self.references)


@dataclass
class ScanResult:
    root_dir: Path
    tex_files: list[Path]
    chapters: list[Chapter]
    headings: list[Heading]
    labels: dict[str, LabelInfo]
    text_by_file: dict[Path, str]
    encoding_by_file: dict[Path, str]
    line_starts_by_file: dict[Path, list[int]]
    file_order: dict[Path, int]
    warnings: list[str]

    def occurrence_key(self, occurrence: Occurrence) -> tuple[int, int, int, int]:
        return (
            self.file_order.get(occurrence.path, 10**9),
            occurrence.line,
            occurrence.column,
            occurrence.start,
        )

    def sorted_occurrences(self, occurrences: Iterable[Occurrence]) -> list[Occurrence]:
        return sorted(occurrences, key=self.occurrence_key)


def read_tex_text(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    if raw.startswith(codecs.BOM_UTF8):
        return raw.decode("utf-8-sig"), "utf-8-sig"

    for encoding in ("utf-8", "cp932"):
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue

    return raw.decode("utf-8", errors="replace"), "utf-8"


def line_start_offsets(text: str) -> tuple[list[str], list[int]]:
    lines = text.splitlines(keepends=True)
    starts: list[int] = []
    offset = 0
    for line in lines:
        starts.append(offset)
        offset += len(line)
    return lines, starts


def uncommented_end(line: str) -> int:
    for index, char in enumerate(line):
        if char != "%":
            continue

        slash_count = 0
        cursor = index - 1
        while cursor >= 0 and line[cursor] == "\\":
            slash_count += 1
            cursor -= 1

        if slash_count % 2 == 0:
            return index
    return len(line)


def skip_spaces(text: str, index: int) -> int:
    while index < len(text) and text[index].isspace():
        index += 1
    return index


def parse_balanced(
    text: str, open_index: int, opener: str = "{", closer: str = "}"
) -> tuple[str, int, int, int] | None:
    if open_index >= len(text) or text[open_index] != opener:
        return None

    depth = 0
    content_start = open_index + 1
    index = open_index
    while index < len(text):
        char = text[index]
        if char == "\\":
            index += 2
            continue
        if char == opener:
            if depth == 0:
                content_start = index + 1
            depth += 1
        elif char == closer:
            depth -= 1
            if depth == 0:
                return text[content_start:index], content_start, index, index + 1
        index += 1
    return None


def skip_options(text: str, index: int) -> int:
    index = skip_spaces(text, index)
    while index < len(text) and text[index] == "[":
        parsed = parse_balanced(text, index, "[", "]")
        if parsed is None:
            break
        index = skip_spaces(text, parsed[3])
    return index


def compact_latex_text(text: str) -> str:
    text = re.sub(r"\\label\s*\{[^{}]*\}", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def split_label_list(content: str) -> Iterable[tuple[str, int, int]]:
    position = 0
    for part in content.split(","):
        raw_start = position
        raw_end = position + len(part)
        position = raw_end + 1

        start = raw_start
        end = raw_end
        while start < end and content[start].isspace():
            start += 1
        while end > start and content[end - 1].isspace():
            end -= 1

        if start < end:
            yield content[start:end], start, end


class LatexProjectScanner:
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir.resolve()
        self.warnings: list[str] = []

    def scan(self) -> ScanResult:
        self.warnings = []
        tex_files = self._discover_tex_files()
        text_by_file: dict[Path, str] = {}
        encoding_by_file: dict[Path, str] = {}
        line_starts_by_file: dict[Path, list[int]] = {}
        all_headings: list[Heading] = []
        all_occurrences: list[Occurrence] = []

        for path in tex_files:
            text, encoding = read_tex_text(path)
            lines, starts = line_start_offsets(text)
            text_by_file[path] = text
            encoding_by_file[path] = encoding
            line_starts_by_file[path] = starts
            headings, occurrences = self._scan_file(path, lines, starts)
            all_headings.extend(headings)
            all_occurrences.extend(occurrences)

        file_order = {path: index for index, path in enumerate(tex_files)}
        chapters = self._collect_chapters(tex_files, all_headings, file_order)
        chapter_paths = {chapter.path for chapter in chapters}

        labels: dict[str, LabelInfo] = {}
        for occurrence in all_occurrences:
            if occurrence.path in chapter_paths:
                occurrence.chapter_file = occurrence.path
            info = labels.setdefault(occurrence.label, LabelInfo(occurrence.label))
            if occurrence.kind == "definition":
                info.definitions.append(occurrence)
            else:
                info.references.append(occurrence)

        result = ScanResult(
            root_dir=self.root_dir,
            tex_files=tex_files,
            chapters=chapters,
            headings=all_headings,
            labels=labels,
            text_by_file=text_by_file,
            encoding_by_file=encoding_by_file,
            line_starts_by_file=line_starts_by_file,
            file_order=file_order,
            warnings=self.warnings,
        )

        for info in result.labels.values():
            info.definitions[:] = result.sorted_occurrences(info.definitions)
            info.references[:] = result.sorted_occurrences(info.references)

        return result

    def _discover_tex_files(self) -> list[Path]:
        root_tex = self.root_dir / "root.tex"
        if not root_tex.exists():
            return sorted(self.root_dir.glob("*.tex"), key=lambda path: path.name.lower())

        ordered: list[Path] = []
        seen: set[Path] = set()

        def add_file(path: Path) -> None:
            path = path.resolve()
            if path in seen or not path.exists():
                return
            seen.add(path)
            ordered.append(path)

            try:
                text, _ = read_tex_text(path)
            except OSError as exc:
                self.warnings.append(f"无法读取 {path}: {exc}")
                return

            for include_path in self._find_includes(path, text):
                add_file(include_path)

        add_file(root_tex)
        return ordered

    def _find_includes(self, current_file: Path, text: str) -> Iterable[Path]:
        lines, _ = line_start_offsets(text)
        for line in lines:
            code = line[: uncommented_end(line)]
            for match in INCLUDE_RE.finditer(code):
                include_name = match.group(1).strip()
                if not include_name:
                    continue
                include_path = Path(include_name)
                if include_path.suffix.lower() != ".tex":
                    include_path = include_path.with_suffix(".tex")
                if not include_path.is_absolute():
                    include_path = current_file.parent / include_path
                if include_path.exists():
                    yield include_path.resolve()
                else:
                    self.warnings.append(
                        f"找不到被 include/input 的文件: {include_path}"
                    )

    def _scan_file(
        self, path: Path, lines: list[str], starts: list[int]
    ) -> tuple[list[Heading], list[Occurrence]]:
        headings: list[Heading] = []
        occurrences: list[Occurrence] = []
        environment_stack: list[str] = []
        current_sections: dict[str, tuple[str, int] | None] = {
            "chapter": None,
            "section": None,
            "subsection": None,
        }

        for line_index, line in enumerate(lines):
            line_number = line_index + 1
            line_start = starts[line_index]
            code = line[: uncommented_end(line)]

            for match in COMMAND_RE.finditer(code):
                command = match.group(1)
                if command not in SECTION_COMMANDS | {"begin", "end", "label"} | REF_COMMANDS:
                    continue

                arg_index = match.end()
                if command in SECTION_COMMANDS:
                    arg_index = skip_options(code, arg_index)
                else:
                    arg_index = skip_spaces(code, arg_index)

                parsed = parse_balanced(code, arg_index)
                if parsed is None:
                    continue

                content, content_start, content_end, _ = parsed

                if command == "begin":
                    environment_stack.append(content.strip())
                    continue

                if command == "end":
                    self._pop_environment(environment_stack, content.strip())
                    continue

                if command in SECTION_COMMANDS:
                    title = compact_latex_text(content)
                    self._set_section(current_sections, command, title, line_number)
                    headings.append(Heading(path, line_number, command, title))
                    continue

                if command == "label":
                    trim_start = 0
                    trim_end = len(content)
                    while trim_start < trim_end and content[trim_start].isspace():
                        trim_start += 1
                    while trim_end > trim_start and content[trim_end - 1].isspace():
                        trim_end -= 1

                    label = content[trim_start:trim_end]
                    if not label:
                        continue
                    column0 = content_start + trim_start
                    occurrences.append(
                        Occurrence(
                            label=label,
                            path=path,
                            line=line_number,
                            column=column0 + 1,
                            start=line_start + column0,
                            end=line_start + content_start + trim_end,
                            command=command,
                            kind="definition",
                            category=self._current_category(
                                environment_stack, current_sections
                            ),
                        )
                    )
                    continue

                if command in REF_COMMANDS:
                    for label, token_start, token_end in split_label_list(content):
                        column0 = content_start + token_start
                        occurrences.append(
                            Occurrence(
                                label=label,
                                path=path,
                                line=line_number,
                                column=column0 + 1,
                                start=line_start + column0,
                                end=line_start + content_start + token_end,
                                command=command,
                                kind="reference",
                                category="引用",
                            )
                        )

        return headings, occurrences

    def _collect_chapters(
        self, tex_files: list[Path], headings: list[Heading], file_order: dict[Path, int]
    ) -> list[Chapter]:
        chapters_by_file: dict[Path, Chapter] = {}
        for heading in sorted(
            (heading for heading in headings if heading.command == "chapter"),
            key=lambda item: (file_order.get(item.path, 10**9), item.line),
        ):
            chapters_by_file.setdefault(heading.path, Chapter(heading.path, heading.title))

        for path in tex_files:
            if path.name.lower().startswith("chapter") and path not in chapters_by_file:
                chapters_by_file[path] = Chapter(path, path.stem)

        return sorted(
            chapters_by_file.values(),
            key=lambda chapter: file_order.get(chapter.path, 10**9),
        )

    @staticmethod
    def _pop_environment(stack: list[str], environment: str) -> None:
        for index in range(len(stack) - 1, -1, -1):
            if stack[index] == environment:
                del stack[index:]
                return

    @staticmethod
    def _set_section(
        sections: dict[str, tuple[str, int] | None],
        command: str,
        title: str,
        line: int,
    ) -> None:
        sections[command] = (title, line)
        if command == "chapter":
            sections["section"] = None
            sections["subsection"] = None
        elif command == "section":
            sections["subsection"] = None

    @staticmethod
    def _current_category(
        environment_stack: list[str],
        sections: dict[str, tuple[str, int] | None],
    ) -> str:
        for environment in reversed(environment_stack):
            if environment not in IGNORED_ENVIRONMENTS:
                return f"环境: {environment}"

        for command in reversed(SECTION_ORDER):
            value = sections.get(command)
            if value is not None:
                title, _ = value
                return f"{SECTION_CATEGORY_NAMES[command]}: {title}"

        return "未分类"


def label_sort_key(result: ScanResult, info: LabelInfo) -> tuple[int, int, int, str]:
    occurrences = info.definitions or info.references
    first = result.sorted_occurrences(occurrences)[0]
    return (*result.occurrence_key(first)[:3], info.name)


def print_scan_summary(result: ScanResult) -> None:
    total_definitions = sum(len(info.definitions) for info in result.labels.values())
    total_references = sum(len(info.references) for info in result.labels.values())
    duplicate_labels = [
        info for info in result.labels.values() if len(info.definitions) > 1
    ]
    undefined_labels = [info for info in result.labels.values() if not info.definitions]

    print(f"Scanned tex files: {len(result.tex_files)}")
    print(f"Labels: {len(result.labels)}")
    print(f"Definitions: {total_definitions}")
    print(f"References: {total_references}")
    print()

    print("Chapter label counts:")
    for chapter in result.chapters:
        count = sum(
            1
            for info in result.labels.values()
            if any(occ.chapter_file == chapter.path for occ in info.definitions)
        )
        print(f"  {chapter.display_name}: {count}")

    if duplicate_labels:
        print()
        print("Duplicate definitions:")
        for info in sorted(duplicate_labels, key=lambda item: item.name):
            locations = ", ".join(
                f"{occ.path.name}:{occ.line}" for occ in info.definitions
            )
            print(f"  {info.name}: {locations}")

    if undefined_labels:
        print()
        print("Undefined references:")
        for info in sorted(undefined_labels, key=lambda item: item.name):
            print(f"  {info.name}: {len(info.references)} reference(s)")

    if result.warnings:
        print()
        print("Warnings:")
        for warning in result.warnings:
            print(f"  {warning}")


def run_gui(root_dir: Path) -> int:
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QColor, QFont, QTextCursor, QTextFormat
        from PySide6.QtWidgets import (
            QApplication,
            QAbstractItemView,
            QComboBox,
            QDialog,
            QDialogButtonBox,
            QGridLayout,
            QGroupBox,
            QHBoxLayout,
            QHeaderView,
            QLabel,
            QLineEdit,
            QMainWindow,
            QMessageBox,
            QPlainTextEdit,
            QPushButton,
            QSplitter,
            QTableWidget,
            QTableWidgetItem,
            QVBoxLayout,
            QWidget,
            QTextEdit,
        )
    except ImportError:
        print(
            "PySide6 is not installed. Install it with: python -m pip install PySide6",
            file=sys.stderr,
        )
        return 1

    class LabelManagerWindow(QMainWindow):
        def __init__(self, project_root: Path):
            super().__init__()
            self.project_root = project_root.resolve()
            self.scanner = LatexProjectScanner(self.project_root)
            self.scan_result: ScanResult | None = None
            self.current_label: str | None = None
            self.current_cycle_index = -1
            self._preview_path: Path | None = None
            self.chapter_prefix_by_chapter: dict[str, str] = {}

            self.setWindowTitle("LaTeX 标签管理器")
            self.resize(1320, 820)
            self._build_ui()
            self.reload_project()

        def _build_ui(self) -> None:
            central = QWidget(self)
            root_layout = QVBoxLayout(central)

            top_bar = QHBoxLayout()
            top_bar.addWidget(QLabel("章节"))
            self.chapter_combo = QComboBox()
            self.chapter_combo.currentIndexChanged.connect(self.handle_chapter_changed)
            top_bar.addWidget(self.chapter_combo, 2)

            top_bar.addWidget(QLabel("章节前缀"))
            self.chapter_prefix_edit = QLineEdit()
            self.chapter_prefix_edit.setPlaceholderText("例如 ch3_")
            self.chapter_prefix_edit.textChanged.connect(
                self.handle_chapter_prefix_changed
            )
            top_bar.addWidget(self.chapter_prefix_edit, 1)

            self.apply_prefix_button = QPushButton("统一添加章节前缀")
            self.apply_prefix_button.clicked.connect(self.apply_chapter_prefix)
            top_bar.addWidget(self.apply_prefix_button)

            top_bar.addWidget(QLabel("过滤"))
            self.filter_edit = QLineEdit()
            self.filter_edit.setPlaceholderText("输入标签片段")
            self.filter_edit.textChanged.connect(self.refresh_table)
            top_bar.addWidget(self.filter_edit, 2)

            self.reload_button = QPushButton("重新扫描")
            self.reload_button.clicked.connect(self.reload_project)
            top_bar.addWidget(self.reload_button)

            self.scan_undefined_button = QPushButton("扫描未定义标签")
            self.scan_undefined_button.clicked.connect(self.show_undefined_labels)
            top_bar.addWidget(self.scan_undefined_button)
            root_layout.addLayout(top_bar)

            splitter = QSplitter(Qt.Orientation.Horizontal)
            left_panel = QWidget()
            left_layout = QVBoxLayout(left_panel)

            self.summary_label = QLabel()
            left_layout.addWidget(self.summary_label)

            self.table = QTableWidget(0, 5)
            self.table.setHorizontalHeaderLabels(
                ["前缀", "标签名称", "引用次数", "章外引用数", "出现次数"]
            )
            self.table.horizontalHeader().setSectionResizeMode(
                0, QHeaderView.ResizeMode.ResizeToContents
            )
            self.table.horizontalHeader().setSectionResizeMode(
                1, QHeaderView.ResizeMode.Stretch
            )
            self.table.horizontalHeader().setSectionResizeMode(
                2, QHeaderView.ResizeMode.ResizeToContents
            )
            self.table.horizontalHeader().setSectionResizeMode(
                3, QHeaderView.ResizeMode.ResizeToContents
            )
            self.table.horizontalHeader().setSectionResizeMode(
                4, QHeaderView.ResizeMode.ResizeToContents
            )
            self.table.verticalHeader().setVisible(False)
            self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
            self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            self.table.cellClicked.connect(self.handle_table_click)
            left_layout.addWidget(self.table, 1)

            rename_group = QGroupBox("重命名选中标签")
            rename_layout = QGridLayout(rename_group)
            rename_layout.addWidget(QLabel("当前"), 0, 0)
            self.old_label_edit = QLineEdit()
            self.old_label_edit.setReadOnly(True)
            rename_layout.addWidget(self.old_label_edit, 0, 1)
            rename_layout.addWidget(QLabel("新标签"), 1, 0)
            self.new_label_edit = QLineEdit()
            rename_layout.addWidget(self.new_label_edit, 1, 1)
            self.rename_button = QPushButton("同步修改定义和引用")
            self.rename_button.clicked.connect(self.rename_selected_label)
            rename_layout.addWidget(self.rename_button, 2, 0, 1, 2)
            left_layout.addWidget(rename_group)

            right_panel = QWidget()
            right_layout = QVBoxLayout(right_panel)
            self.location_label = QLabel("选择左侧标签后，这里会显示定义或引用位置")
            self.location_label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            right_layout.addWidget(self.location_label)

            self.preview = QPlainTextEdit()
            self.preview.setReadOnly(True)
            self.preview.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
            self.preview.setFont(QFont("Consolas", 10))
            right_layout.addWidget(self.preview, 1)

            splitter.addWidget(left_panel)
            splitter.addWidget(right_panel)
            splitter.setStretchFactor(0, 2)
            splitter.setStretchFactor(1, 3)
            root_layout.addWidget(splitter, 1)

            self.setCentralWidget(central)
            self.statusBar().showMessage(str(self.project_root))

        def reload_project(self, select_label: str | None = None) -> None:
            previous_chapter = self.chapter_combo.currentData()
            try:
                self.scan_result = self.scanner.scan()
            except Exception as exc:
                QMessageBox.critical(self, "扫描失败", str(exc))
                return

            self.chapter_combo.blockSignals(True)
            self.chapter_combo.clear()
            self.chapter_combo.addItem("全部章节", "__all__")
            for chapter in self.scan_result.chapters:
                self.chapter_combo.addItem(chapter.display_name, str(chapter.path))
            if any(not info.definitions for info in self.scan_result.labels.values()):
                self.chapter_combo.addItem("未定义引用", "__undefined__")

            index_to_restore = self.chapter_combo.findData(previous_chapter)
            if index_to_restore >= 0:
                self.chapter_combo.setCurrentIndex(index_to_restore)
            self.chapter_combo.blockSignals(False)

            self._restore_chapter_prefix()
            self._update_prefix_controls()
            self._update_summary()
            self.refresh_table()
            if select_label:
                self.select_label_row(select_label)
            else:
                self._reload_preview_source()

        def handle_chapter_changed(self) -> None:
            self._restore_chapter_prefix()
            self._update_prefix_controls()
            self.refresh_table()

        def _reload_preview_source(self) -> None:
            if self.scan_result is None:
                return

            if self.current_label:
                occurrences = self._cycle_occurrences(self.current_label)
                if occurrences:
                    index = min(max(self.current_cycle_index, 0), len(occurrences) - 1)
                    self._preview_path = None
                    self.show_occurrence(occurrences[index], index, len(occurrences))
                    return

                self.current_label = None
                self.current_cycle_index = -1

            if self._preview_path is None:
                return

            text = self.scan_result.text_by_file.get(self._preview_path)
            if text is None:
                self.preview.clear()
                self.preview.setExtraSelections([])
                self.location_label.setText("当前预览文件已不在扫描结果中")
                self._preview_path = None
                return

            preview_path = self._preview_path
            self._preview_path = None
            self.preview.setPlainText(text)
            self._preview_path = preview_path
            self.preview.setExtraSelections([])

        def handle_chapter_prefix_changed(self, text: str) -> None:
            chapter_key = self._current_chapter_key()
            if self._is_specific_chapter_key(chapter_key):
                self.chapter_prefix_by_chapter[chapter_key] = text
            self.refresh_table()

        def _restore_chapter_prefix(self) -> None:
            chapter_key = self._current_chapter_key()
            prefix = ""
            if self._is_specific_chapter_key(chapter_key):
                prefix = self.chapter_prefix_by_chapter.get(chapter_key, "")

            self.chapter_prefix_edit.blockSignals(True)
            try:
                self.chapter_prefix_edit.setText(prefix)
            finally:
                self.chapter_prefix_edit.blockSignals(False)

        def _update_prefix_controls(self) -> None:
            chapter_key = self._current_chapter_key()
            enabled = self._is_specific_chapter_key(chapter_key)
            self.chapter_prefix_edit.setEnabled(enabled)
            self.apply_prefix_button.setEnabled(enabled)
            if enabled:
                self.chapter_prefix_edit.setToolTip(
                    "只检查当前章节标签中 sec:/fig:/tab: 等类型前缀后面的文字。"
                )
                self.apply_prefix_button.setToolTip(
                    "只对当前章节中定义的标签主体添加此前缀，保留 sec:/fig:/tab: 等类型前缀。"
                )
            else:
                self.chapter_prefix_edit.setToolTip(
                    "请选择一个具体章节后再使用章节前缀。"
                )
                self.apply_prefix_button.setToolTip(
                    "请选择一个具体章节后再批量添加章节前缀。"
                )

        def _update_summary(self) -> None:
            if self.scan_result is None:
                return
            definitions = sum(
                len(info.definitions) for info in self.scan_result.labels.values()
            )
            references = sum(
                len(info.references) for info in self.scan_result.labels.values()
            )
            duplicates = sum(
                1 for info in self.scan_result.labels.values() if len(info.definitions) > 1
            )
            undefined = sum(
                1 for info in self.scan_result.labels.values() if not info.definitions
            )
            self.summary_label.setText(
                f"标签 {len(self.scan_result.labels)} 个，定义 {definitions} 处，"
                f"引用 {references} 处；重复定义 {duplicates} 个，未定义引用 {undefined} 个"
            )

        def refresh_table(self) -> None:
            if self.scan_result is None:
                return

            chapter_key = self.chapter_combo.currentData() or "__all__"
            filter_text = self.filter_edit.text().strip().lower()
            grouped: dict[str, list[LabelInfo]] = defaultdict(list)
            category_order: list[str] = []

            label_infos = sorted(
                self.scan_result.labels.values(),
                key=lambda info: label_sort_key(self.scan_result, info),
            )
            for info in label_infos:
                if not self._is_visible_in_chapter(info, chapter_key):
                    continue
                if filter_text and filter_text not in info.name.lower():
                    continue

                category = self._category_for_label(info, chapter_key)
                if category not in grouped:
                    category_order.append(category)
                grouped[category].append(info)

            self.table.setRowCount(0)
            self.table.setSortingEnabled(False)
            for category in category_order:
                self._add_category_row(category, len(grouped[category]))
                for info in grouped[category]:
                    self._add_label_row(info)

            self.table.resizeRowsToContents()

        def _is_visible_in_chapter(self, info: LabelInfo, chapter_key: str) -> bool:
            if chapter_key == "__all__":
                return True
            if chapter_key == "__undefined__":
                return not info.definitions
            return any(str(occ.chapter_file) == chapter_key for occ in info.definitions)

        def _outside_chapter_reference_count(
            self, info: LabelInfo, chapter_key: str
        ) -> int:
            scope_chapter = self._reference_scope_chapter(info, chapter_key)
            if scope_chapter is None:
                return 0
            return sum(
                1
                for occurrence in info.references
                if str(occurrence.chapter_file) != scope_chapter
            )

        def _reference_scope_chapter(
            self, info: LabelInfo, chapter_key: str
        ) -> str | None:
            if self._is_specific_chapter_key(chapter_key):
                return chapter_key
            if not info.definitions:
                return None
            first_definition = self.scan_result.sorted_occurrences(info.definitions)[0]
            if first_definition.chapter_file is None:
                return None
            return str(first_definition.chapter_file)

        def _category_for_label(self, info: LabelInfo, chapter_key: str) -> str:
            if not info.definitions:
                return "未定义引用"

            definitions = info.definitions
            if chapter_key not in {"__all__", "__undefined__"}:
                definitions = [
                    occ for occ in definitions if str(occ.chapter_file) == chapter_key
                ] or info.definitions

            first = self.scan_result.sorted_occurrences(definitions)[0]
            return first.category

        def _current_chapter_key(self) -> str:
            return self.chapter_combo.currentData() or "__all__"

        @staticmethod
        def _is_specific_chapter_key(chapter_key: str) -> bool:
            return chapter_key not in {"__all__", "__undefined__"}

        def _current_chapter_prefix(self) -> str:
            return self.chapter_prefix_edit.text().strip()

        def _chapter_prefix_state(self, info: LabelInfo):
            chapter_key = self._current_chapter_key()
            prefix = self._current_chapter_prefix()
            if not prefix or not self._is_specific_chapter_key(chapter_key):
                return None
            if not self._is_visible_in_chapter(info, chapter_key):
                return None
            if self._is_chapter_prefix_exempt(info):
                return Qt.CheckState.Checked
            _, label_body = self._split_label_type_prefix(info.name)
            if label_body.startswith(prefix):
                return Qt.CheckState.Checked
            return Qt.CheckState.Unchecked

        @staticmethod
        def _is_chapter_prefix_exempt(info: LabelInfo) -> bool:
            return info.name.startswith("ch:")

        @staticmethod
        def _split_label_type_prefix(label: str) -> tuple[str, str]:
            if ":" not in label:
                return "", label
            label_type, label_body = label.split(":", 1)
            return f"{label_type}:", label_body

        def apply_chapter_prefix(self) -> None:
            if self.scan_result is None:
                return

            chapter_key = self._current_chapter_key()
            if not self._is_specific_chapter_key(chapter_key):
                QMessageBox.warning(
                    self,
                    "无法批量修改",
                    "请先在章节下拉列表中选择一个具体章节。",
                )
                return

            prefix = self._current_chapter_prefix()
            prefix_error = self._validate_prefix(prefix)
            if prefix_error:
                QMessageBox.warning(self, "章节前缀无效", prefix_error)
                return

            rename_map = self._collect_chapter_prefix_renames(chapter_key, prefix)
            if not rename_map:
                self.statusBar().showMessage("当前章节没有需要添加该前缀的标签。", 6000)
                return

            conflict = self._rename_map_conflict(rename_map, chapter_key=chapter_key)
            if conflict:
                QMessageBox.warning(self, "重命名冲突", conflict)
                return

            chapter_name = self.chapter_combo.currentText()
            replacements = self._collect_rename_replacements(rename_map)
            if not self._confirm_rename_changes(
                "确认统一添加章节前缀",
                f"章节: {chapter_name}\n"
                f"前缀: {prefix}\n"
                f"定义范围: 只处理当前选中章节中的标签。\n"
                f"插入位置: 保留 sec:/fig:/tab: 等类型前缀，只修改冒号后的主体文字。\n"
                f"同步范围: 修改这些标签在全文中的定义和引用。\n"
                f"将修改 {len(rename_map)} 个标签、{len(replacements)} 个位置。\n"
                "ch: 类型标签不会被修改。",
                replacements,
                accept_text="执行批量修改",
            ):
                return

            try:
                changed_files = self._apply_renames(rename_map)
            except Exception as exc:
                QMessageBox.critical(self, "批量重命名失败", str(exc))
                return

            self.current_label = None
            self.current_cycle_index = -1
            self._preview_path = None
            first_new_label = next(iter(rename_map.values()))
            self.reload_project(select_label=first_new_label)
            self.statusBar().showMessage(
                f"已添加章节前缀，修改 {len(rename_map)} 个标签、"
                f"{len(changed_files)} 个文件。",
                10000,
            )

        def _collect_chapter_prefix_renames(
            self, chapter_key: str, prefix: str
        ) -> dict[str, str]:
            if self.scan_result is None:
                return {}

            rename_map: dict[str, str] = {}
            for info in sorted(
                self.scan_result.labels.values(),
                key=lambda item: label_sort_key(self.scan_result, item),
            ):
                if not self._is_visible_in_chapter(info, chapter_key):
                    continue
                if not info.definitions:
                    continue
                if self._is_chapter_prefix_exempt(info):
                    continue
                label_type_prefix, label_body = self._split_label_type_prefix(info.name)
                if label_body.startswith(prefix):
                    continue
                rename_map[info.name] = f"{label_type_prefix}{prefix}{label_body}"
            return rename_map

        @staticmethod
        def _validate_prefix(prefix: str) -> str | None:
            if not prefix:
                return "章节前缀不能为空。"
            if any(char.isspace() for char in prefix):
                return "章节前缀不能包含空白字符。"
            invalid_chars = set("{}[],%\\")
            found = sorted({char for char in prefix if char in invalid_chars})
            if found:
                return "章节前缀不能包含这些字符: " + " ".join(found)
            reserved_label_types = {
                "alg",
                "algo",
                "algoline",
                "chap",
                "chapter",
                "chp",
                "eq",
                "equ",
                "fig",
                "par",
                "sec",
                "subsec",
                "tab",
                "table",
            }
            prefix_head = prefix.split(":", 1)[0]
            if ":" in prefix and prefix_head in reserved_label_types:
                return (
                    "章节前缀不要包含 sec:/fig:/tab: 等标签类型前缀；"
                    "这里只填写要放在冒号后面的章节文字。"
                )
            return None

        def _rename_map_conflict(
            self, rename_map: dict[str, str], chapter_key: str | None = None
        ) -> str | None:
            if self.scan_result is None:
                return "项目尚未扫描。"

            reverse: dict[str, str] = {}
            for old_label, new_label in rename_map.items():
                old_info = self.scan_result.labels.get(old_label)
                if old_info is None:
                    return f"标签不存在: {old_label}"

                validation_error = self._validate_new_label(new_label)
                if validation_error:
                    return f"{old_label} -> {new_label}: {validation_error}"

                other_old = reverse.get(new_label)
                if other_old is not None:
                    return (
                        f"{other_old} 和 {old_label} 都会变成 {new_label}，"
                        "请换一个章节前缀。"
                    )
                reverse[new_label] = old_label

                existing = self.scan_result.labels.get(new_label)
                if old_info.definitions and existing and existing.definitions:
                    return (
                        f"{old_label} 会变成 {new_label}，但该标签已经有定义。"
                    )

                if chapter_key is not None:
                    outside_definitions = [
                        occurrence
                        for occurrence in old_info.definitions
                        if str(occurrence.chapter_file) != chapter_key
                    ]
                    if outside_definitions:
                        locations = ", ".join(
                            f"{occ.path.name}:{occ.line}"
                            for occ in outside_definitions[:3]
                        )
                        if len(outside_definitions) > 3:
                            locations += f" 等 {len(outside_definitions)} 处"
                        return (
                            f"{old_label} 也在当前章节以外定义于 {locations}。"
                            "章节前缀批量修改只处理当前章节独占的标签，"
                            "请先手动处理重复定义。"
                        )

            return None

        def _collect_rename_replacements(
            self, rename_map: dict[str, str]
        ) -> list[tuple[Occurrence, str, str]]:
            if self.scan_result is None:
                return []

            replacements: list[tuple[Occurrence, str, str]] = []
            for old_label, new_label in rename_map.items():
                info = self.scan_result.labels.get(old_label)
                if info is None:
                    continue
                for occurrence in info.definitions + info.references:
                    replacements.append((occurrence, old_label, new_label))

            return sorted(
                replacements,
                key=lambda item: self.scan_result.occurrence_key(item[0]),
            )

        def _confirm_rename_changes(
            self,
            title: str,
            summary: str,
            replacements: list[tuple[Occurrence, str, str]],
            accept_text: str,
        ) -> bool:
            dialog = QDialog(self)
            dialog.setWindowTitle(title)
            dialog.resize(1100, 650)

            layout = QVBoxLayout(dialog)
            summary_label = QLabel(summary)
            summary_label.setWordWrap(True)
            summary_label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            layout.addWidget(summary_label)

            table = QTableWidget(len(replacements), 8, dialog)
            table.setHorizontalHeaderLabels(
                ["旧标签", "新标签", "类型", "命令", "文件", "行", "列", "分类"]
            )
            table.verticalHeader().setVisible(False)
            table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            table.horizontalHeader().setSectionResizeMode(
                0, QHeaderView.ResizeMode.ResizeToContents
            )
            table.horizontalHeader().setSectionResizeMode(
                1, QHeaderView.ResizeMode.ResizeToContents
            )
            table.horizontalHeader().setSectionResizeMode(
                2, QHeaderView.ResizeMode.ResizeToContents
            )
            table.horizontalHeader().setSectionResizeMode(
                3, QHeaderView.ResizeMode.ResizeToContents
            )
            table.horizontalHeader().setSectionResizeMode(
                4, QHeaderView.ResizeMode.Stretch
            )
            table.horizontalHeader().setSectionResizeMode(
                5, QHeaderView.ResizeMode.ResizeToContents
            )
            table.horizontalHeader().setSectionResizeMode(
                6, QHeaderView.ResizeMode.ResizeToContents
            )
            table.horizontalHeader().setSectionResizeMode(
                7, QHeaderView.ResizeMode.ResizeToContents
            )

            for row, (occurrence, old_label, new_label) in enumerate(replacements):
                kind = "定义" if occurrence.kind == "definition" else "引用"
                values = [
                    old_label,
                    new_label,
                    kind,
                    occurrence.command,
                    self._relative_path_text(occurrence.path),
                    str(occurrence.line),
                    str(occurrence.column),
                    occurrence.category,
                ]
                for column, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    if occurrence.kind == "definition":
                        item.setForeground(QColor("#1864ab"))
                    table.setItem(row, column, item)

            layout.addWidget(table, 1)

            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok
                | QDialogButtonBox.StandardButton.Cancel,
                dialog,
            )
            ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
            cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
            if ok_button is not None:
                ok_button.setText(accept_text)
            if cancel_button is not None:
                cancel_button.setText("取消")
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)

            return dialog.exec() == QDialog.DialogCode.Accepted

        def _relative_path_text(self, path: Path) -> str:
            try:
                return str(path.relative_to(self.project_root))
            except ValueError:
                return str(path)

        def show_undefined_labels(self) -> None:
            self.reload_project()
            if self.scan_result is None:
                return

            undefined_infos = sorted(
                [
                    info
                    for info in self.scan_result.labels.values()
                    if not info.definitions and info.references
                ],
                key=lambda info: info.name.lower(),
            )
            if not undefined_infos:
                QMessageBox.information(
                    self,
                    "扫描未定义标签",
                    "没有发现未定义标签。",
                )
                self.statusBar().showMessage("未发现未定义标签。", 6000)
                return

            rows: list[tuple[LabelInfo, Occurrence, int, int]] = []
            for info in undefined_infos:
                references = self.scan_result.sorted_occurrences(info.references)
                for index, occurrence in enumerate(references):
                    rows.append((info, occurrence, index, len(references)))

            dialog = QDialog(self)
            dialog.setWindowTitle("未定义标签扫描结果")
            dialog.resize(1150, 650)

            layout = QVBoxLayout(dialog)
            summary = QLabel(
                f"发现 {len(undefined_infos)} 个未定义标签，"
                f"共 {len(rows)} 个引用位置。双击某一行可跳转到该引用。"
            )
            summary.setWordWrap(True)
            summary.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            layout.addWidget(summary)

            table = QTableWidget(len(rows), 8, dialog)
            table.setHorizontalHeaderLabels(
                ["标签", "引用次数", "序号", "命令", "文件", "行", "列", "行内容"]
            )
            table.verticalHeader().setVisible(False)
            table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            table.horizontalHeader().setSectionResizeMode(
                0, QHeaderView.ResizeMode.ResizeToContents
            )
            table.horizontalHeader().setSectionResizeMode(
                1, QHeaderView.ResizeMode.ResizeToContents
            )
            table.horizontalHeader().setSectionResizeMode(
                2, QHeaderView.ResizeMode.ResizeToContents
            )
            table.horizontalHeader().setSectionResizeMode(
                3, QHeaderView.ResizeMode.ResizeToContents
            )
            table.horizontalHeader().setSectionResizeMode(
                4, QHeaderView.ResizeMode.ResizeToContents
            )
            table.horizontalHeader().setSectionResizeMode(
                5, QHeaderView.ResizeMode.ResizeToContents
            )
            table.horizontalHeader().setSectionResizeMode(
                6, QHeaderView.ResizeMode.ResizeToContents
            )
            table.horizontalHeader().setSectionResizeMode(
                7, QHeaderView.ResizeMode.Stretch
            )

            for row, (info, occurrence, index, total) in enumerate(rows):
                values = [
                    info.name,
                    str(len(info.references)),
                    f"{index + 1}/{total}",
                    occurrence.command,
                    self._relative_path_text(occurrence.path),
                    str(occurrence.line),
                    str(occurrence.column),
                    self._line_text(occurrence),
                ]
                for column, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    item.setForeground(QColor("#c92a2a"))
                    item.setData(
                        Qt.ItemDataRole.UserRole,
                        (occurrence, index, total),
                    )
                    table.setItem(row, column, item)

            def jump_to_reference(row: int, _column: int) -> None:
                item = table.item(row, 0)
                if item is None:
                    return
                occurrence, index, total = item.data(Qt.ItemDataRole.UserRole)
                dialog.accept()
                self.chapter_combo.setCurrentIndex(
                    max(0, self.chapter_combo.findData("__undefined__"))
                )
                self.select_label_row(occurrence.label)
                self.old_label_edit.setText(occurrence.label)
                self.new_label_edit.setText(occurrence.label)
                self.current_label = occurrence.label
                self.current_cycle_index = index
                self.show_occurrence(occurrence, index, total)

            table.cellDoubleClicked.connect(jump_to_reference)
            layout.addWidget(table, 1)

            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Close,
                dialog,
            )
            close_button = buttons.button(QDialogButtonBox.StandardButton.Close)
            if close_button is not None:
                close_button.setText("关闭")
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)

            self.statusBar().showMessage(
                f"发现 {len(undefined_infos)} 个未定义标签。", 8000
            )
            dialog.exec()

        def _line_text(self, occurrence: Occurrence) -> str:
            if self.scan_result is None:
                return ""
            text = self.scan_result.text_by_file.get(occurrence.path, "")
            lines = text.splitlines()
            if occurrence.line - 1 >= len(lines):
                return ""
            return lines[occurrence.line - 1].strip()

        def _add_category_row(self, category: str, label_count: int) -> None:
            row = self.table.rowCount()
            self.table.insertRow(row)
            item = QTableWidgetItem(f"{category}  ({label_count})")
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            item.setBackground(QColor("#e9ecef"))
            item.setForeground(QColor("#212529"))
            self.table.setItem(row, 0, item)
            self.table.setSpan(row, 0, 1, 5)

        def _add_label_row(self, info: LabelInfo) -> None:
            row = self.table.rowCount()
            self.table.insertRow(row)

            prefix_item = QTableWidgetItem()
            name_item = QTableWidgetItem(info.name)
            reference_item = QTableWidgetItem(str(len(info.references)))
            outside_reference_count = self._outside_chapter_reference_count(
                info, self._current_chapter_key()
            )
            outside_reference_item = QTableWidgetItem(str(outside_reference_count))
            count_item = QTableWidgetItem(str(info.total_count))
            tooltip = (
                f"定义: {len(info.definitions)}\n"
                f"引用: {len(info.references)}\n"
                f"章外引用: {outside_reference_count}\n"
                "点击同一行可在定义和引用之间循环跳转"
            )
            prefix_item.setToolTip(tooltip)
            name_item.setToolTip(tooltip)
            reference_item.setToolTip(tooltip)
            outside_reference_item.setToolTip(tooltip)
            count_item.setToolTip(tooltip)
            prefix_item.setData(Qt.ItemDataRole.UserRole, info.name)
            name_item.setData(Qt.ItemDataRole.UserRole, info.name)
            reference_item.setData(Qt.ItemDataRole.UserRole, info.name)
            outside_reference_item.setData(Qt.ItemDataRole.UserRole, info.name)
            count_item.setData(Qt.ItemDataRole.UserRole, info.name)
            prefix_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)

            prefix_state = self._chapter_prefix_state(info)
            if prefix_state is not None:
                prefix_item.setCheckState(prefix_state)

            if not info.definitions:
                name_item.setForeground(QColor("#c92a2a"))
                reference_item.setForeground(QColor("#c92a2a"))
                outside_reference_item.setForeground(QColor("#c92a2a"))
                count_item.setForeground(QColor("#c92a2a"))
            elif len(info.definitions) > 1:
                name_item.setForeground(QColor("#e67700"))
                reference_item.setForeground(QColor("#e67700"))
                outside_reference_item.setForeground(QColor("#e67700"))
                count_item.setForeground(QColor("#e67700"))
            elif not info.references:
                name_item.setForeground(QColor("#5c940d"))
                reference_item.setForeground(QColor("#5c940d"))
                outside_reference_item.setForeground(QColor("#5c940d"))
                count_item.setForeground(QColor("#5c940d"))

            self.table.setItem(row, 0, prefix_item)
            self.table.setItem(row, 1, name_item)
            self.table.setItem(row, 2, reference_item)
            self.table.setItem(row, 3, outside_reference_item)
            self.table.setItem(row, 4, count_item)

        def handle_table_click(self, row: int, column: int) -> None:
            item = self.table.item(row, column) or self.table.item(row, 0)
            if item is None:
                return
            label = item.data(Qt.ItemDataRole.UserRole)
            if not label or self.scan_result is None:
                return

            occurrences = self._cycle_occurrences(label)
            if not occurrences:
                return

            if label == self.current_label:
                self.current_cycle_index = (self.current_cycle_index + 1) % len(
                    occurrences
                )
            else:
                self.current_label = label
                self.current_cycle_index = 0

            self.old_label_edit.setText(label)
            self.new_label_edit.setText(label)
            self.show_occurrence(
                occurrences[self.current_cycle_index],
                self.current_cycle_index,
                len(occurrences),
            )

        def _cycle_occurrences(self, label: str) -> list[Occurrence]:
            info = self.scan_result.labels.get(label) if self.scan_result else None
            if info is None:
                return []
            definitions = self.scan_result.sorted_occurrences(info.definitions)
            references = self.scan_result.sorted_occurrences(info.references)
            return definitions + references

        def show_occurrence(
            self, occurrence: Occurrence, index: int, total: int
        ) -> None:
            if self.scan_result is None:
                return
            text = self.scan_result.text_by_file.get(occurrence.path, "")
            if occurrence.path != self._preview_path:
                self.preview.setPlainText(text)
                self._preview_path = occurrence.path

            line_starts = self.scan_result.line_starts_by_file.get(occurrence.path, [])
            if occurrence.line - 1 >= len(line_starts):
                return

            block = self.preview.document().findBlockByNumber(occurrence.line - 1)
            if not block.isValid():
                return

            column0 = occurrence.start - line_starts[occurrence.line - 1]
            end_column0 = occurrence.end - line_starts[occurrence.line - 1]
            start_position = block.position() + column0
            end_position = block.position() + end_column0

            cursor = QTextCursor(block)
            cursor.setPosition(start_position)
            cursor.setPosition(end_position, QTextCursor.MoveMode.KeepAnchor)
            self.preview.setTextCursor(cursor)
            self.preview.centerCursor()

            line_selection = QTextEdit.ExtraSelection()
            line_selection.cursor = QTextCursor(block)
            line_selection.format.setBackground(QColor("#fff3bf"))
            line_selection.format.setProperty(
                QTextFormat.Property.FullWidthSelection, True
            )

            label_selection = QTextEdit.ExtraSelection()
            label_selection.cursor = QTextCursor(block)
            label_selection.cursor.setPosition(start_position)
            label_selection.cursor.setPosition(
                end_position, QTextCursor.MoveMode.KeepAnchor
            )
            label_selection.format.setBackground(QColor("#ffd43b"))
            self.preview.setExtraSelections([line_selection, label_selection])

            rel_path = occurrence.path.relative_to(self.project_root)
            kind = "定义" if occurrence.kind == "definition" else f"引用({occurrence.command})"
            self.location_label.setText(
                f"{occurrence.label} - {kind} {index + 1}/{total}: "
                f"{rel_path}:{occurrence.line}:{occurrence.column}"
            )

        def rename_selected_label(self) -> None:
            if self.scan_result is None:
                return

            old_label = self.old_label_edit.text().strip()
            new_label = self.new_label_edit.text().strip()
            if not old_label:
                QMessageBox.warning(self, "无法重命名", "请先在左侧表格选择一个标签。")
                return
            if old_label == new_label:
                self.statusBar().showMessage("新旧标签相同，未修改。", 5000)
                return
            validation_error = self._validate_new_label(new_label)
            if validation_error:
                QMessageBox.warning(self, "新标签无效", validation_error)
                return

            info = self.scan_result.labels.get(old_label)
            if info is None:
                QMessageBox.warning(self, "标签不存在", old_label)
                return

            existing = self.scan_result.labels.get(new_label)
            if info.definitions and existing and existing.definitions:
                QMessageBox.warning(
                    self,
                    "标签已存在",
                    f"{new_label} 已经有定义，重命名会造成重复定义。",
                )
                return

            replacements = self._collect_rename_replacements({old_label: new_label})
            if not self._confirm_rename_changes(
                "确认重命名",
                f"将 {old_label} 重命名为 {new_label}。\n"
                f"会修改 {len(info.definitions)} 个定义、"
                f"{len(info.references)} 个引用，共 {len(replacements)} 个位置。",
                replacements,
                accept_text="执行重命名",
            ):
                return

            try:
                changed_files = self._apply_renames({old_label: new_label})
            except Exception as exc:
                QMessageBox.critical(self, "重命名失败", str(exc))
                return

            self.current_label = None
            self.current_cycle_index = -1
            self._preview_path = None
            self.reload_project(select_label=new_label)
            self.statusBar().showMessage(
                f"已重命名 {old_label} -> {new_label}，修改 {len(changed_files)} 个文件。",
                8000,
            )

        @staticmethod
        def _validate_new_label(label: str) -> str | None:
            if not label:
                return "新标签不能为空。"
            if any(char.isspace() for char in label):
                return "新标签不能包含空白字符。"
            invalid_chars = set("{}[],%\\")
            found = sorted({char for char in label if char in invalid_chars})
            if found:
                return "新标签不能包含这些字符: " + " ".join(found)
            return None

        def _apply_renames(self, rename_map: dict[str, str]) -> list[Path]:
            if self.scan_result is None:
                return []

            by_file: dict[Path, list[tuple[Occurrence, str]]] = defaultdict(list)
            replacements = self._collect_rename_replacements(rename_map)
            for occurrence, _, new_label in replacements:
                by_file[occurrence.path].append((occurrence, new_label))

            changed_files: list[Path] = []
            for path, file_replacements in by_file.items():
                text = self.scan_result.text_by_file[path]
                for occurrence, _ in file_replacements:
                    actual = text[occurrence.start : occurrence.end]
                    if actual != occurrence.label:
                        raise RuntimeError(
                            f"{path.name}:{occurrence.line} 的内容已经变化，"
                            "请重新扫描后再重命名。"
                        )

            for path, file_replacements in by_file.items():
                text = self.scan_result.text_by_file[path]
                for occurrence, new_label in sorted(
                    file_replacements, key=lambda item: item[0].start, reverse=True
                ):
                    text = text[: occurrence.start] + new_label + text[occurrence.end :]

                encoding = self.scan_result.encoding_by_file[path]
                path.write_bytes(text.encode(encoding))
                changed_files.append(path)

            return changed_files

        def select_label_row(self, label: str) -> None:
            for row in range(self.table.rowCount()):
                item = self.table.item(row, 0)
                if item and item.data(Qt.ItemDataRole.UserRole) == label:
                    self.table.selectRow(row)
                    self.handle_table_click(row, 0)
                    return

    app = QApplication(sys.argv)
    window = LabelManagerWindow(root_dir)
    window.show()
    return app.exec()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LaTeX label manager")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="LaTeX project root directory. Defaults to the current directory.",
    )
    parser.add_argument(
        "--scan",
        action="store_true",
        help="Only scan the project and print a summary, without starting the GUI.",
    )
    args = parser.parse_args(argv)

    root_dir = args.root.resolve()
    if args.scan:
        result = LatexProjectScanner(root_dir).scan()
        print_scan_summary(result)
        return 0

    return run_gui(root_dir)


if __name__ == "__main__":
    raise SystemExit(main())
