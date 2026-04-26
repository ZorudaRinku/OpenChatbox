"""VRChat sign-in dialog with ToS warning + 2FA flow."""

from __future__ import annotations

import logging
import threading

from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from services.vrchat_service import persist_cookies

logger = logging.getLogger(__name__)


WARNING_HTML = (
    "<b>Warning:</b> VRChat's API is unofficial. Authenticating against it "
    "from a third-party tool technically violates VRChat's Terms of Service "
    "and carries a real risk of your account being banned. "
    "<b>You sign in at your own risk.</b>"
)


class _LoginRunner(QObject):
    """Runs the (blocking) VRChat auth calls on a worker thread."""

    success = Signal()
    twofa_required = Signal(list)
    failed = Signal(str)

    def login(self, svc, username, password):
        def task():
            from services.vrchat_service import TwoFactorRequired, VRChatAuthError
            try:
                svc.login(username, password)
                self.success.emit()
            except TwoFactorRequired as exc:
                self.twofa_required.emit(exc.methods or [])
            except VRChatAuthError as exc:
                self.failed.emit(str(exc) or "Login failed")
            except Exception as exc:
                logger.exception("VRChat login error")
                self.failed.emit(f"Error: {exc}")

        threading.Thread(target=task, daemon=True, name="VRChat-login").start()

    def verify_2fa(self, svc, code, method):
        def task():
            from services.vrchat_service import VRChatAuthError
            try:
                svc.verify_2fa(code, method)
                self.success.emit()
            except VRChatAuthError as exc:
                self.failed.emit(str(exc) or "2FA failed")
            except Exception as exc:
                logger.exception("VRChat 2FA error")
                self.failed.emit(f"Error: {exc}")

        threading.Thread(target=task, daemon=True, name="VRChat-2fa").start()


class VRChatLoginDialog(QDialog):
    def __init__(self, parent, service, config):
        super().__init__(parent)
        self.service = service
        self.config = config
        self._twofa_method = "totp"

        self.setWindowTitle("VRChat Sign In")
        self.setModal(True)
        self.setMinimumWidth(440)

        layout = QVBoxLayout(self)

        warning = QLabel(WARNING_HTML)
        warning.setWordWrap(True)
        warning.setTextFormat(Qt.TextFormat.RichText)
        warning.setStyleSheet(
            "color: #b94a48; padding: 10px; border: 1px solid #b94a48; "
            "border-radius: 4px; background-color: rgba(185, 74, 72, 0.08);"
        )
        layout.addWidget(warning)

        self.acknowledge = QCheckBox("I understand the risks and want to continue")
        layout.addWidget(self.acknowledge)
        self.acknowledge.toggled.connect(self._update_submit_enabled)

        layout.addSpacing(8)

        layout.addWidget(QLabel("Username or email:"))
        self.username = QLineEdit()
        layout.addWidget(self.username)

        layout.addWidget(QLabel("Password:"))
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.password)

        self.twofa_label = QLabel("2FA code:")
        self.twofa_label.setVisible(False)
        layout.addWidget(self.twofa_label)
        self.twofa_code = QLineEdit()
        self.twofa_code.setVisible(False)
        layout.addWidget(self.twofa_code)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #b94a48")
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)

        button_row = QHBoxLayout()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(self.cancel_btn)
        button_row.addStretch()
        self.submit_btn = QPushButton("Sign In")
        self.submit_btn.setDefault(True)
        self.submit_btn.setEnabled(False)
        self.submit_btn.clicked.connect(self._on_submit)
        button_row.addWidget(self.submit_btn)
        layout.addLayout(button_row)

        # Worker (parented so it lives in our thread/event scope)
        self._runner = _LoginRunner(self)
        self._runner.success.connect(self._on_success)
        self._runner.twofa_required.connect(self._on_twofa_required)
        self._runner.failed.connect(self._on_failed)

    def _update_submit_enabled(self, *_):
        self.submit_btn.setEnabled(self.acknowledge.isChecked())

    @Slot()
    def _on_submit(self):
        self.error_label.setText("")
        self.submit_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        if self.twofa_code.isVisible():
            code = self.twofa_code.text().strip()
            if not code:
                self.error_label.setText("Enter your 2FA code.")
                self._reset_buttons()
                return
            self.submit_btn.setText("Verifying...")
            self._runner.verify_2fa(self.service, code, self._twofa_method)
            return

        username = self.username.text().strip()
        password = self.password.text()
        if not username or not password:
            self.error_label.setText("Enter username and password.")
            self._reset_buttons()
            return
        self.submit_btn.setText("Signing in...")
        self._runner.login(self.service, username, password)

    def _reset_buttons(self):
        self.cancel_btn.setEnabled(True)
        self.submit_btn.setEnabled(self.acknowledge.isChecked())
        self.submit_btn.setText("Verify" if self.twofa_code.isVisible() else "Sign In")

    @Slot()
    def _on_success(self):
        persist_cookies(self.service, self.config)
        self.service.start_polling()
        self.service.request_refresh()
        self.accept()

    @Slot(list)
    def _on_twofa_required(self, methods):
        # Priority: totp (authenticator app) > emailOtp > otp (recovery only).
        # VRChat returns ["totp", "otp"] for accounts with an authenticator;
        # both endpoints are valid but only totp accepts the rolling 6-digit
        # code from the user's app.
        if "totp" in methods:
            self._twofa_method = "totp"
            self.twofa_label.setText("Authenticator code:")
        elif "emailOtp" in methods:
            self._twofa_method = "emailotp"
            self.twofa_label.setText("Email 2FA code:")
        elif "otp" in methods:
            self._twofa_method = "otp"
            self.twofa_label.setText("Recovery code:")
        else:
            self._twofa_method = "totp"
            self.twofa_label.setText("Authenticator code:")
        self.twofa_label.setVisible(True)
        self.twofa_code.setVisible(True)
        self.username.setEnabled(False)
        self.password.setEnabled(False)
        self.submit_btn.setText("Verify")
        self.cancel_btn.setEnabled(True)
        self.submit_btn.setEnabled(self.acknowledge.isChecked())
        self.twofa_code.setFocus()
        QApplication.processEvents()

    @Slot(str)
    def _on_failed(self, message: str):
        self.error_label.setText(message)
        self._reset_buttons()
