"""
JASS English → Mizo Translator v1.1

Offline translation-memory translator built on the existing
JASS_English_Mizo_Translation.db.

v1.1 goals:
- Exact sentence/phrase matching first
- Better FTS candidate ranking
- Normalized matching
- Phrase/word fallback
- Candidate translations grouped by Mizo output
- Match type and corpus frequency shown
- Corpus evidence for the selected translation
- Copy English / Mizo / both
- Export results
- Database information
- No modification of the translation database
"""

from pathlib import Path
import csv
import re
import sqlite3
from collections import Counter

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QSplitter,
    QListWidget, QListWidgetItem, QTextEdit, QGroupBox, QFormLayout,
    QMessageBox, QFileDialog, QStatusBar, QSpinBox, QToolButton
)

BASE = Path(__file__).resolve().parent
DB_PATH = BASE / "JASS_English_Mizo_Translation.db"


def norm(text):
    text = str(text or "").strip().lower()
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = re.sub(r"\s+", " ", text)
    return text


def tokenize(text):
    return re.findall(r"[^\W_]+(?:['’\-][^\W_]+)*", norm(text), flags=re.UNICODE)


class TranslationDB:
    def __init__(self, path):
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(
                f"Translation database not found:\n{self.path}"
            )
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self._validate()

    def _validate(self):
        tables = {
            r["name"] for r in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        required = {"translations", "translations_fts", "metadata"}
        missing = required - tables
        if missing:
            raise RuntimeError(
                "Invalid JASS translation database.\nMissing: "
                + ", ".join(sorted(missing))
            )

    def count(self):
        return self.conn.execute(
            "SELECT COUNT(*) FROM translations"
        ).fetchone()[0]

    def metadata(self):
        return dict(self.conn.execute(
            "SELECT key, value FROM metadata ORDER BY key"
        ).fetchall())

    def exact(self, query, limit=100):
        q = norm(query)
        return self.conn.execute("""
            SELECT *
            FROM translations
            WHERE english_normalized = ?
            ORDER BY frequency DESC, id
            LIMIT ?
        """, (q, limit)).fetchall()

    def prefix(self, query, limit=100):
        q = norm(query)
        return self.conn.execute("""
            SELECT *
            FROM translations
            WHERE english_normalized LIKE ?
            ORDER BY frequency DESC, id
            LIMIT ?
        """, (q + "%", limit)).fetchall()

    def contains(self, query, limit=100):
        q = "%" + norm(query) + "%"
        return self.conn.execute("""
            SELECT *
            FROM translations
            WHERE english_normalized LIKE ?
               OR mizo_normalized LIKE ?
            ORDER BY frequency DESC, id
            LIMIT ?
        """, (q, q, limit)).fetchall()

    def fts(self, query, limit=100):
        tokens = tokenize(query)
        if not tokens:
            return []

        # Phrase search is attempted first.
        phrase = '"' + " ".join(tokens).replace('"', " ") + '"'
        attempts = [phrase, " ".join(tokens)]

        for match in attempts:
            try:
                return self.conn.execute("""
                    SELECT t.*,
                           bm25(translations_fts) AS rank
                    FROM translations_fts f
                    JOIN translations t ON t.id = f.rowid
                    WHERE translations_fts MATCH ?
                    ORDER BY rank ASC, t.frequency DESC, t.id
                    LIMIT ?
                """, (match, limit)).fetchall()
            except sqlite3.OperationalError:
                pass

        return self.contains(query, limit)

    def candidate_search(self, query, limit=100):
        """Return ranked candidates without changing the database."""
        qn = norm(query)
        if not qn:
            return []

        exact = self.exact(query, limit)
        if exact:
            return [
                {"row": r, "match": "Exact sentence / phrase", "score": 1000000 - i}
                for i, r in enumerate(exact)
            ]

        rows = self.fts(query, max(limit * 3, 100))

        q_tokens = set(tokenize(query))
        scored = []

        for r in rows:
            en = norm(r["english"])
            en_tokens = set(tokenize(en))

            if en == qn:
                match_type = "Exact sentence / phrase"
                score = 1000000
            elif en.startswith(qn):
                match_type = "Prefix match"
                score = 900000
            elif qn in en:
                match_type = "Phrase contained"
                score = 800000
            else:
                overlap = (
                    len(q_tokens & en_tokens) / max(len(q_tokens), 1)
                )
                if overlap >= 0.75:
                    match_type = "Strong word overlap"
                elif overlap >= 0.40:
                    match_type = "Partial word overlap"
                else:
                    match_type = "Corpus / FTS match"

                # Frequency helps, but relevance remains primary.
                score = overlap * 100000 + min(
                    int(r["frequency"] or 0), 50000
                )

            scored.append({
                "row": r,
                "match": match_type,
                "score": score,
            })

        scored.sort(
            key=lambda x: (
                -x["score"],
                -int(x["row"]["frequency"] or 0),
                x["row"]["id"],
            )
        )
        return scored[:limit]

    def grouped_candidates(self, query, limit=12):
        """Group identical Mizo outputs and retain strongest evidence."""
        candidates = self.candidate_search(query, max(limit * 5, 60))
        groups = {}

        for c in candidates:
            r = c["row"]
            key = norm(r["mizo"])
            if not key:
                continue

            if key not in groups:
                groups[key] = {
                    "mizo": r["mizo"],
                    "english": r["english"],
                    "frequency": int(r["frequency"] or 0),
                    "source": r["source"],
                    "match": c["match"],
                    "score": c["score"],
                    "rows": [r],
                }
            else:
                g = groups[key]
                g["frequency"] += int(r["frequency"] or 0)
                g["rows"].append(r)
                if c["score"] > g["score"]:
                    g["score"] = c["score"]
                    g["match"] = c["match"]
                    g["english"] = r["english"]
                    g["source"] = r["source"]

        result = list(groups.values())
        result.sort(
            key=lambda g: (-g["score"], -g["frequency"], norm(g["mizo"]))
        )
        return result[:limit]

    def evidence(self, english, mizo, limit=12):
        return self.conn.execute("""
            SELECT *
            FROM translations
            WHERE english_normalized = ?
              AND mizo_normalized = ?
            ORDER BY frequency DESC, id
            LIMIT ?
        """, (norm(english), norm(mizo), limit)).fetchall()

    def close(self):
        self.conn.close()


class MainWindow(QMainWindow):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.candidates = []
        self.selected = None

        self.setWindowTitle("JASS English → Mizo Translator v1.1")
        self.resize(1500, 900)
        self.setMinimumSize(1100, 700)

        self._build_ui()

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(9)

        title = QLabel("JASS English → Mizo Translator")
        title.setFont(QFont("Segoe UI", 23, QFont.Weight.Bold))
        outer.addWidget(title)

        subtitle = QLabel(
            "Offline translation memory • exact matching • FTS5 • "
            "candidate ranking • corpus evidence"
        )
        subtitle.setStyleSheet("color:#667085;")
        outer.addWidget(subtitle)

        search_row = QHBoxLayout()

        self.search = QLineEdit()
        self.search.setPlaceholderText(
            "Enter an English word, phrase, or sentence…"
        )
        self.search.setClearButtonEnabled(True)
        self.search.returnPressed.connect(self.translate)

        self.mode = QComboBox()
        self.mode.addItems([
            "Smart Translate",
            "Exact",
            "FTS",
            "Prefix",
            "Contains",
        ])
        self.mode.setMinimumWidth(145)

        self.limit = QSpinBox()
        self.limit.setRange(5, 200)
        self.limit.setValue(50)
        self.limit.setPrefix("Results: ")

        btn = QPushButton("Translate")
        btn.setMinimumWidth(110)
        btn.clicked.connect(self.translate)

        clear = QToolButton()
        clear.setText("Clear")
        clear.clicked.connect(self.clear_all)

        search_row.addWidget(self.search, 1)
        search_row.addWidget(self.mode)
        search_row.addWidget(self.limit)
        search_row.addWidget(btn)
        search_row.addWidget(clear)
        outer.addLayout(search_row)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # LEFT: candidates
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 6, 0)

        left_heading = QLabel("Translation Candidates")
        left_heading.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        left_layout.addWidget(left_heading)

        self.results_list = QListWidget()
        self.results_list.setWordWrap(True)
        self.results_list.currentRowChanged.connect(self.show_candidate)
        left_layout.addWidget(self.results_list, 1)

        self.match_summary = QLabel("Enter English text to begin.")
        self.match_summary.setStyleSheet("color:#667085;")
        self.match_summary.setWordWrap(True)
        left_layout.addWidget(self.match_summary)

        splitter.addWidget(left)

        # RIGHT
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(6, 0, 0, 0)

        result_box = QGroupBox("Translation Result")
        result_form = QFormLayout(result_box)
        result_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.english_label = QLabel("—")
        self.english_label.setWordWrap(True)
        self.english_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.mizo_label = QLabel("—")
        self.mizo_label.setWordWrap(True)
        self.mizo_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.mizo_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))

        self.match_label = QLabel("—")
        self.frequency_label = QLabel("—")
        self.source_label = QLabel("—")
        self.source_label.setWordWrap(True)

        result_form.addRow("English:", self.english_label)
        result_form.addRow("Mizo:", self.mizo_label)
        result_form.addRow("Match:", self.match_label)
        result_form.addRow("Corpus frequency:", self.frequency_label)
        result_form.addRow("Source:", self.source_label)

        buttons = QHBoxLayout()
        copy_mizo = QPushButton("Copy Mizo")
        copy_mizo.clicked.connect(self.copy_mizo)
        copy_both = QPushButton("Copy Both")
        copy_both.clicked.connect(self.copy_both)
        copy_english = QPushButton("Copy English")
        copy_english.clicked.connect(self.copy_english)

        buttons.addWidget(copy_mizo)
        buttons.addWidget(copy_both)
        buttons.addWidget(copy_english)
        buttons.addStretch()

        result_form.addRow("", buttons)
        right_layout.addWidget(result_box)

        evidence_box = QGroupBox("Corpus Evidence")
        evidence_layout = QVBoxLayout(evidence_box)
        self.evidence = QTextEdit()
        self.evidence.setReadOnly(True)
        self.evidence.setPlaceholderText(
            "Evidence for the selected translation will appear here."
        )
        evidence_layout.addWidget(self.evidence)
        right_layout.addWidget(evidence_box, 1)

        splitter.addWidget(right)
        splitter.setSizes([520, 940])

        outer.addWidget(splitter, 1)

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage(
            f"{self.db.count():,} translation pairs loaded"
        )

        export_action = QAction("Export Results", self)
        export_action.triggered.connect(self.export_results)
        self.menuBar().addAction(export_action)

        info_action = QAction("Database Info", self)
        info_action.triggered.connect(self.show_info)
        self.menuBar().addAction(info_action)

    def translate(self):
        query = self.search.text().strip()
        if not query:
            self.clear_all()
            return

        mode = self.mode.currentText()
        limit = self.limit.value()

        if mode == "Smart Translate":
            self.candidates = self.db.grouped_candidates(query, limit)
        else:
            if mode == "Exact":
                rows = self.db.exact(query, limit)
                match = "Exact sentence / phrase"
            elif mode == "FTS":
                rows = self.db.fts(query, limit)
                match = "FTS corpus match"
            elif mode == "Prefix":
                rows = self.db.prefix(query, limit)
                match = "Prefix match"
            else:
                rows = self.db.contains(query, limit)
                match = "Contains match"

            self.candidates = []
            for r in rows:
                self.candidates.append({
                    "mizo": r["mizo"],
                    "english": r["english"],
                    "frequency": int(r["frequency"] or 0),
                    "source": r["source"],
                    "match": match,
                    "score": 0,
                    "rows": [r],
                })

        self.results_list.clear()

        for c in self.candidates:
            item = QListWidgetItem(
                f"{c['mizo']}   •   "
                f"{c['frequency']:,}   •   "
                f"{c['match']}\n"
                f"English evidence: {c['english']}"
            )
            item.setToolTip(
                f"Mizo: {c['mizo']}\n"
                f"English: {c['english']}\n"
                f"Frequency: {c['frequency']:,}\n"
                f"Match: {c['match']}\n"
                f"Source: {c['source']}"
            )
            self.results_list.addItem(item)

        self.match_summary.setText(
            f"{len(self.candidates):,} candidate translation(s) "
            f"for “{query}”"
        )
        self.status.showMessage(
            f"{len(self.candidates):,} candidate(s) for “{query}”"
        )

        if self.candidates:
            self.results_list.setCurrentRow(0)
        else:
            self.clear_result()

    def show_candidate(self, index):
        if index < 0 or index >= len(self.candidates):
            return

        c = self.candidates[index]
        self.selected = c

        self.english_label.setText(c["english"])
        self.mizo_label.setText(c["mizo"])
        self.match_label.setText(c["match"])
        self.frequency_label.setText(f"{c['frequency']:,}")
        self.source_label.setText(c["source"])

        rows = c.get("rows", [])
        if rows:
            # Prefer exact English+Mizo evidence.
            exact_rows = self.db.evidence(
                c["english"], c["mizo"], 12
            )
            if exact_rows:
                rows = exact_rows

        blocks = []
        for i, r in enumerate(rows[:12], 1):
            blocks.append(
                f"{i}. English: {r['english']}\n"
                f"   Mizo: {r['mizo']}\n"
                f"   Frequency: {int(r['frequency'] or 0):,}\n"
                f"   Source: {r['source']}\n"
            )

        self.evidence.setPlainText(
            "\n".join(blocks)
            if blocks else
            "No additional corpus evidence."
        )

    def clear_result(self):
        self.selected = None
        self.english_label.setText("—")
        self.mizo_label.setText("No translation found")
        self.match_label.setText("—")
        self.frequency_label.setText("—")
        self.source_label.setText("—")
        self.evidence.clear()

    def clear_all(self):
        self.search.clear()
        self.results_list.clear()
        self.candidates = []
        self.match_summary.setText("Enter English text to begin.")
        self.clear_result()
        self.status.showMessage(
            f"{self.db.count():,} translation pairs loaded"
        )

    def copy_mizo(self):
        if not self.selected:
            return
        QApplication.clipboard().setText(self.selected["mizo"])
        self.status.showMessage("Mizo translation copied")

    def copy_english(self):
        if not self.selected:
            return
        QApplication.clipboard().setText(self.selected["english"])
        self.status.showMessage("English text copied")

    def copy_both(self):
        if not self.selected:
            return
        text = (
            f"English: {self.selected['english']}\n"
            f"Mizo: {self.selected['mizo']}"
        )
        QApplication.clipboard().setText(text)
        self.status.showMessage("English + Mizo copied")

    def export_results(self):
        if not self.candidates:
            QMessageBox.information(
                self, "Export", "There are no results to export."
            )
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Translation Results",
            "mizo_translation_results.csv",
            "CSV Files (*.csv);;TSV Files (*.tsv);;Text Files (*.txt)"
        )
        if not path:
            return

        try:
            if path.lower().endswith(".txt"):
                with open(path, "w", encoding="utf-8-sig") as f:
                    for c in self.candidates:
                        f.write(
                            f"English: {c['english']}\n"
                            f"Mizo: {c['mizo']}\n"
                            f"Match: {c['match']}\n"
                            f"Frequency: {c['frequency']}\n"
                            f"Source: {c['source']}\n\n"
                        )
            else:
                delimiter = "\t" if path.lower().endswith(".tsv") else ","
                with open(path, "w", newline="", encoding="utf-8-sig") as f:
                    writer = csv.writer(f, delimiter=delimiter)
                    writer.writerow([
                        "English", "Mizo", "Match",
                        "Frequency", "Source"
                    ])
                    for c in self.candidates:
                        writer.writerow([
                            c["english"], c["mizo"], c["match"],
                            c["frequency"], c["source"]
                        ])

            QMessageBox.information(
                self, "Export Complete", f"Saved:\n{path}"
            )
        except Exception as exc:
            QMessageBox.critical(self, "Export Error", str(exc))

    def show_info(self):
        meta = self.db.metadata()

        text = (
            "JASS English → Mizo Translation Memory\n\n"
            f"Database:\n{self.db.path}\n\n"
            f"Translation pairs: {self.db.count():,}\n\n"
            "Metadata:\n"
        )

        for key, value in meta.items():
            text += f"  {key}: {value}\n"

        QMessageBox.information(self, "Database Info", text)

    def closeEvent(self, event):
        self.db.close()
        event.accept()


def main():
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("JASS English → Mizo Translator")
    app.setStyle("Fusion")

    try:
        db = TranslationDB(DB_PATH)
    except Exception as exc:
        QMessageBox.critical(
            None,
            "Database Error",
            str(exc)
        )
        return 1

    window = MainWindow(db)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
