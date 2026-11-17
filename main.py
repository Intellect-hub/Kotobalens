import sys

import html

import keyboard

import mss

from PySide6.QtCore import (

    QObject,

    Signal,

    QThread,

    QTimer,

    QSettings,

    Qt,

)

from PySide6.QtGui import QFont, QIcon, QPixmap, QPainter, QColor, QAction

from PySide6.QtWidgets import (

    QApplication,

    QWidget,

    QSystemTrayIcon,

    QMenu,

    QVBoxLayout,

    QHBoxLayout,

    QLabel,

    QTextEdit,

    QTextBrowser,

    QPushButton,

    QScrollArea,

    QComboBox,

    QFrame,

    QTabWidget,

    QTableWidget,

    QTableWidgetItem,

    QHeaderView,

    QAbstractItemView,

    QLineEdit,

    QCheckBox,

    QFileDialog,

    QMessageBox,

)

from overlay import SelectionOverlay

from ocr import recognize_japanese

from tokenizer import split_japanese

from dictionary import load_dictionary, lookup_word

from ai_helper import translate_sentence, explain_word

from anki_helper import save_word, save_sentence

from database import (

    initialize_database,

    save_sentence as save_history_sentence,

    save_vocabulary as save_history_vocabulary,

    get_sentences,

    get_vocabulary,

    delete_vocabulary_by_ids,

    clear_all_history,

)

SHORTCUTS = {

    "Alt + Shift + Z": "alt+shift+z",

    "Ctrl + Shift + S": "ctrl+shift+s",

    "Ctrl + Alt + J": "ctrl+alt+j",

    "Ctrl + Shift + J": "ctrl+shift+j",

    "F8": "f8",

    "F9": "f9",

}

class HotkeyHandler(QObject):

    activated = Signal()

class OCRWorker(QThread):

    finished_text = Signal(str)

    failed = Signal(str)

    def __init__(self, image_path):

        super().__init__()

        self.image_path = image_path

    def run(self):

        try:

            result = recognize_japanese(

                self.image_path

            )

            self.finished_text.emit(result)

        except Exception as error:

            self.failed.emit(str(error))

class TranslationWorker(QThread):

    translated = Signal(str, str)

    failed = Signal(str, str)

    def __init__(self, japanese_text):

        super().__init__()

        self.japanese_text = japanese_text

    def run(self):

        try:

            result = translate_sentence(

                self.japanese_text

            )

            self.translated.emit(

                self.japanese_text,

                result,

            )

        except Exception as error:

            self.failed.emit(

                self.japanese_text,

                str(error),

            )

class ExplanationWorker(QThread):

    explained = Signal(int, str)

    failed = Signal(int, str)

    def __init__(

        self,

        request_id,

        sentence,

        word,

    ):

        super().__init__()

        self.request_id = request_id

        self.sentence = sentence

        self.word = word

    def run(self):

        try:

            result = explain_word(

                self.sentence,

                self.word["word"],

                self.word["reading"],

                self.word["dictionary_form"],

            )

            self.explained.emit(

                self.request_id,

                result,

            )

        except Exception as error:

            self.failed.emit(

                self.request_id,

                str(error),

            )

class DictionaryWorker(QThread):

    loaded = Signal()

    failed = Signal(str)

    def run(self):

        try:

            load_dictionary()

            self.loaded.emit()

        except Exception as error:

            self.failed.emit(str(error))

class AnkiWorker(QThread):

    saved = Signal(str)

    failed = Signal(str)

    def __init__(self, mode, data):

        super().__init__()

        self.mode = mode

        self.data = data

    def run(self):

        try:

            if self.mode == "word":

                save_word(**self.data)

                self.saved.emit(

                    "Word saved to Anki!"

                )

            else:

                save_sentence(**self.data)

                self.saved.emit(

                    "Sentence saved to Anki!"

                )

        except Exception as error:

            self.failed.emit(str(error))

class AutoGrowingTextEdit(QTextEdit):

    """Grow with wrapped text up to three visible lines."""

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.document().contentsChanged.connect(self.update_height)

        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    def resizeEvent(self, event):

        super().resizeEvent(event)

        self.update_height()

    def update_height(self):

        line_height = self.fontMetrics().lineSpacing()

        padding = 22

        maximum = 3 * line_height + padding

        minimum = line_height + padding

        content = int(self.document().documentLayout().documentSize().height()) + 12

        target = max(minimum, min(maximum, content))

        if self.height() != target:

            self.setFixedHeight(target)

class AutoGrowingTextBrowser(QTextBrowser):

    """Show up to three wrapped HTML lines before scrolling."""

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.document().contentsChanged.connect(self.update_height)

        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    def resizeEvent(self, event):

        super().resizeEvent(event)

        self.update_height()

    def update_height(self):

        # Word links use 20px text with 1.5 line height.

        line_height = 30

        padding = 22

        maximum = 3 * line_height + padding

        minimum = line_height + padding

        content = int(self.document().documentLayout().documentSize().height()) + 12

        target = max(minimum, min(maximum, content))

        if self.height() != target:

            self.setFixedHeight(target)

