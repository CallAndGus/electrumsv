# The Open BSV license.
#
# Copyright © 2020 Bitcoin Association
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the “Software”), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
#   1. The above copyright notice and this permission notice shall be included
#      in all copies or substantial portions of the Software.
#   2. The Software, and any software that is derived from the Software or parts
#      thereof, can only be used on the Bitcoin SV blockchains. The Bitcoin SV
#      blockchains are defined, for purposes of this license, as the Bitcoin
#      blockchain containing block height #556767 with the hash
#      “000000000000000001d956714215d96ffc00e0afda4cd0a96c96f8d802b1662b” and
#      the test blockchains that are supported by the unmodified Software.
#
# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from typing import Optional

from bitcoinx import bip32_key_from_string, BIP32PublicKey

from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QCursor, QPainter
from PyQt5.QtWidgets import (QAbstractItemView, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QPlainTextEdit, QSizePolicy, QStyle, QStyleOption, QToolButton, QVBoxLayout,
    QWizard)

from electrumsv.constants import KeystoreTextType
from electrumsv.i18n import _
from electrumsv.keystore import instantiate_keystore_from_text, KeyStore

from .main_window import ElectrumWindow
from .util import FormSectionWidget, read_QIcon
from .wizard_common import WizardFlags


class CosignerState:
    keystore: Optional[KeyStore] = None
    is_local = False

    def __init__(self, cosigner_index: int) -> None:
        self.cosigner_index = cosigner_index

    def reset(self) -> None:
        self.keystore = None
        self.is_local = False

    def is_complete(self) -> bool:
        return self.keystore is not None


class CosignerCard(FormSectionWidget):
    minimum_label_width = 60

    cosigner_updated = pyqtSignal(int)

    def __init__(self, main_window: ElectrumWindow, state: CosignerState) -> None:
        super().__init__()

        self._main_window = main_window
        self._state = state

        self.setObjectName("CosignerCard")

        title_text = _("Cosigner #{}").format(state.cosigner_index+1)
        self.add_title(title_text)

        cosigner_name_edit = QLineEdit()
        cosigner_name_edit.setPlaceholderText(_("A name or label for this cosigner (optional)."))
        cosigner_name_edit.setContentsMargins(0, 0, 0, 0)

        self._key_icon = read_QIcon('icons8-key.svg')
        self._delete_icon = read_QIcon('icons8-delete.svg')
        self._copy_icon = read_QIcon('icons8-copy-to-clipboard-32.png')

        cosigner_key_button = QToolButton()
        cosigner_key_button.setIcon(self._key_icon)
        cosigner_key_button.clicked.connect(self._event_click_set_cosigner_key)
        cosigner_key_button.setCursor(QCursor(Qt.PointingHandCursor))
        cosigner_key_button.setContentsMargins(0, 0, 0, 0)
        self._cosigner_key_button = cosigner_key_button

        copy_button = QToolButton()
        copy_button.setIcon(self._copy_icon)
        copy_button.clicked.connect(self._event_click_copy_key)
        copy_button.setCursor(QCursor(Qt.PointingHandCursor))
        copy_button.setContentsMargins(0, 0, 0, 0)
        copy_button.setVisible(False)

        key_edit = QPlainTextEdit()
        key_edit.setPlaceholderText(_("Paste any extended public key for this cosigner here, or "
            "use the key button for other options."))
        key_edit.setMaximumHeight(40)
        key_edit.setTabChangesFocus(True)
        key_edit.textChanged.connect(self._event_text_changed)
        key_edit.setContentsMargins(0, 0, 0, 0)
        self._key_edit = key_edit

        button_vbox = QVBoxLayout()
        button_vbox.addWidget(cosigner_key_button, 0, Qt.AlignTop)
        button_vbox.addWidget(copy_button, 0, Qt.AlignTop)
        button_vbox.addStretch(1)

        key_hbox = QHBoxLayout()
        key_hbox.setContentsMargins(0, 0, 0, 0)
        key_hbox.setSpacing(3)
        key_hbox.addWidget(key_edit, 1, Qt.AlignTop)
        key_hbox.addLayout(button_vbox)

        signed_by_label = QLabel()
        signed_by_label.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
        self._signed_by_label = signed_by_label

        self.add_row(_("Name"), cosigner_name_edit, True)
        self.add_row(_("Key"), key_hbox, True)
        self.add_row(_("Signed by"), signed_by_label)

        self._update_keystore(None)

    def _event_click_set_cosigner_key(self) -> None:
        if self._state.keystore is not None:
            self._update_keystore(None)
            return

        from .account_wizard import AccountWizard
        child_wizard = AccountWizard(self._main_window, WizardFlags.MULTISIG_MODE, self)
        subtitle_text = _("Cosigner #{} Key Selection").format(self._state.cosigner_index+1)
        child_wizard.set_subtitle(subtitle_text)
        if child_wizard.run() == QWizard.Accepted:
            assert child_wizard.has_result(), "accepted result-less wizard"
            self._update_keystore(child_wizard.get_keystore())
        else:
            self._update_keystore(None)

    def _event_click_copy_key(self) -> None:
        pass

    def _event_text_changed(self) -> None:
        if self._key_edit.isReadOnly():
            return

        text = self._key_edit.toPlainText()
        try:
            key = bip32_key_from_string(text)
        except ValueError:
            return
        else:
            if not isinstance(key, BIP32PublicKey):
                return

        password = None
        keystore = instantiate_keystore_from_text(KeystoreTextType.EXTENDED_PUBLIC_KEY,
            text, password)
        self._update_keystore(keystore)

    def _update_keystore(self, keystore: Optional[KeyStore]) -> None:
        if keystore is None:
            self._state.reset()
            self._key_edit.setReadOnly(False)
            self._key_edit.clear()
            self._cosigner_key_button.setIcon(self._key_icon)
            self._cosigner_key_button.setToolTip(_("Set the current key for this cosigner"))
        else:
            self._state.keystore = keystore
            # The stringification of the key will ensure it displays correctly.
            self._key_edit.setReadOnly(True)
            self._key_edit.clear()
            self._key_edit.appendPlainText(keystore.get_master_public_key())
            self._cosigner_key_button.setIcon(self._delete_icon)
            self._cosigner_key_button.setToolTip(_("Clear the current key for this cosigner"))

        self._update_status_label()
        self.cosigner_updated.emit(self._state.cosigner_index)

    def _update_status_label(self) -> None:
        if self._state.is_complete():
            if self._state.keystore.is_watching_only():
                self._signed_by_label.setText(_("External party") +".")
            else:
                self._signed_by_label.setText(_("This account") +".")
            self._signed_by_label.setStyleSheet("")
        else:
            self._signed_by_label.setText(_("Not yet specified") +".")
            self._signed_by_label.setStyleSheet("QLabel { color: red; }")

    # QWidget styles do not render. Found this somewhere on the qt5 doc site.
    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, p, self)


class CosignerList(QListWidget):
    def __init__(self, main_window: ElectrumWindow) -> None:
        self._main_window = main_window

        super().__init__()

        self.setSortingEnabled(False)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)

    def add_state(self, state: CosignerState) -> CosignerCard:
        card = CosignerCard(self._main_window, state)
        list_item = QListWidgetItem()
        # The item won't display unless it gets a size hint. It seems to resize horizontally
        # but unless the height is a minimal amount it won't do anything proactive..
        list_item.setSizeHint(card.sizeHint())
        self.addItem(list_item)
        self.setItemWidget(list_item, card)
        return card
