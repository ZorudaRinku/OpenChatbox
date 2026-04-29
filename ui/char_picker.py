import unicodedata
from collections import Counter

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QComboBox,
    QListWidget,
    QListWidgetItem,
    QCheckBox,
    QPushButton,
    QLabel,
)

from ui.vrc_charset import vrc_supported_codepoints


# (lo, hi, group_name). First match wins, so list narrow specialty ranges before broad script ranges. Display order also drives dropdown order.
_BLOCKS: tuple[tuple[int, int, str], ...] = (
    (0x2500, 0x257F, "Borders & Lines"),
    (0x2580, 0x259F, "Borders & Lines"),
    (0x2600, 0x26FF, "Symbols & Decorations"),
    (0x2700, 0x27BF, "Symbols & Decorations"),
    (0x2190, 0x21FF, "Symbols & Decorations"),
    (0x27F0, 0x27FF, "Symbols & Decorations"),
    (0x2900, 0x297F, "Symbols & Decorations"),
    (0x25A0, 0x25FF, "Symbols & Decorations"),
    (0x2B00, 0x2BFF, "Symbols & Decorations"),
    (0x20A0, 0x20CF, "Symbols & Decorations"),
    (0x2200, 0x22FF, "Math"),
    (0x2A00, 0x2AFF, "Math"),
    (0x2010, 0x205F, "Punctuation"),
    (0x3000, 0x303F, "Punctuation"),
    # Emoji presentation blocks. System font handles rendering (color or B&W).
    (0x1F000, 0x1F02F, "Emoji"),  # Mahjong tiles
    (0x1F0A0, 0x1F0FF, "Emoji"),  # Playing cards
    (0x1F300, 0x1F5FF, "Emoji"),  # Misc Symbols & Pictographs
    (0x1F600, 0x1F64F, "Emoji"),  # Emoticons
    (0x1F680, 0x1F6FF, "Emoji"),  # Transport & Map
    (0x1F700, 0x1F77F, "Emoji"),  # Alchemical
    (0x1F900, 0x1F9FF, "Emoji"),  # Supplemental Symbols & Pictographs
    (0x1FA70, 0x1FAFF, "Emoji"),  # Symbols & Pictographs Extended-A
    # Logographic / CJK script blocks (incl. radicals, strokes, kana, hangul jamo, bopomofo, fullwidth forms, enclosed CJK).
    (0x1100, 0x11FF, "CJK & Hangul"),  # Hangul Jamo
    (0x2E80, 0x2EFF, "CJK & Hangul"),  # CJK Radicals Supplement
    (0x2F00, 0x2FDF, "CJK & Hangul"),  # Kangxi Radicals
    (0x2FF0, 0x2FFF, "CJK & Hangul"),  # Ideographic Description
    (0x3040, 0x309F, "CJK & Hangul"),  # Hiragana
    (0x30A0, 0x30FF, "CJK & Hangul"),  # Katakana
    (0x3100, 0x312F, "CJK & Hangul"),  # Bopomofo
    (0x3130, 0x318F, "CJK & Hangul"),  # Hangul Compatibility Jamo
    (0x3190, 0x319F, "CJK & Hangul"),  # Kanbun
    (0x31A0, 0x31BF, "CJK & Hangul"),  # Bopomofo Extended
    (0x31C0, 0x31EF, "CJK & Hangul"),  # CJK Strokes
    (0x31F0, 0x31FF, "CJK & Hangul"),  # Katakana Phonetic Extensions
    (0x3200, 0x32FF, "CJK & Hangul"),  # Enclosed CJK Letters & Months
    (0x3300, 0x33FF, "CJK & Hangul"),  # CJK Compatibility
    (0x3400, 0x4DBF, "CJK & Hangul"),  # CJK Unified Ideographs Extension A
    (0x4E00, 0x9FFF, "CJK & Hangul"),  # CJK Unified Ideographs
    (0xA960, 0xA97F, "CJK & Hangul"),  # Hangul Jamo Extended-A
    (0xAC00, 0xD7AF, "CJK & Hangul"),  # Hangul Syllables + Jamo Extended-B
    (0xF900, 0xFAFF, "CJK & Hangul"),  # CJK Compatibility Ideographs
    (0xFE30, 0xFE4F, "CJK & Hangul"),  # CJK Compatibility Forms
    (0xFF00, 0xFFEF, "CJK & Hangul"),  # Halfwidth & Fullwidth Forms
    # Alphabetic / abjad / abugida scripts share one bucket.
    (0x0370, 0x03FF, "Alphabetic Scripts"),  # Greek
    (0x0400, 0x04FF, "Alphabetic Scripts"),  # Cyrillic
    (0x0530, 0x058F, "Alphabetic Scripts"),  # Armenian
    (0x10A0, 0x10FF, "Alphabetic Scripts"),  # Georgian
    (0x0600, 0x06FF, "Alphabetic Scripts"),  # Arabic
    (0x0750, 0x077F, "Alphabetic Scripts"),  # Arabic Supplement
    (0x0900, 0x0D7F, "Alphabetic Scripts"),  # Indic block range
    (0x0E00, 0x0FFF, "Alphabetic Scripts"),  # Thai / Lao / Tibetan
)