class HistoryWindow(QWidget):

    """Search and selectively export saved sentences and vocabulary."""

    def __init__(self):

        super().__init__()

        self.setWindowTitle("Japanese Subtitle Helper — History")

        self.resize(900, 520)

        self.setMinimumSize(580, 320)

        self.setStyleSheet("""

            QWidget { background-color: #191b20; color: #edf0f5;

                      font-family: 'Segoe UI'; font-size: 13px; }

            QTableWidget { background-color: #252831; color: #f4f5f8;

                           gridline-color: #393e49;

                           alternate-background-color: #2c303a; }

            QHeaderView::section { background-color: #303744;

                                   color: #edf0f5; padding: 7px;

                                   border: 1px solid #465061; }

            QTabWidget::pane { border: 1px solid #393e49; }

            QTabBar::tab { background: #303744; padding: 9px 18px; }

            QTabBar::tab:selected { background: #245a85; }

            QPushButton { background-color: #303744; color: #edf0f5;

                          border: 1px solid #465061; border-radius: 7px;

                          padding: 8px 14px; }

            QPushButton:hover { background-color: #3c485a; }

            QLineEdit { background-color: #252831; color: #f4f5f8;

                        border: 1px solid #465061; border-radius: 7px;

                        padding: 9px; }

        """)

        layout = QVBoxLayout(self)

        self.search_box = QLineEdit()

        self.search_box.setPlaceholderText(

            "Search sentences, translations, words, readings, or meanings..."

        )

        self.search_box.setClearButtonEnabled(True)

        self.search_box.textChanged.connect(self.filter_history)

        layout.addWidget(self.search_box)

        self.tabs = QTabWidget()

        layout.addWidget(self.tabs)

        self.sentence_table = self.make_table(

            ["Captured at", "Japanese", "English"]

        )

        self.vocabulary_table = self.make_table(

            ["Select", "Word", "Reading", "Dictionary form", "Meaning", "Times seen"]

        )

        self.vocabulary_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)

        self.vocabulary_table.horizontalHeader().setSectionResizeMode(

            0, QHeaderView.ResizeMode.Fixed

        )

        self.vocabulary_table.setColumnWidth(0, 65)

        self.vocabulary_table.itemChanged.connect(self.vocabulary_checkbox_changed)

        self.checked_vocabulary_ids = set()

        self._filling_vocabulary = False

        self.tabs.addTab(self.sentence_table, "Sentences")

        self.tabs.addTab(self.vocabulary_table, "Vocabulary")

        self.selection_controls_widget = QWidget()

        selection_controls = QHBoxLayout(self.selection_controls_widget)

        selection_controls.setContentsMargins(0, 0, 0, 0)

        self.select_all_checkbox = QCheckBox("Select all visible words")

        self.select_all_checkbox.stateChanged.connect(self.toggle_all_visible_vocabulary)

        selection_controls.addWidget(self.select_all_checkbox)

        self.selected_count_label = QLabel("0 words selected")

        selection_controls.addWidget(self.selected_count_label)

        selection_controls.addStretch()

        layout.addWidget(self.selection_controls_widget)

        self.export_controls_widget = QWidget()

        export_controls = QHBoxLayout(self.export_controls_widget)

        export_controls.setContentsMargins(0, 0, 0, 0)

        export_controls.addWidget(QLabel("Export vocabulary:"))

        self.export_scope = QComboBox()

        self.export_scope.addItem("Selected rows", "selected")

        self.export_scope.addItem("Current search results", "filtered")

        self.export_scope.addItem("All entries", "all")

        export_controls.addWidget(self.export_scope)

        export_button = QPushButton("Export Vocabulary CSV")

        export_button.clicked.connect(self.export_history)

        export_controls.addWidget(export_button)

        layout.addWidget(self.export_controls_widget)

        delete_controls = QHBoxLayout()

        delete_controls.addStretch()

        self.delete_button = QPushButton("Delete Selected Vocabulary")

        self.delete_button.clicked.connect(self.delete_selected_vocabulary)

        delete_controls.addWidget(self.delete_button)

        self.clear_all_button = QPushButton("Clear All History")

        self.clear_all_button.clicked.connect(self.clear_history)

        delete_controls.addWidget(self.clear_all_button)

        layout.addLayout(delete_controls)

        self.tabs.currentChanged.connect(self.update_history_buttons)

        self.update_history_buttons()

        bottom = QHBoxLayout()

        self.status = QLabel("")

        bottom.addWidget(self.status)

        bottom.addStretch()

        refresh_button = QPushButton("Refresh")

        refresh_button.clicked.connect(self.refresh_history)

        bottom.addWidget(refresh_button)

        close_button = QPushButton("Close")

        close_button.clicked.connect(self.close)

        bottom.addWidget(close_button)

        layout.addLayout(bottom)

    @staticmethod

    def make_table(headers):

        table = QTableWidget(0, len(headers))

        table.setHorizontalHeaderLabels(headers)

        table.setAlternatingRowColors(True)

        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

        table.setWordWrap(True)

        table.verticalHeader().setVisible(False)

        table.horizontalHeader().setSectionResizeMode(

            QHeaderView.ResizeMode.Stretch

        )

        return table

    @staticmethod

    def fill_table(table, rows, fields):

        table.setRowCount(len(rows))

        for row_number, record in enumerate(rows):

            for column, field in enumerate(fields):

                value = record[field]

                item = QTableWidgetItem("" if value is None else str(value))

                table.setItem(row_number, column, item)

        table.resizeRowsToContents()

    def refresh_history(self):

        try:

            self.sentences = get_sentences()

            self.vocabulary = get_vocabulary()

            current_ids = {record["id"] for record in self.vocabulary}

            self.checked_vocabulary_ids.intersection_update(current_ids)

            self.filter_history()

        except Exception as error:

            self.status.setText(f"Could not load history: {error}")

    def filter_history(self, _text=None):

        query = self.search_box.text().strip().casefold()

        def matches(record, fields):

            return any(

                query in str(record[field] or "").casefold()

                for field in fields

            )

        sentence_fields = ["captured_at", "japanese", "english"]

        vocabulary_fields = [

            "word", "reading", "dictionary_form", "meaning", "times_seen"

        ]

        sentences = [

            record for record in getattr(self, "sentences", [])

            if matches(record, sentence_fields)

        ]

        vocabulary = [

            record for record in getattr(self, "vocabulary", [])

            if matches(record, vocabulary_fields)

        ]

        self.filtered_sentences = sentences

        self.filtered_vocabulary = vocabulary

        self.fill_table(self.sentence_table, sentences, sentence_fields)

        self.fill_vocabulary_checkboxes(vocabulary, vocabulary_fields)

        self.status.setText(

            f"{len(sentences)} sentences · {len(vocabulary)} vocabulary words"

        )

    def fill_vocabulary_checkboxes(self, records, fields):

        """Rebuild visible vocabulary rows without losing checked IDs on search."""

        self._filling_vocabulary = True

        self.vocabulary_table.blockSignals(True)

        try:

            self.vocabulary_table.setRowCount(len(records))

            for row_number, record in enumerate(records):

                checkbox_item = QTableWidgetItem()

                checkbox_item.setFlags(

                    Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable

                )

                checkbox_item.setCheckState(

                    Qt.CheckState.Checked if record["id"] in self.checked_vocabulary_ids

                    else Qt.CheckState.Unchecked

                )

                self.vocabulary_table.setItem(row_number, 0, checkbox_item)

                for column, field in enumerate(fields, start=1):

                    value = record[field]

                    item = QTableWidgetItem("" if value is None else str(value))

                    self.vocabulary_table.setItem(row_number, column, item)

            self.vocabulary_table.resizeRowsToContents()

        finally:

            self.vocabulary_table.blockSignals(False)

            self._filling_vocabulary = False

        self.update_checkbox_status()

    def vocabulary_checkbox_changed(self, item):

        if self._filling_vocabulary or item.column() != 0:

            return

        row = item.row()

        if row >= len(self.filtered_vocabulary):

            return

        record_id = self.filtered_vocabulary[row]["id"]

        if item.checkState() == Qt.CheckState.Checked:

            self.checked_vocabulary_ids.add(record_id)

        else:

            self.checked_vocabulary_ids.discard(record_id)

        self.update_checkbox_status()

    def toggle_all_visible_vocabulary(self, _state):

        if self._filling_vocabulary:

            return

        visible_ids = {record["id"] for record in self.filtered_vocabulary}

        if self.select_all_checkbox.isChecked():

            self.checked_vocabulary_ids.update(visible_ids)

        else:

            self.checked_vocabulary_ids.difference_update(visible_ids)

        self.fill_vocabulary_checkboxes(self.filtered_vocabulary, [

            "word", "reading", "dictionary_form", "meaning", "times_seen"

        ])

    def update_checkbox_status(self):

        count = len(self.checked_vocabulary_ids)

        self.selected_count_label.setText(f"{count} word{'s' if count != 1 else ''} selected")

        visible_ids = {record["id"] for record in self.filtered_vocabulary}

        all_visible = bool(visible_ids) and visible_ids.issubset(self.checked_vocabulary_ids)

        self.select_all_checkbox.blockSignals(True)

        self.select_all_checkbox.setChecked(all_visible)

        self.select_all_checkbox.blockSignals(False)

    def checked_records(self):

        """Return checked vocabulary across searches, in database display order."""

        return [record for record in self.vocabulary

                if record["id"] in self.checked_vocabulary_ids]

    def update_history_buttons(self, _index=None):

        """Show vocabulary-only actions only on the Vocabulary tab."""

        is_vocabulary = self.tabs.currentWidget() is self.vocabulary_table

        self.selection_controls_widget.setVisible(is_vocabulary)

        self.delete_button.setVisible(is_vocabulary)

        self.export_controls_widget.setVisible(is_vocabulary)

    def clear_history(self):

        """Clear both history tables after explicit confirmation."""

        sentence_count = len(getattr(self, "sentences", []))

        vocabulary_count = len(getattr(self, "vocabulary", []))

        if sentence_count == 0 and vocabulary_count == 0:

            QMessageBox.information(self, "Clear All History", "History is already empty.")

            return

        response = QMessageBox.warning(

            self,

            "Clear All History — Confirm",

            f"Permanently delete ALL history?\n\n"

            f"{sentence_count} saved sentence(s) and {vocabulary_count} vocabulary word(s)\n\n"

            "This deletes entries from BOTH tabs, including items hidden by search.\n"

            "This cannot be undone. Anki cards and exported CSV files are unaffected.",

            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,

            QMessageBox.StandardButton.Cancel,

        )

        if response != QMessageBox.StandardButton.Yes:

            return

        try:

            clear_all_history()

            self.refresh_history()

            QMessageBox.information(self, "History cleared", "All sentence and vocabulary history was deleted.")

        except Exception as error:

            QMessageBox.warning(self, "Clear history error", str(error))

    def delete_selected_vocabulary(self):

        """Delete only the selected vocabulary records, by database ID."""

        rows = self.checked_records()

        if not rows:

            QMessageBox.information(

                self, "Delete vocabulary", "Tick the checkbox beside one or more vocabulary words first."

            )

            return

        count = len(rows)

        response = QMessageBox.question(

            self,

            "Confirm deletion",

            f"Permanently delete {count} selected vocabulary word(s) from History?\n\n"

            "This cannot be undone. Sentence history and Anki cards will not be changed.",

            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,

            QMessageBox.StandardButton.No,

        )

        if response != QMessageBox.StandardButton.Yes:

            return

        try:

            deleted = delete_vocabulary_by_ids([record["id"] for record in rows])

            self.refresh_history()

            QMessageBox.information(

                self, "Deletion complete", f"Deleted {deleted} vocabulary word(s)."

            )

        except Exception as error:

            QMessageBox.warning(self, "Delete error", str(error))

    def export_history(self):

        """Export only Japanese word and combined reading/English meaning."""

        scope = self.export_scope.currentData()

        if scope == "selected":

            rows = self.checked_records()

        elif scope == "filtered":

            rows = self.filtered_vocabulary

        else:

            rows = self.vocabulary

        if not rows:

            QMessageBox.information(

                self, "Export", "No vocabulary to export. Tick vocabulary checkboxes "

                "or choose another export scope."

            )

            return

        from pathlib import Path

        from datetime import datetime

        import csv

        suggested_name = "japanese_vocabulary_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".csv"

        filename, _ = QFileDialog.getSaveFileName(

            self, "Save vocabulary CSV", suggested_name, "CSV files (*.csv)"

        )

        if not filename:

            return

        path = Path(filename)

        if path.suffix.lower() != ".csv":

            path = path.with_suffix(".csv")

        try:

            with path.open("w", encoding="utf-8-sig", newline="") as output:

                writer = csv.writer(output)

                writer.writerow(["Japanese Word", "Yomikata, English Meaning"])

                for record in rows:

                    word = str(record["word"] or "")

                    reading = str(record["reading"] or "")

                    meaning = str(record["meaning"] or "")

                    combined = ", ".join(part for part in (reading, meaning) if part)

                    writer.writerow([word, combined])

        except Exception as error:

            QMessageBox.warning(self, "Export error", str(error))

            return

        QMessageBox.information(

            self, "Export complete", f"Exported {len(rows)} vocabulary words to:\n{path}"

        )

