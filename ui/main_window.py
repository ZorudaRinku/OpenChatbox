import sys
import time
import logging
from services.osc import OSCClient
from config import save_config

logger = logging.getLogger(__name__)
from ui.char_width import count_visual_lines
from PySide6.QtCore import Qt, QTimer, QThread, QObject, Signal, Slot
from PySide6.QtGui import QBrush, QColor, QDesktopServices, QPalette, QTextOption
from PySide6.QtWidgets import QMainWindow, QWidget, QLabel, QVBoxLayout, QAbstractItemView, QStyledItemDelegate, QTextEdit, QPushButton, QListWidget, QListWidgetItem, QHBoxLayout, QLineEdit, QComboBox, QScrollArea, QToolButton, QSpinBox, QTreeWidget, QTreeWidgetItem


TOKEN_GROUPS = [
    ("Time & Date", ["time", "date", "utc", "timezone", "countdown", "session", "uptime"]),
    ("Specs", ["cpu", "cpuspeed", "cpu_temp", "ram", "ramgb", "disk",
               "gpu", "gpuspeed", "gpu_temp", "battery"]),
    ("OS", ["window", "wm", "de", "distro"]),
    ("Network", ["network", "ping", "weather"]),
    ("Media", ["nowplaying", "artist", "song", "song_progress",
               "song_progress_bar", "volume"]),
    ("Streaming", ["twitch_followers", "twitch_viewers", "heartrate", "heartrate_emote"]),
    ("Misc", ["random", "blankline", "egg"]),
]


class SendWorker(QObject):
    """Resolves tokens and sends OSC messages off the main thread."""
    send_complete = Signal()

    @Slot(str)
    def send(self, text):
        if self.text_processor:
            text = self.text_processor.process(text)
        self.osc_client.send_message(text)
        self.send_complete.emit()


class ResolveWorker(QObject):
    """Resolves tokens for UI validation off the main thread."""
    text_resolved = Signal(str)
    item_resolved = Signal(int, str)

    @Slot(str)
    def resolve_text(self, text):
        resolved = self.text_processor.process(text) if self.text_processor else text
        self.text_resolved.emit(resolved)

    @Slot(int, str)
    def resolve_item(self, row, text):
        resolved = self.text_processor.process(text) if self.text_processor else text
        self.item_resolved.emit(row, resolved)


