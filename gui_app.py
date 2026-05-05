import sys
import os
import re
import shutil
import yaml
import pykakasi
import json
from pathlib import Path
from typing import List, Dict, Optional, Any

from PySide6.QtCore import Qt, QSize, QSettings, QRunnable, QThreadPool, Signal, QObject
from PySide6.QtGui import QStandardItemModel, QStandardItem, QFont, QColor, QPalette, QPainter, QIcon
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QFileDialog, QTableView,
    QHeaderView, QSplitter, QGroupBox, QCheckBox, QStatusBar,
    QMessageBox, QFrame, QSpinBox, QSizePolicy, QStyledItemDelegate,
    QStyle
)

class HoverDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.hovered_row = -1

    def paint(self, painter, option, index):
        # Fill background if row is hovered and not selected
        if index.row() == self.hovered_row and not (option.state & QStyle.State_Selected):
            painter.save()
            painter.fillRect(option.rect, option.palette.alternateBase())
            painter.restore()
        super().paint(painter, option, index)

class DropOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.hide()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        pal = self.palette()
        
        # Semi-transparent background
        bg_color = QColor(pal.color(QPalette.Highlight))
        bg_color.setAlpha(40)
        painter.setBrush(bg_color)
        painter.setPen(Qt.NoPen)
        painter.drawRect(self.rect())
        
        # Border
        border_pen = QColor(pal.color(QPalette.Highlight))
        painter.setPen(border_pen)
        painter.drawRect(self.rect().adjusted(10, 10, -10, -10))
        
        # Text
        painter.setPen(pal.color(QPalette.WindowText))
        painter.setFont(QFont("Segoe UI", 20, QFont.Bold))
        painter.drawText(self.rect(), Qt.AlignCenter, "ファイルをドロップして読み込み")

class RenameWorkerSignals(QObject):
    finished = Signal()
    progress = Signal(str)
    error = Signal(str)

class RenameWorker(QRunnable):
    def __init__(self, tasks, output_dir):
        super().__init__()
        self.tasks = tasks # List of (src, dst)
        self.output_dir = output_dir
        self.signals = RenameWorkerSignals()

    def run(self):
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            for src, dst in self.tasks:
                shutil.copy2(src, dst)
            self.signals.finished.emit()
        except Exception as e:
            self.signals.error.emit(str(e))