class ResultWindow(QWidget):

    translation_requested = Signal(str)

    explanation_requested = Signal(

        int, str, object

    )

    anki_requested = Signal(str, object)

    shortcut_requested = Signal(str)

    def __init__(self):

        super().__init__()

        self.setWindowTitle(

            "Japanese Subtitle Helper"

        )

        self.resize(720, 620)

        self.setMinimumSize(480, 420)

        self.words = []

        self.dictionary_ready = False

        self.current_sentence = ""

        self.current_translation = ""

        self.selected_word = None

        self.selected_meaning = ""

        self.selected_explanation = ""

        self.explanation_request_id = 0

        self.anki_busy = False

        self.settings = QSettings(

            "JapaneseSubtitleHelper",

            "JapaneseSubtitleHelper",

        )

        self.setStyleSheet("""

            QWidget {

                background-color: #191b20;

                color: #edf0f5;

                font-family: "Segoe UI";

                font-size: 13px;

            }

            QLabel {

                background: transparent;

            }

            QTextEdit, QTextBrowser {

                background-color: #252831;

                color: #f4f5f8;

                border: 1px solid #393e49;

                border-radius: 8px;

                padding: 7px;

                selection-background-color: #406b9c;

            }

            QTextEdit:focus, QTextBrowser:focus {

                border: 1px solid #6095cf;

            }

            QPushButton {

                background-color: #303744;

                border: 1px solid #465061;

                border-radius: 7px;

                padding: 9px 12px;

                font-weight: 600;

            }

            QPushButton:hover {

                background-color: #3c485a;

            }

            QPushButton:disabled {

                color: #7d8490;

                background-color: #242831;

                border-color: #343942;

            }

            QPushButton#saveButton {

                background-color: #245a85;

                border-color: #3478aa;

            }

            QPushButton#saveButton:hover {

                background-color: #2d709f;

            }

            QComboBox {

                background-color: #252831;

                color: #edf0f5;

                border: 1px solid #465061;

                border-radius: 6px;

                padding: 6px 10px;

                min-width: 150px;

            }

            QComboBox QAbstractItemView {

                background-color: #252831;

                color: #edf0f5;

                selection-background-color: #345b80;

            }

            QScrollArea {

                border: none;

                background: transparent;

            }

            QFrame#separator {

                background-color: #363b45;

                max-height: 1px;

            }

        """)

        main_layout = QVBoxLayout(self)

        main_layout.setContentsMargins(

            14, 12, 14, 12

        )

        main_layout.setSpacing(8)

        # Fixed header with shortcut settings.

        header = QHBoxLayout()

        title = QLabel(

            "Japanese Subtitle Helper"

        )

        title.setStyleSheet(

            "font-size: 17px; font-weight: 700;"

        )

        header.addWidget(title)

        header.addStretch()

        header.addWidget(

            QLabel("Capture shortcut:")

        )

        self.shortcut_combo = QComboBox()

        for label, hotkey in SHORTCUTS.items():

            self.shortcut_combo.addItem(

                label, hotkey

            )

        saved_shortcut = self.settings.value(

            "capture_shortcut",

            "alt+shift+z",

        )

        index = self.shortcut_combo.findData(

            saved_shortcut

        )

        if index < 0:

            index = 0

        self.shortcut_combo.setCurrentIndex(

            index

        )

        header.addWidget(

            self.shortcut_combo

        )

        main_layout.addLayout(header)

        self.shortcut_combo.currentIndexChanged.connect(

            self.shortcut_changed

        )

        # Scrollable content.

        scroll_area = QScrollArea()

        scroll_area.setWidgetResizable(True)

        content_widget = QWidget()

        layout = QVBoxLayout(content_widget)

        layout.setContentsMargins(

            4, 6, 4, 6

        )

        layout.setSpacing(8)

        scroll_area.setWidget(

            content_widget

        )

        main_layout.addWidget(

            scroll_area, 1

        )

        self.status_label = QLabel(

            "Choose a shortcut to capture Japanese subtitles."

        )

        self.status_label.setStyleSheet(

            "color: #a7b5c8;"

        )

        layout.addWidget(

            self.status_label

        )

        # Recognized Japanese.

        layout.addWidget(

            self.section_label(

                "Recognized Japanese"

            )

        )

        self.text_box = AutoGrowingTextEdit()

        self.text_box.setFont(

            QFont("Yu Gothic UI", 12)

        )

        layout.addWidget(

            self.text_box

        )

        # English translation.

        layout.addWidget(

            self.section_label(

                "English Translation"

            )

        )

        self.translation_label = QLabel(

            "Your translation will appear here."

        )

        self.translation_label.setWordWrap(

            True

        )

        self.translation_label.setMinimumHeight(

            38

        )

        self.translation_label.setStyleSheet(

            "font-size: 14px; "

            "color: #e1e8f3;"

        )

        layout.addWidget(

            self.translation_label

        )

        # Clickable Japanese words.

        layout.addWidget(

            self.section_label(

                "Click a Japanese Word"

            )

        )

        self.word_browser = AutoGrowingTextBrowser()

        self.word_browser.setOpenLinks(False)

        self.word_browser.anchorClicked.connect(

            self.word_clicked

        )

        layout.addWidget(

            self.word_browser

        )

        # Word details.

        self.word_label = QLabel("Word: —")

        self.reading_label = QLabel(

            "Reading: —"

        )

        self.dictionary_label = QLabel(

            "Dictionary form: —"

        )

        self.meaning_label = QLabel(

            "Dictionary meaning: —"

        )

        self.meaning_label.setWordWrap(

            True

        )

        layout.addWidget(

            self.word_label

        )

        layout.addWidget(

            self.reading_label

        )

        layout.addWidget(

            self.dictionary_label

        )

        layout.addWidget(

            self.meaning_label

        )

        # AI explanation.

        layout.addWidget(

            self.section_label(

                "AI Explanation in Context"

            )

        )

        self.explanation_box = QTextBrowser()

        self.explanation_box.setFixedHeight(

            115

        )

        self.explanation_box.setPlainText(

            "Click a Japanese word to see its AI explanation."

        )

        layout.addWidget(

            self.explanation_box

        )

        # Anki buttons.

        anki_buttons = QHBoxLayout()

        self.save_word_button = QPushButton(

            "Save Word to Anki"

        )

        self.save_sentence_button = QPushButton(

            "Save Sentence to Anki"

        )

        self.save_word_button.setObjectName(

            "saveButton"

        )

        self.save_sentence_button.setObjectName(

            "saveButton"

        )

        self.save_word_button.clicked.connect(

            self.save_selected_word

        )

        self.save_sentence_button.clicked.connect(

            self.save_full_sentence

        )

        anki_buttons.addWidget(

            self.save_word_button

        )

        anki_buttons.addWidget(

            self.save_sentence_button

        )

        layout.addLayout(

            anki_buttons

        )

        self.anki_status = QLabel("")

        self.anki_status.setWordWrap(True)

        layout.addWidget(

            self.anki_status

        )

        layout.addStretch()

        # Keep History accessible without changing the existing workflow.

        self.history_window = None

        self.history_button = QPushButton("History")

        self.history_button.clicked.connect(self.open_history)

        main_layout.addWidget(self.history_button)

        # Exit always stays visible.

        self.exit_button = QPushButton(

            "Exit Application"

        )

        self.exit_button.clicked.connect(

            self.exit_application

        )

        main_layout.addWidget(

            self.exit_button

        )

        self.update_save_buttons()

    def section_label(self, text):

        label = QLabel(text)

        label.setStyleSheet(

            "font-size: 13px;"

            "font-weight: 600;"

            "color: #a9c7e7;"

        )

        return label

    def shortcut_changed(self, index):

        hotkey = self.shortcut_combo.itemData(

            index

        )

        if hotkey:

            self.shortcut_requested.emit(

                hotkey

            )

    def update_save_buttons(self):

        self.save_word_button.setEnabled(

            not self.anki_busy

            and self.selected_word is not None

            and bool(self.selected_explanation)

        )

        self.save_sentence_button.setEnabled(

            not self.anki_busy

            and bool(self.current_sentence)

            and bool(self.current_translation)

        )

    def show_loading(self):

        self.explanation_request_id += 1

        self.current_sentence = ""

        self.current_translation = ""

        self.selected_word = None

        self.selected_meaning = ""

        self.selected_explanation = ""

        self.words = []

        self.status_label.setText(

            "Recognizing Japanese text..."

        )

        self.text_box.clear()

        self.word_browser.clear()

        self.translation_label.setText(

            "Waiting for Japanese text..."

        )

        self.word_label.setText(

            "Word: —"

        )

        self.reading_label.setText(

            "Reading: —"

        )

        self.dictionary_label.setText(

            "Dictionary form: —"

        )

        self.meaning_label.setText(

            "Dictionary meaning: —"

        )

        self.explanation_box.setPlainText(

            "Click a Japanese word to see its AI explanation."

        )

        self.anki_status.clear()

        self.update_save_buttons()

        self.showNormal()

        self.raise_()

        self.activateWindow()

    def display_text(self, text):

        self.current_sentence = text

        self.text_box.setPlainText(text)

        if not text.strip():

            self.status_label.setText(

                "No Japanese text detected."

            )

            self.translation_label.setText(

                "No text to translate."

            )

            return

        self.status_label.setText(

            "Click a word for its explanation."

        )

        self.translation_label.setText(

            "Translating..."

        )

        try:

            self.words = split_japanese(text)

            parts = []

            for index, item in enumerate(

                self.words

            ):

                word = html.escape(

                    item["word"]

                )

                parts.append(

                    f'<a href="word:{index}" '

                    f'style="color: #85d9ff; '

                    f'text-decoration: none;">'

                    f'{word}</a>'

                )

            self.word_browser.setHtml(

                '<div style="'

                'font-family: Yu Gothic UI;'

                'font-size: 20px;'

                'line-height: 1.5;'

                'white-space: pre-wrap;">'

                + "".join(parts)

                + '</div>'

            )

        except Exception as error:

            self.status_label.setText(

                f"Tokenizer error: {error}"

            )

        self.translation_requested.emit(

            text

        )

    def show_translation(

        self, sentence, translation

    ):

        if sentence != self.current_sentence:

            return

        self.current_translation = translation

        self.translation_label.setText(

            translation

        )

        self.update_save_buttons()

        # Store completed translations; history errors must not break the UI.

        if sentence.strip() and translation.strip():

            try:

                save_history_sentence(sentence, translation)

            except Exception as error:

                print("Sentence history save error:", error)

    def show_translation_error(

        self, sentence, error

    ):

        if sentence != self.current_sentence:

            return

        self.translation_label.setText(

            f"Translation error: {error}"

        )

    def word_clicked(self, url):

        try:

            index = int(url.path())

            word = self.words[index]

        except (ValueError, IndexError):

            return

        self.explanation_request_id += 1

        request_id = (

            self.explanation_request_id

        )

        self.selected_word = word.copy()

        self.selected_meaning = ""

        self.selected_explanation = ""

        self.word_label.setText(

            f"Word: {word['word']}"

        )

        self.reading_label.setText(

            f"Reading: {word['reading']}"

        )

        self.dictionary_label.setText(

            "Dictionary form: "

            + word["dictionary_form"]

        )

        if self.dictionary_ready:

            try:

                result = lookup_word(

                    word["dictionary_form"]

                )

                if result["meanings"] == [

                    "Meaning not found."

                ]:

                    result = lookup_word(

                        word["word"]

                    )

                self.selected_meaning = (

                    "; ".join(

                        result["meanings"]

                    )

                )

                self.meaning_label.setText(

                    "Dictionary meaning: "

                    + self.selected_meaning

                )

            except Exception as error:

                self.meaning_label.setText(

                    f"Dictionary error: {error}"

                )

        else:

            self.meaning_label.setText(

                "Dictionary is loading..."

            )

        # Record clicked vocabulary without affecting word explanations.

        # A database error must never interrupt the existing workflow.

        try:

            save_history_vocabulary(

                word["word"],

                word["reading"],

                word["dictionary_form"],

                self.selected_meaning,

            )

        except Exception as error:

            print("Vocabulary history save error:", error)

        self.explanation_box.setPlainText(

            "Generating contextual AI explanation..."

        )

        self.anki_status.clear()

        self.update_save_buttons()

        self.explanation_requested.emit(

            request_id,

            self.current_sentence,

            word,

        )

    def show_explanation(

        self, request_id, explanation

    ):

        if request_id != (

            self.explanation_request_id

        ):

            return

        self.selected_explanation = explanation

        self.explanation_box.setPlainText(

            explanation

        )

        self.update_save_buttons()

    def show_explanation_error(

        self, request_id, error

    ):

        if request_id != (

            self.explanation_request_id

        ):

            return

        self.explanation_box.setPlainText(

            f"AI explanation error: {error}"

        )

    def save_selected_word(self):

        if (

            self.selected_word is None

            or not self.selected_explanation

            or self.anki_busy

        ):

            return

        word = self.selected_word

        data = {

            "word": word["word"],

            "reading": word["reading"],

            "meaning": self.selected_meaning,

            "explanation": "",

            "japanese_sentence": "",

            "english_translation": "",

        }

        self.start_anki_save(

            "word", data

        )

    def save_full_sentence(self):

        if (

            not self.current_sentence

            or not self.current_translation

            or self.anki_busy

        ):

            return

        data = {

            "japanese_sentence": self.current_sentence,

            "english_translation": self.current_translation,

        }

        self.start_anki_save(

            "sentence", data

        )

    def start_anki_save(

        self, mode, data

    ):

        self.anki_busy = True

        self.anki_status.setText(

            "Saving to Anki..."

        )

        self.update_save_buttons()

        self.anki_requested.emit(

            mode, data

        )

    def anki_saved(self, message):

        self.anki_busy = False

        self.anki_status.setText(

            message

        )

        self.update_save_buttons()

    def anki_failed(self, error):

        self.anki_busy = False

        self.anki_status.setText(

            f"Anki error: {error}"

        )

        self.update_save_buttons()

    def display_error(self, error):

        self.status_label.setText(

            "OCR error"

        )

        self.text_box.setPlainText(

            error

        )

    def open_history(self):

        if self.history_window is None:

            self.history_window = HistoryWindow()

        self.history_window.refresh_history()

        self.history_window.showNormal()

        self.history_window.raise_()

        self.history_window.activateWindow()

    def exit_application(self):

        QApplication.instance().quit()

