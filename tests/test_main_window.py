import pytest
from unittest.mock import patch
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLineEdit, QSpinBox
from services.text_processor import FieldDef, init_fields
from ui.main_window import MainWindow


class TextFieldToken:
    tag = "texttok"
    field_defs = [FieldDef("name", "Name", "")]
    fields: dict[str, str]

    def resolve(self) -> str:
        return self.fields["name"]


class SpinFieldToken:
    tag = "spintok"
    field_defs = [FieldDef("n", "N", "5", field_type="spinbox")]
    fields: dict[str, str]

    def resolve(self) -> str:
        return self.fields["n"]


class GroupedFieldToken:
    tag = "grouptok"
    field_defs = [
        FieldDef("a", "A", "", group=1),
        FieldDef("b", "B", "", group=1),
    ]
    fields: dict[str, str]

    def resolve(self) -> str:
        return self.fields["a"] + self.fields["b"]


def _find_token_item(tree, tag):
    for i in range(tree.topLevelItemCount()):
        group = tree.topLevelItem(i)
        for j in range(group.childCount()):
            child = group.child(j)
            if child.data(0, Qt.ItemDataRole.UserRole) == tag:
                return child
    return None


@pytest.fixture(autouse=True)
def _no_real_config_writes():
    with patch("ui.main_window.save_config"):
        yield


@pytest.fixture
def window(qtbot, mock_osc_client, sample_config, text_processor):
    win = MainWindow(mock_osc_client, sample_config, text_processor=text_processor)
    qtbot.addWidget(win)
    yield win
    win.close()


@pytest.fixture
def rich_window(qtbot, mock_osc_client, sample_config, text_processor):
    for token in (TextFieldToken(), SpinFieldToken(), GroupedFieldToken()):
        init_fields(token)
        text_processor.register(token)
    win = MainWindow(mock_osc_client, sample_config, text_processor=text_processor)
    qtbot.addWidget(win)
    yield win
    win.close()