class UpdateBanner(QWidget):
    URL = "https://github.com/ZorudaRinku/OpenChatbox/releases/latest"

    def __init__(self, version: str, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.version = version
        self.setObjectName("UpdateBanner")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setFixedHeight(28)

        pal = self.palette()
        base = pal.color(QPalette.ColorRole.Window)
        blue_tint = QColor(
            int(base.red() * 0.92),
            int(base.green() * 0.92),
            min(255, int(base.blue() * 1.12)),
        )
        border = blue_tint.darker(120)
        self.setStyleSheet(f"""
            #UpdateBanner {{
                background-color: {blue_tint.name()};
                border-bottom: 1px solid {border.name()};
            }}
            #UpdateBanner QLabel, #UpdateBanner QPushButton {{
                background: transparent;
                font-size: 12px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 6, 0)

        label = QLabel(f"Version {version} is available!")
        layout.addWidget(label)

        layout.addStretch()

        link_text = "Release Notes" if sys.platform != "win32" else "Download"
        link = QPushButton(link_text)
        link.setCursor(Qt.CursorShape.PointingHandCursor)
        link.setFlat(True)
        link_color = pal.color(QPalette.ColorRole.Link)
        link.setStyleSheet(f"color: {link_color.name()}; text-decoration: underline; padding: 0;")
        link.clicked.connect(lambda: QDesktopServices.openUrl(self.URL))
        layout.addWidget(link)

        dismiss = QPushButton("\u2715")
        dismiss.setCursor(Qt.CursorShape.PointingHandCursor)
        dismiss.setFlat(True)
        dismiss.setStyleSheet("padding: 0 4px;")
        dismiss.clicked.connect(self._dismiss)
        layout.addWidget(dismiss)

    def _dismiss(self):
        self.config["dismissed_update"] = self.version
        save_config(self.config)
        self.setVisible(False)

class ChatItemDelegate(QStyledItemDelegate):
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        if not index.data(Qt.ItemDataRole.UserRole):
            dim = option.palette.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text)
            option.palette.setColor(QPalette.ColorRole.HighlightedText, dim)

class MainWindow(QMainWindow):
    _send_requested = Signal(str)
    _resolve_text_requested = Signal(str)
    _resolve_item_requested = Signal(int, str)

    def __init__(self, osc_client: OSCClient, config, parent=None, text_processor=None):
        super().__init__(parent)
        self.config = config
        self.text_processor = text_processor

        # Worker thread for OSC send
        self._send_thread = QThread()
        self._send_worker = SendWorker()
        self._send_worker.text_processor = text_processor
        self._send_worker.osc_client = osc_client
        self._send_worker.moveToThread(self._send_thread)
        self._send_requested.connect(self._send_worker.send)
        self._send_worker.send_complete.connect(self._on_send_complete)
        self._sending = False
        self._last_send_ms = 0
        self._send_thread.start()

        # Worker thread for UI validation
        self._resolve_thread = QThread()
        self._resolve_worker = ResolveWorker()
        self._resolve_worker.text_processor = text_processor
        self._resolve_worker.moveToThread(self._resolve_thread)
        self._resolve_text_requested.connect(self._resolve_worker.resolve_text)
        self._resolve_item_requested.connect(self._resolve_worker.resolve_item)
        self._resolve_worker.text_resolved.connect(self._on_text_resolved)
        self._resolve_worker.item_resolved.connect(self._on_item_resolved)
        self._resolve_thread.start()

        # Main
        central = QWidget()
        self.setCentralWidget(central)
        self.main_layout = QVBoxLayout(central)

        from app import VERSION
        from services.update_check import UpdateChecker

        self._update_thread = QThread()
        self._update_checker = UpdateChecker(VERSION)
        self._update_checker.moveToThread(self._update_thread)
        self._update_thread.started.connect(self._update_checker.run)
        self._update_checker.update_available.connect(self._on_update_available)
        self._update_checker.finished.connect(self._update_thread.quit)
        self._update_thread.start()

        content_layout = QHBoxLayout()

        # List + Buttons (left side)
        list_layout = QVBoxLayout()
        self.list = QListWidget()
        self.list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.list.setDragDropMode(QAbstractItemView.InternalMove)
        self.list.setItemDelegate(ChatItemDelegate(self.list))
        self.list.currentRowChanged.connect(self.item_click)
        self.list.itemDoubleClicked.connect(self.toggle_item_enabled)
        self.list.model().rowsMoved.connect(self._schedule_save)
        list_layout.addWidget(self.list)

        button_row = QHBoxLayout()
        btn_style = "font-size: 16px"
        self.add = QPushButton("+")
        self.add.setStyleSheet(btn_style)
        self.add.setToolTip("Add a new chat")
        self.add.clicked.connect(self.click_add)
        button_row.addWidget(self.add)
        self.remove = QPushButton("-")
        self.remove.setStyleSheet(btn_style)
        self.remove.setToolTip("Remove selected chats")
        self.remove.clicked.connect(self.click_remove)
        button_row.addWidget(self.remove)
        self.copy = QPushButton("⧉")
        self.copy.setStyleSheet(btn_style)
        self.copy.setToolTip("Duplicate selected chat")
        self.copy.clicked.connect(self.click_copy)
        button_row.addWidget(self.copy)
        list_layout.addLayout(button_row)

        cycle_row = QHBoxLayout()
        cycle_row.setSpacing(4)
        self.cycle_spin = QSpinBox()
        self.cycle_spin.setRange(0, 999)
        self.cycle_spin.setPrefix("Cycle: ")
        self.cycle_spin.setSuffix("s")
        self.cycle_spin.setSpecialValueText("Cycle: off")
        self.cycle_spin.setToolTip("Seconds between cycling to the next chat")
        cycle_val = config.get("osc", {}).get("cycle_interval", 4)
        if cycle_val == 1:
            cycle_val = 2
        self.cycle_spin.setValue(cycle_val)
        self._prev_cycle = cycle_val
        self.cycle_spin.valueChanged.connect(self._on_cycle_changed)
        cycle_row.addWidget(self.cycle_spin)
        self.update_spin = QSpinBox()
        self.update_spin.setRange(0, 999)
        self.update_spin.setPrefix("Update: ")
        self.update_spin.setSuffix("s")
        self.update_spin.setSpecialValueText("Update: off")
        self.update_spin.setToolTip("Seconds between re-sending the current chat")
        update_val = config.get("osc", {}).get("update_interval", 2)
        if update_val == 1:
            update_val = 2
        self.update_spin.setValue(update_val)
        self._prev_update = update_val
        self.update_spin.valueChanged.connect(self._on_update_changed)
        cycle_row.addWidget(self.update_spin)
        list_layout.addLayout(cycle_row)

        content_layout.addLayout(list_layout)

        # Right side: vertical split
        right_layout = QVBoxLayout()

        # Top: edit field + labels
        self.edit_text = QTextEdit()
        opt = QTextOption()
        opt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.edit_text.document().setDefaultTextOption(opt)
        self.edit_text.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.edit_text.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.edit_text.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.edit_text.setWordWrapMode(QTextOption.WrapMode.WrapAnywhere)
        self.edit_text.textChanged.connect(self.text_edited)
        right_layout.addWidget(self.edit_text)

        label_row = QHBoxLayout()
        self.charcount = QLabel("0/144 Characters")
        self.charcount.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.charcount.setFixedHeight(self.add.sizeHint().height())
        label_row.addWidget(self.charcount)
        self.linecount = QLabel("0/9 Lines")
        self.linecount.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.linecount.setFixedHeight(self.add.sizeHint().height())
        label_row.addWidget(self.linecount)
        right_layout.addLayout(label_row)

        # Bottom: list on left, editable fields on right
        bottom_widget = QWidget()
        bottom_layout = QHBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 0, 0, 0)

        self.right_list = QTreeWidget()
        self.right_list.setHeaderHidden(True)
        self.right_list.setRootIsDecorated(True)
        self.right_list.setAnimated(True)
        if self.text_processor:
            remaining = dict(self.text_processor.tokens)
            bold_font = None
            for group_name, tags in TOKEN_GROUPS:
                group_item = QTreeWidgetItem([group_name])
                if bold_font is None:
                    bold_font = group_item.font(0)
                    bold_font.setBold(True)
                group_item.setFont(0, bold_font)
                group_item.setFlags(group_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                self.right_list.addTopLevelItem(group_item)
                for tag in tags:
                    if tag in remaining:
                        child = QTreeWidgetItem([f"<{tag}>"])
                        child.setData(0, Qt.ItemDataRole.UserRole, tag)
                        group_item.addChild(child)
                        del remaining[tag]
                if group_item.childCount() == 0:
                    group_item.setHidden(True)
            if remaining:
                misc = self.right_list.findItems("Misc", Qt.MatchFlag.MatchExactly, 0)
                misc_item = misc[0] if misc else None
                if misc_item is None:
                    misc_item = QTreeWidgetItem(["Misc"])
                    misc_item.setFont(0, bold_font)
                    misc_item.setFlags(misc_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                    self.right_list.addTopLevelItem(misc_item)
                misc_item.setHidden(False)
                for tag in remaining:
                    child = QTreeWidgetItem([f"<{tag}>"])
                    child.setData(0, Qt.ItemDataRole.UserRole, tag)
                    misc_item.addChild(child)
            self.right_list.expandAll()
        self.right_list.currentItemChanged.connect(
            lambda curr, _prev: self._show_token_fields(curr)
        )
        self.right_list.itemDoubleClicked.connect(self._insert_token)
        bottom_layout.addWidget(self.right_list, stretch=2)

        self._field_widgets: list[QWidget] = []
        fields_inner = QWidget()
        self.fields_layout = QVBoxLayout(fields_inner)
        self.fields_layout.setContentsMargins(0, 0, 0, 0)
        self.fields_layout.addStretch()

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(fields_inner)
        scroll_area.setMinimumWidth(150)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        bottom_layout.addWidget(scroll_area, stretch=3)

        right_layout.addWidget(bottom_widget)

        content_layout.addLayout(right_layout)

        self.main_layout.addLayout(content_layout)

        self.osc_client = osc_client

        self.setWindowTitle("OpenChatbox")
        self.resize(1000, 700)

        self.current_index = 0
        self._next_cycle_at = 0
        self._next_update_at = 0
        self._next_action = None
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_timer)

        self._sync_update_suffix()

        self._save_timer = QTimer()
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(500)
        self._save_timer.timeout.connect(self.save_chats)

        disabled_chats = self.config.get("disabled_chats", [])
        for i, text in enumerate(self.config.get("chats", [])):
            item = QListWidgetItem(text)
            enabled = not (i < len(disabled_chats) and disabled_chats[i])
            item.setData(Qt.ItemDataRole.UserRole, enabled)
            self.list.addItem(item)
            self.validate_item(item)

        if self.list.count() > 0:
            QTimer.singleShot(0, lambda: self.list.setCurrentRow(0))

        self.send_current()
        now = int(time.monotonic() * 1000)
        cycle_val = self.cycle_spin.value()
        update_val = self.update_spin.value()
        if cycle_val > 0:
            self._next_cycle_at = now + cycle_val * 1000
        if update_val > 0:
            self._next_update_at = now + update_val * 1000

    def _schedule_save(self):
        self._save_timer.start()

    def save_chats(self):
        self.config["chats"] = [self.list.item(i).text() for i in range(self.list.count())]
        self.config["disabled_chats"] = [
            not self.list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.list.count())
        ]
        save_config(self.config)
        logger.debug("Saved %d chats", self.list.count())

    def closeEvent(self, event):
        self._save_timer.stop()
        self.save_chats()
        self._send_thread.quit()
        self._resolve_thread.quit()
        self._update_thread.quit()
        self._send_thread.wait()
        self._resolve_thread.wait()
        self._update_thread.wait()
        if self.text_processor:
            for token in self.text_processor.tokens.values():
                stop = getattr(token, "stop", None)
                if callable(stop):
                    try:
                        stop(blocking=False)
                    except TypeError:
                        stop()
        from services import heartrate_service
        heartrate_service.shutdown()
        super().closeEvent(event)

    def click_add(self):
        item = QListWidgetItem("")
        item.setData(Qt.ItemDataRole.UserRole, True)
        self.list.addItem(item)
        self.list.setCurrentItem(item)
        self.edit_text.setFocus()
        self._schedule_save()

    def click_copy(self):
        current = self.list.currentItem()
        if not current:
            return
        item = QListWidgetItem(current.text())
        item.setData(Qt.ItemDataRole.UserRole, current.data(Qt.ItemDataRole.UserRole))
        self.list.insertItem(self.list.currentRow() + 1, item)
        self.validate_item(item)
        self.list.setCurrentItem(item)
        self._schedule_save()

    def click_remove(self):
        self.list.blockSignals(True)
        self.edit_text.blockSignals(True)
        for item in self.list.selectedItems():
            self.list.takeItem(self.list.row(item))
        self.edit_text.blockSignals(False)
        self.list.blockSignals(False)
        if self.list.currentItem():
            self.edit_text.setText(self.list.currentItem().text())
        else:
            self.edit_text.clear()
        self._schedule_save()

    def item_click(self):
        if self.list.currentItem():
            if self.list.currentItem().text() == "<Blank>":
                self.edit_text.setText("")
            else:
                self.edit_text.setText(self.list.currentItem().text())
            self.edit_text.setFocus()

    def text_edited(self):
        text = self.edit_text.toPlainText()
        if self.list.currentItem():
            if text == "":
                self.list.currentItem().setText("<Blank>")
            else:
                self.list.currentItem().setText(text)
        self.validate_text(text)
        self._schedule_save()

    def toggle_item_enabled(self, item):
        enabled = item.data(Qt.ItemDataRole.UserRole)
        item.setData(Qt.ItemDataRole.UserRole, not enabled)
        self.validate_item(item)
        self._schedule_save()
        if enabled and self.list.row(item) == self.current_index:
            self.cycle_next()

    def validate_text(self, text):
        self._resolve_text_requested.emit(text)

    def _on_text_resolved(self, resolved):
        resolved_len = len(resolved)
        visual_lines = count_visual_lines(resolved)
        self.charcount.setText(f"{resolved_len}/144 Characters")
        self.linecount.setText(f"{visual_lines}/9 Lines")
        if resolved_len > 144:
            self.charcount.setStyleSheet("color: red")
        else:
            self.charcount.setStyleSheet("")
        if visual_lines > 9:
            self.linecount.setStyleSheet("color: red")
        else:
            self.linecount.setStyleSheet("")
        if self.list.currentItem():
            self.validate_item(self.list.currentItem())

    def validate_item(self, item):
        if not item.data(Qt.ItemDataRole.UserRole):
            palette = self.palette()
            item.setForeground(palette.color(palette.ColorGroup.Disabled, palette.ColorRole.Text))
            return
        item.setForeground(QBrush())
        row = self.list.row(item)
        self._resolve_item_requested.emit(row, item.text())

    def _on_item_resolved(self, row, resolved):
        if row < 0 or row >= self.list.count():
            return
        item = self.list.item(row)
        if not item or not item.data(Qt.ItemDataRole.UserRole):
            return
        if len(resolved) > 144 or count_visual_lines(resolved) > 9:
            item.setForeground(QColor("red"))
        else:
            item.setForeground(QBrush())

    def _insert_token(self, item, _col=0):
        tag = item.data(0, Qt.ItemDataRole.UserRole)
        if not tag:
            return
        self.edit_text.insertPlainText(f"<{tag}>")
        self.edit_text.setFocus()

    def _make_field_widget(self, tag, field_def, token):
        """Create and connect a widget for a token field definition."""
        key = field_def.key
        value = token.fields.get(key, field_def.default)

        if field_def.field_type == "spinbox":
            sb = QSpinBox()
            sb.setMinimum(-1000000)
            sb.setMaximum(1000000)
            sb.setValue(int(value))
            sb.valueChanged.connect(
                lambda val, t=tag, k=key: self._on_field_edited(t, k, str(val))
            )
            return sb

        if field_def.field_type == "dropdown" and field_def.options:
            combo = QComboBox()
            combo.addItems(field_def.options)
            idx = combo.findText(value)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            combo.currentTextChanged.connect(
                lambda text, t=tag, k=key: (
                    self._on_field_edited(t, k, text),
                    self._show_token_fields(self.right_list.currentItem()),
                )
            )
            return combo

        le = QLineEdit(value)
        le.textChanged.connect(
            lambda text, t=tag, k=key: self._on_field_edited(t, k, text)
        )
        return le

    def _show_token_fields(self, item):
        for widget in self._field_widgets:
            if isinstance(widget, QTimer):
                widget.stop()
            widget.deleteLater()
        self._field_widgets.clear()

        if item is None or not self.text_processor:
            return

        tag = item.data(0, Qt.ItemDataRole.UserRole)
        if not tag:
            return
        token = self.text_processor.tokens.get(tag)
        if not token:
            return

        hint = getattr(token, "hint", None)
        if hint:
            hint_label = QLabel(hint)
            hint_label.setOpenExternalLinks(True)
            hint_label.setStyleSheet("color: gray; font-style: italic")
            hint_label.setWordWrap(True)
            self.fields_layout.insertWidget(0, hint_label)
            self._field_widgets.append(hint_label)

        if not token.field_defs:
            return

        visible_defs = [
            fd for fd in token.field_defs
            if not fd.visible_when or all(
                token.fields.get(k) == v for k, v in fd.visible_when.items()
            )
        ]

        insert_pos = 1 if hint else 0
        i = 0
        while i < len(visible_defs):
            field_def = visible_defs[i]

            # Grouped fields: render side-by-side in one row
            if field_def.group is not None:
                group_name = field_def.group
                group_fields = []
                while i < len(visible_defs) and visible_defs[i].group == group_name:
                    group_fields.append(visible_defs[i])
                    i += 1

                row_widget = QWidget()
                row_layout = QHBoxLayout(row_widget)
                row_layout.setContentsMargins(0, 0, 0, 0)
                row_layout.setSpacing(4)
                for gf in group_fields:
                    widget = self._make_field_widget(tag, gf, token)
                    if gf.field_type == "spinbox":
                        widget.setMinimum(0)
                    stretch = 1 if isinstance(widget, QLineEdit) else 0
                    row_layout.addWidget(widget, stretch=stretch)
                self.fields_layout.insertWidget(insert_pos, row_widget)
                self._field_widgets.append(row_widget)
                insert_pos += 1
                continue

            # -- Single field (existing logic) --
            i += 1

            label = QLabel(field_def.label)
            self.fields_layout.insertWidget(insert_pos, label)
            self._field_widgets.append(label)
            insert_pos += 1

            if field_def.field_type == "ble_scan":
                row_widget = QWidget()
                row_layout = QHBoxLayout(row_widget)
                row_layout.setContentsMargins(0, 0, 0, 0)
                row_layout.setSpacing(4)

                combo = QComboBox()
                combo.setEditable(True)
                current = token.fields.get(field_def.key, field_def.default)
                if current:
                    combo.addItem(current)
                    combo.setCurrentText(current)

                def on_ble_selected(index, c=combo, t=tag, k=field_def.key):
                    data = c.itemData(index)
                    self._on_field_edited(t, k, data if data else c.itemText(index))
                combo.currentIndexChanged.connect(on_ble_selected)
                combo.editTextChanged.connect(
                    lambda text, t=tag, k=field_def.key: self._on_field_edited(t, k, text)
                )
                row_layout.addWidget(combo, stretch=1)

                scan_btn = QToolButton()
                scan_btn.setText("↻")
                scan_btn.setToolTip("Scan for BLE devices")
                spinner_frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
                spin_state = {"idx": 0}

                def start_scan(_checked=None, _tok=token):
                    if _tok.scanning:
                        return
                    _tok.scan()
                scan_btn.clicked.connect(start_scan)
                row_layout.addWidget(scan_btn)

                self.fields_layout.insertWidget(insert_pos, row_widget)
                self._field_widgets.append(row_widget)

                # Status label that polls the token's status
                status_label = QLabel("")
                status_label.setStyleSheet("color: gray; font-style: italic")
                status_label.setWordWrap(True)
                insert_pos += 1
                self.fields_layout.insertWidget(insert_pos, status_label)
                self._field_widgets.append(status_label)

                # Single timer polls both scan results and connection status
                poll_timer = QTimer()
                poll_timer.setInterval(200)
                _prev_results = {"val": token.scan_results}
                def poll_token(_tok=token, _combo=combo, _btn=scan_btn,
                               _lbl=status_label, _sp=spin_state):
                    # Update spinner / button
                    if _tok.scanning:
                        _btn.setEnabled(False)
                        _btn.setText(spinner_frames[_sp["idx"] % len(spinner_frames)])
                        _sp["idx"] += 1
                    else:
                        _btn.setEnabled(True)
                        _btn.setText("↻")
                    # Update combo when new results arrive
                    results = _tok.scan_results
                    if results is not None and results is not _prev_results["val"]:
                        _prev_results["val"] = results
                        self._populate_ble_combo(_combo, results)
                    # Update status
                    _lbl.setText(getattr(_tok, "status", ""))
                poll_timer.timeout.connect(poll_token)
                poll_timer.start()
                self._field_widgets.append(poll_timer)
            else:
                widget = self._make_field_widget(tag, field_def, token)
                self.fields_layout.insertWidget(insert_pos, widget)
                self._field_widgets.append(widget)
            insert_pos += 1

    def _populate_ble_combo(self, combo, results):
        saved = combo.currentText()
        saved_data = combo.currentData()
        combo.clear()

        hr_devices = [r for r in results if r[3]]
        other_devices = [r for r in results if not r[3] and r[1]]

        if hr_devices:
            combo.addItem("-- Heart Rate --")
            idx = combo.count() - 1
            combo.model().item(idx).setEnabled(False)
            for address, name, rssi, _ in hr_devices:
                label = f"♥ {name or address} ({rssi} dBm)" if name else f"♥ {address} ({rssi} dBm)"
                combo.addItem(label, userData=address)

        if other_devices:
            combo.addItem("-- Other --")
            idx = combo.count() - 1
            combo.model().item(idx).setEnabled(False)
            for address, name, rssi, _ in other_devices:
                display = f"{name} ({rssi} dBm)" if name else f"{address} ({rssi} dBm)"
                combo.addItem(display, userData=address)

        if not hr_devices and not other_devices:
            combo.addItem("No devices found")

        restore = saved_data or saved
        if restore:
            idx = combo.findData(restore)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            else:
                combo.setEditText(saved)

    def _on_field_edited(self, tag, key, value):
        token = self.text_processor.tokens[tag]
        token.fields[key] = value
        if hasattr(token, "reconnect"):
            token.reconnect()

        if "tokens" not in self.config:
            self.config["tokens"] = {}
        if tag not in self.config["tokens"]:
            self.config["tokens"][tag] = {}
        self.config["tokens"][tag][key] = value
        self._schedule_save()

        self.validate_text(self.edit_text.toPlainText())

    def send_current(self):
        if self.list.count() == 0:
            return
        if self.current_index >= self.list.count():
            self.current_index = 0
        item = self.list.item(self.current_index)
        if not item.data(Qt.ItemDataRole.UserRole):
            return
        text = item.text()
        if text == "<Blank>":
            logger.debug("Skipped blank chat at index %d", self.current_index)
            return
        self._sending = True
        self._last_send_ms = int(time.monotonic() * 1000)
        self._send_requested.emit(text)

    def _on_send_complete(self):
        self._sending = False
        self._schedule_next()

    @Slot(str)
    def _on_update_available(self, latest_tag: str):
        latest = latest_tag.lstrip("v")
        if self.config.get("dismissed_update") == latest:
            return
        self.main_layout.insertWidget(0, UpdateBanner(latest, self.config))

    def _schedule_next(self):
        now = int(time.monotonic() * 1000)
        min_at = self._last_send_ms + 2000

        best = None
        cycle_val = self.cycle_spin.value()
        if cycle_val > 0 and self._next_cycle_at > 0:
            at = max(self._next_cycle_at, min_at)
            best = ('cycle', at)

        update_val = self.update_spin.value()
        if update_val > 0 and self._next_update_at > 0:
            if not (cycle_val > 0 and update_val >= cycle_val):
                at = max(self._next_update_at, min_at)
                if best is None or at < best[1]:
                    best = ('update', at)

        if best is None:
            return
        self._next_action = best[0]
        self._timer.start(max(0, best[1] - now))

    def _on_timer(self):
        if self._sending:
            self._timer.start(100)
            return
        now = int(time.monotonic() * 1000)
        if self._next_action == 'cycle':
            count = self.list.count()
            for _ in range(count):
                self.current_index = (self.current_index + 1) % count
                if self.list.item(self.current_index).data(Qt.ItemDataRole.UserRole):
                    self.send_current()
                    self._next_cycle_at = now + self.cycle_spin.value() * 1000
                    if self.update_spin.value() > 0:
                        self._next_update_at = now + self.update_spin.value() * 1000
                    return
        else:
            self.send_current()
            self._next_update_at = now + self.update_spin.value() * 1000

    def cycle_next(self):
        now = int(time.monotonic() * 1000)
        self._next_cycle_at = max(now, self._last_send_ms + 2000)
        self._schedule_next()

    def _on_cycle_changed(self, value):
        self._on_spin_changed(self.cycle_spin, "_prev_cycle", "cycle_interval", value)

    def _on_update_changed(self, value):
        self._on_spin_changed(self.update_spin, "_prev_update", "update_interval", value)

    def _on_spin_changed(self, spin, prev_attr, config_key, value):
        prev = getattr(self, prev_attr)
        if value == 1:
            spin.setValue(2 if prev == 0 else 0)
            return
        setattr(self, prev_attr, value)
        self._update_interval(config_key, value)

    def _update_interval(self, config_key, value):
        now = int(time.monotonic() * 1000)
        if config_key == "cycle_interval":
            self._next_cycle_at = now + value * 1000 if value > 0 else 0
        else:
            self._next_update_at = now + value * 1000 if value > 0 else 0
        self._schedule_next()
        self._sync_update_suffix()
        if "osc" not in self.config:
            self.config["osc"] = {}
        self.config["osc"][config_key] = value
        self._schedule_save()

    def _sync_update_suffix(self):
        cycle_val = self.cycle_spin.value()
        update_val = self.update_spin.value()
        if update_val > 0 and cycle_val > 0 and update_val >= cycle_val:
            self.update_spin.setSuffix("s (Disabled)")
        else:
            self.update_spin.setSuffix("s")