class OggRenameApp(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("OGG File Renamer (Qt Edition)")
        self.resize(1100, 850)

        # Core logic setup
        self.kks = pykakasi.kakasi()
        self.input_paths: List[Path] = []
        self.output_dir: Optional[Path] = None
        self.preview_data: List[Dict[str, Any]] = []
        self.thread_pool = QThreadPool.globalInstance()
        self.forbidden_chars = []
        
        self.init_settings_dir()
        self.setup_ui()
        self.load_settings()


    def init_settings_dir(self) -> None:
        # Get directory where the script/exe is located
        if getattr(sys, 'frozen', False):
            # Bundled by PyInstaller
            base_dir = Path(sys.executable).parent
        else:
            # Running as script
            base_dir = Path(__file__).parent

        self.settings_dir = base_dir / "settings"
        self.settings_dir.mkdir(exist_ok=True)
        
        # 1. Forbidden Chars
        chars_file = self.settings_dir / "forbidden_chars.json"
        default_forbidden = [" ", "　", "!", "?", "\"", "#", "$", "%", "&", "'", "(", ")", "=", "~", "|", "^", "@", "[", "]", "{", "}", ";", ":", "+", "*", ",", "<", ">", ".", "/", "\\"]
        if not chars_file.exists():
            with open(chars_file, "w", encoding="utf-8") as f:
                json.dump({"forbidden": default_forbidden}, f, ensure_ascii=False, indent=4)
        
        try:
            with open(chars_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.forbidden_chars = data.get("forbidden", default_forbidden)
        except Exception:
            self.forbidden_chars = default_forbidden
            
        # 2. App Config
        self.config_file = self.settings_dir / "config.json"
        if not self.config_file.exists():
            default_config = {
                "char_limit": 63,
                "regex_enabled": False,
                "prefix_text": "",
                "output_dir": ""
            }
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=4)
        
        try:
            with open(chars_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.forbidden_chars = data.get("forbidden", default_forbidden)
        except Exception:
            self.forbidden_chars = default_forbidden

    def closeEvent(self, event) -> None:
        self.save_settings()
        super().closeEvent(event)

    def save_settings(self) -> None:
        config = {
            "char_limit": self.ent_limit.value(),
            "regex_enabled": self.chk_regex.isChecked(),
            "prefix_text": self.ent_prefix.text(),
            "output_dir": str(self.output_dir) if self.output_dir else ""
        }
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")

    def load_settings(self) -> None:
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
                
            self.ent_limit.setValue(config.get("char_limit", 63))
            self.chk_regex.setChecked(config.get("regex_enabled", False))
            self.ent_prefix.setText(config.get("prefix_text", ""))
            
            saved_dir = config.get("output_dir", "")
            if saved_dir and os.path.exists(saved_dir):
                self.output_dir = Path(saved_dir)
                self.lbl_output.setText(saved_dir)
        except Exception as e:
            print(f"Error loading config: {e}")

    def setup_ui(self) -> None:
        # Main Widget and Layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        self.setAcceptDrops(True)
        main_layout = QVBoxLayout(main_widget)

        # DnD Overlay
        self.drop_overlay = DropOverlay(self)

        # Splitter for Sidebar and Content
        self.splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(self.splitter)

        # --- Sidebar (Left) ---
        self.sidebar = QFrame()
        self.sidebar.setMinimumWidth(320)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(0, 0, 10, 0)

        # 1. Input Group
        input_group = QGroupBox("入力設定")
        input_layout = QVBoxLayout(input_group)
        
        self.btn_select_folder = QPushButton("📁 フォルダを選択")
        self.btn_select_folder.clicked.connect(self.select_folder)
        input_layout.addWidget(self.btn_select_folder)

        self.btn_select_files = QPushButton("📄 ファイルを選択")
        self.btn_select_files.clicked.connect(self.select_files)
        input_layout.addWidget(self.btn_select_files)

        self.lbl_path = QLabel("未選択")
        self.lbl_path.setWordWrap(True)
        self.lbl_path.setStyleSheet("color: gray;")
        input_layout.addWidget(self.lbl_path)
        
        sidebar_layout.addWidget(input_group)

        # 2. Settings Group
        settings_group = QGroupBox("変換・警告設定")
        settings_layout = QVBoxLayout(settings_group)
        
        lim_layout = QHBoxLayout()
        lim_layout.addWidget(QLabel("文字数警告:"))
        self.ent_limit = QSpinBox()
        self.ent_limit.setRange(1, 999)
        self.ent_limit.setValue(63)
        self.ent_limit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.ent_limit.valueChanged.connect(self.update_preview)
        lim_layout.addWidget(self.ent_limit)
        lim_layout.addWidget(QLabel("文字以上"))
        settings_layout.addLayout(lim_layout)
        
        sidebar_layout.addWidget(settings_group)

        # 2.5 Bulk Edit Group
        bulk_group = QGroupBox("一括編集")
        bulk_layout = QVBoxLayout(bulk_group)
        
        # Prefix
        pre_layout = QHBoxLayout()
        self.ent_prefix = QLineEdit()
        self.ent_prefix.setPlaceholderText("接頭辞 (例: music_)")
        pre_layout.addWidget(self.ent_prefix)
        btn_add_prefix = QPushButton("追加")
        btn_add_prefix.clicked.connect(self.bulk_add_prefix)
        pre_layout.addWidget(btn_add_prefix)
        bulk_layout.addLayout(pre_layout)
        
        # Replace
        rep_layout = QHBoxLayout()
        self.ent_src = QLineEdit()
        self.ent_src.setPlaceholderText("置換前")
        self.ent_dst = QLineEdit()
        self.ent_dst.setPlaceholderText("置換後")
        rep_layout.addWidget(self.ent_src)
        rep_layout.addWidget(QLabel("→"))
        rep_layout.addWidget(self.ent_dst)
        bulk_layout.addLayout(rep_layout)
        
        rep_control_layout = QHBoxLayout()
        self.chk_regex = QCheckBox("Regex")
        rep_control_layout.addWidget(self.chk_regex)
        
        btn_replace = QPushButton("一括置換")
        btn_replace.clicked.connect(self.bulk_replace)
        rep_control_layout.addWidget(btn_replace)
        bulk_layout.addLayout(rep_control_layout)

        # Duplicates
        self.btn_resolve = QPushButton("重複を連番で解消")
        self.btn_resolve.clicked.connect(self.resolve_duplicates)
        bulk_layout.addWidget(self.btn_resolve)
        
        sidebar_layout.addWidget(bulk_group)

        # 3. Output Group
        output_group = QGroupBox("出力設定")
        output_layout = QVBoxLayout(output_group)
        
        self.btn_select_output = QPushButton("📂 出力先を変更")
        self.btn_select_output.clicked.connect(self.select_output_folder)
        output_layout.addWidget(self.btn_select_output)

        self.lbl_output = QLabel("デフォルト\n(入力フォルダ/renamed)")
        self.lbl_output.setWordWrap(True)
        self.lbl_output.setStyleSheet("color: gray;")
        output_layout.addWidget(self.lbl_output)
        
        sidebar_layout.addWidget(output_group)

        sidebar_layout.addStretch()

        # 4. Action Area
        self.btn_run = QPushButton("リネーム実行")
        self.btn_run.setEnabled(False)
        self.btn_run.setFixedHeight(50)
        self.btn_run.setObjectName("runButton")
        self.btn_run.clicked.connect(self.run_rename)
        sidebar_layout.addWidget(self.btn_run)

        self.splitter.addWidget(self.sidebar)

        # --- Content Area (Right) ---
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(10, 0, 0, 0)

        # Header
        header_layout = QHBoxLayout()
        lbl_preview = QLabel("プレビュー")
        lbl_preview.setFont(QFont("Segoe UI", 14, QFont.Bold))
        header_layout.addWidget(lbl_preview)
        
        header_layout.addStretch()
        
        self.btn_refresh = QPushButton("🔄 更新")
        self.btn_refresh.clicked.connect(self.update_preview)
        header_layout.addWidget(self.btn_refresh)
        content_layout.addLayout(header_layout)

        content_layout.addWidget(QLabel("※ファイル名をダブルクリックで編集"))

        # Filter
        self.chk_filter = QCheckBox("警告ありのみ表示")
        self.chk_filter.stateChanged.connect(self.refresh_table)
        content_layout.addWidget(self.chk_filter)

        # Table
        self.table_view = QTableView()
        self.model = QStandardItemModel(0, 5)
        self.model.setHorizontalHeaderLabels(["再生", "元のファイル名", "変換後のファイル名", "文字数", "ステータス"])
        self.table_view.setModel(self.model)
        
        # Table configuration
        header = self.table_view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        self.table_view.setColumnWidth(0, 45)
        self.table_view.setColumnWidth(1, 300)
        self.table_view.setColumnWidth(2, 300)
        self.table_view.setColumnWidth(3, 70)
        self.table_view.setColumnWidth(4, 150)
        
        self.table_view.setSelectionBehavior(QTableView.SelectRows)
        self.table_view.setShowGrid(False)
        self.table_view.setMouseTracking(True)
        
        # Add hover delegate
        self.hover_delegate = HoverDelegate(self.table_view)
        self.table_view.setItemDelegate(self.hover_delegate)
        self.table_view.entered.connect(self.on_row_hovered)
        self.table_view.installEventFilter(self) # For Key events
        self.table_view.viewport().installEventFilter(self) # For Mouse events
        
        self.table_view.clicked.connect(self.handle_table_click)
        
        # Connect edit signal
        self.model.itemChanged.connect(self.on_item_changed)
        
        content_layout.addWidget(self.table_view)
        
        # Apply theme-based grid color
        self.apply_table_theme()

        self.splitter.addWidget(content_widget)
        self.splitter.setStretchFactor(1, 3)

        # Status Bar
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("準備完了")

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, 'drop_overlay'):
            self.drop_overlay.setGeometry(self.rect())

    def on_row_hovered(self, index) -> None:
        self.hover_delegate.hovered_row = index.row()
        self.table_view.viewport().update()

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.drop_overlay.show()

    def dragLeaveEvent(self, event) -> None:
        self.drop_overlay.hide()

    def dropEvent(self, event) -> None:
        self.drop_overlay.hide()
        urls = event.mimeData().urls()
        dropped_paths = [Path(url.toLocalFile()) for url in urls]
        
        target_files = []
        for p in dropped_paths:
            if p.is_dir():
                # Get all ogg files in directory
                target_files.extend(list(p.glob("*.ogg")))
            elif p.suffix.lower() == ".ogg":
                target_files.append(p)
        
        if target_files:
            # Sort for consistency
            target_files.sort()
            self.input_paths = target_files
            self.lbl_path.setText(f"読み込み済: {len(target_files)} files")
            
            # Set default output dir if not already set
            if not self.output_dir:
                self.output_dir = target_files[0].parent / "renamed"
                self.lbl_output.setText(str(self.output_dir))
                
            self.update_preview()
            self.statusBar().showMessage(f"{len(target_files)} 個のファイルをドロップで読み込みました")

    def eventFilter(self, source, event) -> bool:
        # Check if mouse left the table view area
        if source == self.table_view.viewport():
            if event.type() == event.Type.Leave:
                self.hover_delegate.hovered_row = -1
                self.table_view.viewport().update()
        
        # F2 key to rename
        if event.type() == event.Type.KeyPress and event.key() == Qt.Key_F2:
            idx = self.table_view.currentIndex()
            if idx.isValid():
                target_idx = self.model.index(idx.row(), 2)
                self.table_view.setCurrentIndex(target_idx)
                self.table_view.edit(target_idx)
                return True

        return super().eventFilter(source, event)

    def apply_table_theme(self) -> None:
        self.table_view.setStyleSheet("""
            QTableView {
                background-color: transparent;
                outline: 0;
            }
            QTableView::item {
                border-bottom: 1px solid palette(mid);
                padding: 4px;
            }
            QTableView::item:selected {
                background-color: palette(highlight);
                color: palette(highlighted-text);
            }
            /* Row hover handled by Delegate */
            QTableView QLineEdit {
                border: none;
                background-color: palette(base);
                color: palette(text);
            }
            QHeaderView::section {
                background-color: palette(window);
                color: palette(window-text);
                border: none;
                border-bottom: 2px solid palette(mid);
                border-right: 1px solid palette(mid);
                padding: 4px;
            }
        """)

    def handle_table_click(self, index) -> None:
        # Check if the "Play" column (index 0) was clicked
        if index.column() == 0:
            row = index.row()
            if row < len(self.preview_data):
                path = self.preview_data[row]["path"]
                os.startfile(path)


    def on_item_changed(self, item: QStandardItem) -> None:
        # Only handle changes in the "Renamed" column (index 2)
        if item.column() != 2:
            return
            
        row = item.row()
        new_name = item.text()
        
        # Update underlying data
        if row < len(self.preview_data):
            self.preview_data[row]["renamed"] = new_name
            
            # Recalculate validation
            limit = self.get_limit()
            length = len(new_name)
            is_warning = length >= limit
            
            self.preview_data[row]["length"] = length
            self.preview_data[row]["status"] = "警告: 文字数超過" if is_warning else "待機中"
            self.preview_data[row]["is_warning"] = is_warning
            
            # Temporarily block signals to avoid recursion when updating other columns
            self.model.blockSignals(True)
            
            # Update Length column (index 3)
            len_item = self.model.item(row, 3)
            len_item.setText(str(length))
            
            # Update Status column (index 4)
            status_item = self.model.item(row, 4)
            status_item.setText(self.preview_data[row]["status"])
            
            # Update colors for the whole row (skip play button at 0)
            color = QColor("red") if is_warning else QColor("black")
            bg_color = QColor("#fff0f0") if is_warning else QColor("white")
            
            for col in range(1, 5):
                curr_item = self.model.item(row, col)
                if curr_item:
                    curr_item.setForeground(color)
                    curr_item.setBackground(bg_color)
            
            self.model.blockSignals(False)
            
            # Update Run button state
            has_warning = any(d["is_warning"] for d in self.preview_data)
            self.btn_run.setEnabled(has_warning == False and len(self.preview_data) > 0)


    # --- Bulk Edit Logic ---

    def bulk_add_prefix(self) -> None:
        prefix = self.ent_prefix.text()
        if not prefix: return
        
        for item in self.preview_data:
            item["renamed"] = prefix + item["renamed"]
        
        self.update_preview_after_bulk()

    def bulk_replace(self) -> None:
        src = self.ent_src.text()
        dst = self.ent_dst.text()
        if not src: return
        
        is_regex = self.chk_regex.isChecked()
        
        for item in self.preview_data:
            if is_regex:
                try:
                    item["renamed"] = re.sub(src, dst, item["renamed"])
                except Exception as e:
                    self.statusBar().showMessage(f"Regexエラー: {e}")
                    return
            else:
                item["renamed"] = item["renamed"].replace(src, dst)
        
        self.update_preview_after_bulk()

    def resolve_duplicates(self) -> None:
        if not self.preview_data: return
        
        # Count current names
        name_groups = {}
        for i, item in enumerate(self.preview_data):
            name = item["renamed"]
            if name not in name_groups:
                name_groups[name] = []
            name_groups[name].append(i)
            
        for name, indices in name_groups.items():
            if len(indices) > 1:
                # We have duplicates
                for count, idx in enumerate(indices, 1):
                    # Append _01, _02...
                    self.preview_data[idx]["renamed"] = f"{name}_{count:02d}"
                    
        self.update_preview_after_bulk()
        self.statusBar().showMessage("重複を連番で解消しました")

    def update_preview_after_bulk(self) -> None:
        # Re-validate all based on current "renamed" values in preview_data
        limit = self.get_limit()
        
        # Count occurrences for duplicate detection
        name_counts = {}
        for item in self.preview_data:
            name = item["renamed"]
            name_counts[name] = name_counts.get(name, 0) + 1
            
        has_issue = False
        for item in self.preview_data:
            name = item["renamed"]
            length = len(name)
            is_over_limit = length >= limit
            is_duplicate = name_counts[name] > 1
            
            if is_duplicate:
                item["status"] = "エラー: 名前重複"
                item["is_warning"] = True
                has_issue = True
            elif is_over_limit:
                item["status"] = "警告: 文字数超過"
                item["is_warning"] = True
                has_issue = True
            else:
                item["status"] = "待機中"
                item["is_warning"] = False
                
        self.refresh_table()
        # Enable run only if NO warnings/errors and data exists
        self.btn_run.setEnabled(not has_issue and len(self.preview_data) > 0)

    # --- Logic Methods ---

    def select_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "フォルダを選択")
        if folder:
            p = Path(folder)
            self.input_paths = list(p.glob("*.ogg"))
            self.lbl_path.setText(f"フォルダ: {folder}\n({len(self.input_paths)} files)")
            self.output_dir = p / "renamed"
            self.lbl_output.setText(str(self.output_dir))
            self.update_preview()
            self.statusBar().showMessage(f"フォルダを読み込みました: {folder}")

    def select_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "ファイルを選択", "", "OGG Files (*.ogg)")
        if files:
            self.input_paths = [Path(f) for f in files]
            folder = self.input_paths[0].parent
            self.lbl_path.setText(f"ファイル: {len(files)}個")
            self.output_dir = folder / "renamed"
            self.lbl_output.setText(str(self.output_dir))
            self.update_preview()
            self.statusBar().showMessage(f"{len(files)}個のファイルを読み込みました")

    def select_output_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "出力先を選択")
        if folder:
            self.output_dir = Path(folder)
            self.lbl_output.setText(str(folder))

    def convert_filename(self, filename: str) -> str:
        stem = Path(filename).stem
        try:
            result = self.kks.convert(stem)
            romaji = "".join([item['hepburn'] for item in result])
        except Exception:
            romaji = stem
        
        # Apply forbidden chars from external settings
        for char in self.forbidden_chars:
            romaji = romaji.replace(char, "_")
            
        cleaned = re.sub(r'[^A-Za-z0-9_]', '', romaji)
        return cleaned

    def update_preview(self) -> None:
        limit = self.get_limit()
        self.preview_data = []
        has_warning = False

        for p in self.input_paths:
            new_stem = self.convert_filename(p.name)
            length = len(new_stem)
            is_warning = length >= limit
            if is_warning: has_warning = True

            self.preview_data.append({
                "original": p.name,
                "renamed": new_stem,
                "length": length,
                "status": "警告: 文字数超過" if is_warning else "待機中",
                "is_warning": is_warning,
                "path": p
            })
        
        self.refresh_table()
        self.btn_run.setEnabled(not has_warning and len(self.preview_data) > 0)

    def refresh_table(self) -> None:
        self.model.removeRows(0, self.model.rowCount())
        limit = self.get_limit()
        show_only_warning = self.chk_filter.isChecked()

        for item in self.preview_data:
            if show_only_warning and not item["is_warning"]:
                continue
            
            # Create items
            it_play = QStandardItem("▶️")
            it_orig = QStandardItem(item["original"])
            it_renamed = QStandardItem(item["renamed"])
            it_len = QStandardItem(str(item["length"]))
            it_status = QStandardItem(item["status"])
            
            # Set editability: Only the "Renamed" column (index 2) is editable
            it_play.setEditable(False)
            it_orig.setEditable(False)
            it_renamed.setEditable(True)
            it_len.setEditable(False)
            it_status.setEditable(False)
            
            it_play.setTextAlignment(Qt.AlignCenter)
            
            row = [it_play, it_orig, it_renamed, it_len, it_status]
            
            # Formatting
            if item["is_warning"]:
                for cell in row[1:]: # Skip play button for coloring if preferred, or include all
                    cell.setForeground(QColor("red"))
                    cell.setBackground(QColor("#fff0f0"))
            
            self.model.appendRow(row)

    def get_limit(self) -> int:
        return self.ent_limit.value()

    def run_rename(self) -> None:
        if not self.output_dir: return
        
        prefix = self.ent_prefix.text() or "mod"
        mapping = {}
        tasks = []
        
        for item in self.preview_data:
            src = item["path"]
            new_name = item["renamed"]
            dest = self.output_dir / f"{new_name}{src.suffix}"
            tasks.append((src, dest))
            mapping[new_name] = Path(item["original"]).stem

        # Disable UI
        self.btn_run.setEnabled(False)
        self.statusBar().showMessage("実行中 (並列処理)...")

        worker = RenameWorker(tasks, self.output_dir)
        
        def on_finished():
            # Generate YAML
            try:
                yaml_path = self.generate_yaml(mapping, self.output_dir, prefix)
                QMessageBox.information(self, "完了", f"リネームとYAML生成が完了しました。\n出力先: {self.output_dir}")
                self.statusBar().showMessage(f"完了: {yaml_path.name}")
            except Exception as e:
                QMessageBox.critical(self, "エラー", f"YAML作成に失敗しました: {e}")
            self.btn_run.setEnabled(True)

        def on_error(err):
            QMessageBox.critical(self, "エラー", f"処理中にエラーが発生しました:\n{err}")
            self.btn_run.setEnabled(True)
            self.statusBar().showMessage("エラー発生")

        worker.signals.finished.connect(on_finished)
        worker.signals.error.connect(on_error)
        
        self.thread_pool.start(worker)

    def generate_yaml(self, mapping: Dict[str, str], output_dir: Path, prefix: str) -> Path:
        yaml_path = output_dir / f"{prefix}_l_japanese.yml"
        
        # Custom representer to force quotes only on values
        class QuotedStr(str): pass
        yaml.add_representer(QuotedStr, lambda dumper, data: dumper.represent_scalar('tag:yaml.org,2002:str', data, style='"'))
        
        quoted_mapping = {k: QuotedStr(v) for k, v in mapping.items()}
        output_data = {"l_japanese": quoted_mapping}
        
        with open(yaml_path, "w", encoding="utf-8-sig") as f:
            yaml.dump(output_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False, width=float("inf"), indent=1)
        return yaml_path

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = OggRenameApp()
    window.show()
    sys.exit(app.exec())