# Display order in the dropdown
_GROUP_ORDER = (
    "Borders & Lines",
    "Symbols & Decorations",
    "Math",
    "Punctuation",
    "Emoji",
    "Alphabetic Scripts",
    "CJK & Hangul",
)


def _classify(cp: int, cat: str) -> str:
    for lo, hi, name in _BLOCKS:
        if lo <= cp <= hi:
            return name
    # General-category fallback for codepoints outside the named blocks above.
    if cat.startswith("P"):
        return "Punctuation"
    if cat.startswith("S"):
        return "Symbols & Decorations"
    return "Alphabetic Scripts"


class CharPickerDialog(QDialog):
    """Non-modal grid of every character VRChat's chatbox can render."""

    char_chosen = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Character Picker")
        self.setWindowFlag(Qt.WindowType.Tool, True)
        self.resize(640, 520)

        layout = QVBoxLayout(self)

        top_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search by character or Unicode name...")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._apply_filter)
        top_row.addWidget(self.search, stretch=1)

        self.category = QComboBox()
        top_row.addWidget(self.category)
        layout.addLayout(top_row)

        self.list = QListWidget()
        self.list.setViewMode(QListWidget.ViewMode.IconMode)
        self.list.setMovement(QListWidget.Movement.Static)
        self.list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list.setUniformItemSizes(True)
        self.list.setGridSize(QSize(32, 32))
        self.list.setIconSize(QSize(0, 0))
        self.list.setSpacing(0)
        self.list.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.list.setWordWrap(False)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        font = self.list.font()
        font.setPointSize(16)
        self.list.setFont(font)
        self.list.itemActivated.connect(self._on_item_chosen)
        self.list.itemClicked.connect(self._on_item_chosen)
        layout.addWidget(self.list, stretch=1)

        bottom_row = QHBoxLayout()
        self.copy_check = QCheckBox("Copy to clipboard instead of inserting")
        self.copy_check.setToolTip(
            "When checked, clicking a character copies it to the clipboard "
            "rather than inserting it at the cursor."
        )
        bottom_row.addWidget(self.copy_check)
        bottom_row.addStretch()
        self.status = QLabel("")
        self.status.setStyleSheet("color: gray; font-style: italic")
        bottom_row.addWidget(self.status)
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        bottom_row.addWidget(close)
        layout.addLayout(bottom_row)

        self._all_items: list[tuple[QListWidgetItem, str, str, str]] = []
        self._populate()
        self._build_category_dropdown()
        self._apply_filter()

    def _populate(self):
        self.list.setUpdatesEnabled(False)
        for cp in vrc_supported_codepoints():
            ch = chr(cp)
            cat = unicodedata.category(ch)
            if cat in ("Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp"):
                continue
            try:
                name = unicodedata.name(ch)
            except ValueError:
                continue
            group = _classify(cp, cat)
            item = QListWidgetItem(ch)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setToolTip(f"U+{cp:04X}  {name}")
            self.list.addItem(item)
            self._all_items.append((item, ch, name, group))
        self.list.setUpdatesEnabled(True)

    def _build_category_dropdown(self):
        counts = Counter(g for _, _, _, g in self._all_items)
        self.category.blockSignals(True)
        self.category.clear()
        self.category.addItem(f"All ({len(self._all_items)})", "all")
        for name in _GROUP_ORDER:
            if counts[name]:
                self.category.addItem(f"{name} ({counts[name]})", name)
        self.category.blockSignals(False)
        self.category.currentIndexChanged.connect(self._apply_filter)

    def _apply_filter(self):
        query = self.search.text().strip().upper()
        cat_filter = self.category.currentData()
        visible = 0
        for item, ch, name, group in self._all_items:
            ok = True
            if cat_filter and cat_filter != "all" and group != cat_filter:
                ok = False
            if ok and query:
                ok = (query in name) or (query == ch.upper())
            item.setHidden(not ok)
            if ok:
                visible += 1
        self.status.setText(f"{visible} shown")

    def _on_item_chosen(self, item):
        ch = item.text()
        if not ch:
            return
        if self.copy_check.isChecked():
            QGuiApplication.clipboard().setText(ch)
            self.status.setText(f"Copied {ch!r} to clipboard")
        else:
            self.char_chosen.emit(ch)