class TestMainWindow:
    def test_initial_chat_list(self, window):
        assert window.list.count() == 2
        assert window.list.item(0).text() == "Hello world"
        assert window.list.item(1).text() == "<time>"

    def test_add_item(self, window, qtbot):
        initial = window.list.count()
        window.click_add()
        assert window.list.count() == initial + 1

    def test_remove_item(self, window, qtbot):
        window.list.setCurrentRow(0)
        window.click_remove()
        assert window.list.count() == 1

    def test_text_edit_syncs_to_list(self, window, qtbot):
        window.list.setCurrentRow(0)
        window.edit_text.setText("updated")
        assert window.list.item(0).text() == "updated"

    def test_blank_text_shows_placeholder(self, window, qtbot):
        window.list.setCurrentRow(0)
        window.edit_text.setText("")
        assert window.list.item(0).text() == "<Blank>"

    def test_item_click_loads_text(self, window, qtbot):
        window.list.setCurrentRow(1)
        assert window.edit_text.toPlainText() == "<time>"

    def test_item_click_blank_loads_empty(self, window, qtbot):
        window.click_add()
        last_row = window.list.count() - 1
        window.list.setCurrentRow(last_row)
        window.edit_text.setText("")
        # Now click it again
        window.list.setCurrentRow(0)
        window.list.setCurrentRow(last_row)
        assert window.edit_text.toPlainText() == ""

    @patch("ui.main_window.save_config")
    def test_save_chats(self, mock_save, window):
        window.save_chats()
        mock_save.assert_called_once()
        saved = mock_save.call_args[0][0]
        assert saved["chats"] == ["Hello world", "<time>"]

    def test_cycle_next_advances(self, window, mock_osc_client):
        window.current_index = 0
        window._sending = False
        window._next_action = "cycle"
        window._on_timer()
        assert window.current_index == 1

    def test_cycle_next_wraps_around(self, window, mock_osc_client):
        window.current_index = window.list.count() - 1
        window._sending = False
        window._next_action = "cycle"
        window._on_timer()
        assert window.current_index == 0

    def test_toggle_disables_chat(self, window):
        item = window.list.item(0)
        assert item.data(Qt.ItemDataRole.UserRole) is True
        window.toggle_item_enabled(item)
        assert item.data(Qt.ItemDataRole.UserRole) is False

    def test_toggle_re_enables_chat(self, window):
        item = window.list.item(0)
        item.setData(Qt.ItemDataRole.UserRole, False)
        window.toggle_item_enabled(item)
        assert item.data(Qt.ItemDataRole.UserRole) is True

    def test_cycle_skips_disabled_chat(self, window, mock_osc_client):
        window.click_add()
        assert window.list.count() == 3
        window.list.item(1).setData(Qt.ItemDataRole.UserRole, False)
        window.current_index = 0
        window._sending = False
        window._next_action = "cycle"
        window._on_timer()
        assert window.current_index == 2

    def test_disabling_current_chat_triggers_immediate_cycle(self, window):
        window.current_index = 0
        with patch.object(window, "cycle_next") as mock_cycle:
            window.toggle_item_enabled(window.list.item(0))
            mock_cycle.assert_called_once()

    def test_disabling_non_current_chat_does_not_cycle(self, window):
        window.current_index = 0
        with patch.object(window, "cycle_next") as mock_cycle:
            window.toggle_item_enabled(window.list.item(1))
            mock_cycle.assert_not_called()

    def test_send_current_empty_list(self, window, mock_osc_client):
        while window.list.count():
            window.list.takeItem(0)
        mock_osc_client.send_message.reset_mock()
        window.send_current()
        mock_osc_client.send_message.assert_not_called()

    def test_startup_with_first_chat_disabled_starts_cycle(
        self, qtbot, mock_osc_client, text_processor
    ):
        config = {
            "osc": {"ip": "127.0.0.1", "port": 9000},
            "chats": ["Hello world", "<time>"],
            "disabled_chats": [True, False],
            "tokens": {},
        }
        win = MainWindow(mock_osc_client, config, text_processor=text_processor)
        qtbot.addWidget(win)
        try:
            assert win._timer.isActive()
        finally:
            win.close()

    def test_char_count_label_updates(self, window, qtbot):
        window.list.setCurrentRow(0)
        window.edit_text.setText("abc")
        qtbot.waitUntil(lambda: "3/144" in window.charcount.text(), timeout=1000)

    def test_char_count_over_limit_red(self, window, qtbot):
        window.list.setCurrentRow(0)
        window.edit_text.setText("x" * 145)
        qtbot.waitUntil(lambda: "red" in window.charcount.styleSheet(), timeout=1000)

    def test_token_list_populated(self, window):
        """Right-side tree should contain registered token tags as leaf items."""
        tree = window.right_list
        tags = []
        for i in range(tree.topLevelItemCount()):
            group = tree.topLevelItem(i)
            for j in range(group.childCount()):
                tags.append(group.child(j).text(0))
        assert "<dummy>" in tags

    def test_double_click_token_inserts_placeholder(self, rich_window):
        rich_window.edit_text.setPlainText("")
        item = _find_token_item(rich_window.right_list, "texttok")
        rich_window._insert_token(item)
        assert "<texttok>" in rich_window.edit_text.toPlainText()

    def test_click_token_shows_text_field(self, rich_window):
        item = _find_token_item(rich_window.right_list, "texttok")
        rich_window._show_token_fields(item)
        assert any(isinstance(w, QLineEdit) for w in rich_window._field_widgets)

    def test_click_token_shows_spinbox(self, rich_window):
        item = _find_token_item(rich_window.right_list, "spintok")
        rich_window._show_token_fields(item)
        assert any(isinstance(w, QSpinBox) for w in rich_window._field_widgets)

    def test_click_token_shows_grouped_fields(self, rich_window):
        item = _find_token_item(rich_window.right_list, "grouptok")
        rich_window._show_token_fields(item)
        grouped_rows = [
            w for w in rich_window._field_widgets
            if len(w.findChildren(QLineEdit)) == 2
        ]
        assert grouped_rows, "grouped fields should render as one row with 2 line edits"