class AppController(QObject):

    def __init__(self):

        super().__init__()

        self.result_window = ResultWindow()

        self.overlay = None

        self.worker = None

        self.translation_worker = None

        self.explanation_workers = []

        self.anki_workers = []

        self.hotkey_handler = HotkeyHandler()

        self.hotkey_handler.activated.connect(

            self.start_capture

        )

        self.hotkey_id = None

        self.current_hotkey = None

        self.result_window.shortcut_requested.connect(

            self.change_shortcut

        )

        self.result_window.translation_requested.connect(

            self.start_translation

        )

        self.result_window.explanation_requested.connect(

            self.start_explanation

        )

        self.result_window.anki_requested.connect(

            self.start_anki_save

        )

        initial_hotkey = (

            self.result_window.shortcut_combo.currentData()

        )

        self.change_shortcut(

            initial_hotkey

        )

        self.dictionary_worker = DictionaryWorker()

        self.dictionary_worker.loaded.connect(

            self.dictionary_loaded

        )

        self.dictionary_worker.failed.connect(

            self.dictionary_failed

        )

        self.dictionary_worker.start()

        self.setup_system_tray()

    def setup_system_tray(self):

        """Keep the app discoverable while its main window is hidden."""

        self.tray = None

        if not QSystemTrayIcon.isSystemTrayAvailable():

            # On systems without a tray, show the window so startup is visible.

            self.result_window.showNormal()

            self.result_window.raise_()

            return

        pixmap = QPixmap(64, 64)

        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setBrush(QColor("#245a85"))

        painter.setPen(Qt.PenStyle.NoPen)

        painter.drawRoundedRect(2, 2, 60, 60, 14, 14)

        painter.setPen(QColor("#ffffff"))

        font = QFont("Segoe UI", 34, QFont.Weight.Bold)

        painter.setFont(font)

        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "K")

        painter.end()

        icon = QIcon(pixmap)

        QApplication.instance().setWindowIcon(icon)

        self.result_window.setWindowIcon(icon)

        self.tray = QSystemTrayIcon(icon, self)

        self.tray.setToolTip("KotobaLens — Japanese Subtitle Helper")

        menu = QMenu()

        open_action = QAction("Open KotobaLens", menu)

        open_action.triggered.connect(self.open_main_window)

        menu.addAction(open_action)

        capture_action = QAction("Capture Japanese Subtitle", menu)

        capture_action.triggered.connect(self.start_capture)

        menu.addAction(capture_action)

        menu.addSeparator()

        exit_action = QAction("Exit KotobaLens", menu)

        exit_action.triggered.connect(QApplication.instance().quit)

        menu.addAction(exit_action)

        self.tray.setContextMenu(menu)

        self.tray.activated.connect(self.tray_activated)

        self.tray.show()

        QTimer.singleShot(900, self.show_startup_notification)

    def open_main_window(self):

        self.result_window.showNormal()

        self.result_window.raise_()

        self.result_window.activateWindow()

    def tray_activated(self, reason):

        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:

            self.open_main_window()

    def show_startup_notification(self):

        if self.tray is None or not self.tray.isVisible():

            return

        shortcut = next(

            (name for name, value in SHORTCUTS.items()

             if value == self.current_hotkey),

            self.current_hotkey or "your configured shortcut",

        )

        self.tray.showMessage(

            "KotobaLens is ready",

            f"Press {shortcut} to capture Japanese subtitles. "

            "Right-click the tray icon for options.",

            QSystemTrayIcon.MessageIcon.Information,

            5000,

        )

    def change_shortcut(self, hotkey):

        if hotkey == self.current_hotkey:

            return

        old_hotkey = self.current_hotkey

        old_id = self.hotkey_id

        if old_id is not None:

            keyboard.remove_hotkey(old_id)

            self.hotkey_id = None

        try:

            new_id = keyboard.add_hotkey(

                hotkey,

                lambda: self.hotkey_handler.activated.emit(),

            )

            self.hotkey_id = new_id

            self.current_hotkey = hotkey

            self.result_window.settings.setValue(

                "capture_shortcut",

                hotkey,

            )

            label = next(

                (

                    name

                    for name, value in SHORTCUTS.items()

                    if value == hotkey

                ),

                hotkey,

            )

            self.result_window.status_label.setText(

                f"Capture shortcut: {label}"

            )

            print(

                f"Capture shortcut changed to: {label}"

            )

        except Exception as error:

            self.result_window.status_label.setText(

                f"Shortcut error: {error}"

            )

            if old_hotkey:

                try:

                    self.hotkey_id = keyboard.add_hotkey(

                        old_hotkey,

                        lambda: self.hotkey_handler.activated.emit(),

                    )

                    self.current_hotkey = old_hotkey

                except Exception:

                    self.current_hotkey = None

            if self.current_hotkey:

                index = (

                    self.result_window.shortcut_combo.findData(

                        self.current_hotkey

                    )

                )

                if index >= 0:

                    combo = self.result_window.shortcut_combo

                    combo.blockSignals(True)

                    combo.setCurrentIndex(index)

                    combo.blockSignals(False)

    def dictionary_loaded(self):

        self.result_window.dictionary_ready = True

        print(

            "Japanese-English dictionary ready!"

        )

    def dictionary_failed(self, error):

        print(

            "Dictionary loading error:", error

        )

    def start_capture(self):

        if (

            self.overlay is not None

            and self.overlay.isVisible()

        ):

            return

        if (

            self.worker is not None

            and self.worker.isRunning()

        ):

            return

        if (

            self.translation_worker is not None

            and self.translation_worker.isRunning()

        ):

            print(

                "Translation is still running."

            )

            return

        self.result_window.hide()

        QApplication.processEvents()

        try:

            with mss.MSS() as screenshot_tool:

                monitor = screenshot_tool.monitors[1]

                screenshot = screenshot_tool.grab(

                    monitor

                )

            self.overlay = SelectionOverlay(

                screenshot,

                QApplication.primaryScreen().geometry(),

            )

            self.overlay.image_selected.connect(

                self.process_selection

            )

            self.overlay.show()

            self.overlay.raise_()

            self.overlay.activateWindow()

        except Exception as error:

            self.result_window.showNormal()

            self.result_window.display_error(

                str(error)

            )

    def process_selection(self, image):

        # Store screenshots in the user's writable app-data folder.
        from pathlib import Path
        import os

        app_data = Path(os.environ.get(
            "LOCALAPPDATA", str(Path.home() / "AppData" / "Local")
        )) / "KotobaLens"
        app_data.mkdir(parents=True, exist_ok=True)
        image_path = str(app_data / "selected_subtitle.png")

        if not image.save(image_path):

            self.result_window.showNormal()

            self.result_window.display_error(

                "Could not save selected image."

            )

            return

        self.result_window.show_loading()

        self.worker = OCRWorker(

            image_path

        )

        self.worker.finished_text.connect(

            self.result_window.display_text

        )

        self.worker.failed.connect(

            self.result_window.display_error

        )

        self.worker.start()

    def start_translation(

        self, japanese_text

    ):

        self.translation_worker = TranslationWorker(

            japanese_text

        )

        self.translation_worker.translated.connect(

            self.result_window.show_translation

        )

        self.translation_worker.failed.connect(

            self.result_window.show_translation_error

        )

        self.translation_worker.start()

    def start_explanation(

        self, request_id, sentence, word

    ):

        worker = ExplanationWorker(

            request_id,

            sentence,

            word,

        )

        self.explanation_workers.append(

            worker

        )

        worker.explained.connect(

            self.result_window.show_explanation

        )

        worker.failed.connect(

            self.result_window.show_explanation_error

        )

        worker.finished.connect(

            lambda: self.remove_worker(

                self.explanation_workers,

                worker,

            )

        )

        worker.start()

    def start_anki_save(

        self, mode, data

    ):

        worker = AnkiWorker(

            mode, data

        )

        self.anki_workers.append(

            worker

        )

        worker.saved.connect(

            self.result_window.anki_saved

        )

        worker.failed.connect(

            self.result_window.anki_failed

        )

        worker.finished.connect(

            lambda: self.remove_worker(

                self.anki_workers,

                worker,

            )

        )

        worker.start()

    def remove_worker(

        self, worker_list, worker

    ):

        if worker in worker_list:

            worker_list.remove(worker)

        worker.deleteLater()

    def cleanup(self):

        if self.hotkey_id is not None:

            keyboard.remove_hotkey(

                self.hotkey_id

            )

            self.hotkey_id = None

        active_workers = [

            self.worker,

            self.translation_worker,

            self.dictionary_worker,

            *self.explanation_workers,

            *self.anki_workers,

        ]

        for worker in active_workers:

            if (

                worker is not None

                and worker.isRunning()

            ):

                worker.wait()

def main():

    app = QApplication(sys.argv)

    app.setQuitOnLastWindowClosed(False)

    app.setFont(

        QFont("Segoe UI", 10)

    )

    # Initialize local history without preventing app startup on failure.

    try:

        initialize_database()

    except Exception as error:

        print("Database initialization error:", error)

    controller = AppController()

    app.aboutToQuit.connect(

        controller.cleanup

    )

    print(

        "Japanese Subtitle Helper is running."

    )

    return app.exec()

if __name__ == "__main__":

    sys.exit(main())
