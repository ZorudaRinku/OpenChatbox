from ui.restore_dialog import RestoreBackupDialog


def _make_backups(tmp_path):
    old = tmp_path / "config-2026-07-01_10-00-00.toml"
    new = tmp_path / "config-2026-07-02_11-00-00.toml"
    old.write_text('chats = ["old"]\n')
    new.write_text('chats = ["now"]\n')
    return new, old


class TestCurrentIndicator:
    def test_marks_backup_matching_current_data(self, qtbot, tmp_path):
        new, old = _make_backups(tmp_path)
        dlg = RestoreBackupDialog(
            [new, old], startup=False, current_data=new.read_bytes()
        )
        qtbot.addWidget(dlg)

        assert dlg.list.item(0).text().endswith("- current")
        assert dlg.list.item(0).font().bold()
        assert "- current" not in dlg.list.item(1).text()
        assert not dlg.list.item(1).font().bold()

    def test_no_marker_without_current_data(self, qtbot, tmp_path):
        new, old = _make_backups(tmp_path)
        dlg = RestoreBackupDialog([new, old])
        qtbot.addWidget(dlg)

        for i in range(dlg.list.count()):
            assert "- current" not in dlg.list.item(i).text()

    def test_unreadable_backup_not_marked(self, qtbot, tmp_path):
        new, old = _make_backups(tmp_path)
        data = new.read_bytes()
        new.unlink()
        dlg = RestoreBackupDialog([old], startup=False, current_data=data)
        qtbot.addWidget(dlg)

        assert "- current" not in dlg.list.item(0).text()
