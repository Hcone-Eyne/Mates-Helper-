"""Focused security tests for Finance_bot/Expense_analyzer.py containment.

Statement reads are confined to the approved Finance root (the File Manager
Vault). These tests prove legitimate in-root files still load, traversal /
absolute / symlink escapes are refused before any file is touched, and the
boundary fails closed when the root itself is unavailable.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from Finance_bot import Expense_analyzer as ea


CSV_CONTENT = """Date,Narration,Amount
01/02/2025,Test Store,-125.50
03/02/2025,Salary,2000.00
"""


def _minimal_pdf_bytes(text_line: str) -> bytes:
    """Build a minimal one-page PDF holding a single transaction line.

    Offsets for the xref table are computed programmatically so the file
    is structurally valid for pdfplumber without extra dependencies.
    """
    objs = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n",
    ]
    stream = b"BT /F1 12 Tf 72 720 Td (" + text_line.encode("latin-1") + b") Tj ET\n"
    objs.append(
        b"4 0 obj\n<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n"
        + stream + b"endstream\nendobj\n"
    )
    objs.append(b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n")

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for obj in objs:
        offsets.append(len(out))
        out += obj
    xref_pos = len(out)
    out += b"xref\n0 6\n"
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode("ascii")
    out += (
        b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n"
        + str(xref_pos).encode("ascii") + b"\n%%EOF"
    )
    return bytes(out)


@pytest.fixture()
def root(tmp_path, monkeypatch):
    statements = tmp_path / "statements"
    statements.mkdir()
    monkeypatch.setattr(ea, "STATEMENT_ROOT", statements)
    return statements


class TestLegitimateCsv:
    def test_valid_csv_inside_approved_root(self, root):
        statement = root / "statement.csv"
        statement.write_text(CSV_CONTENT)

        df = ea.load_statement(str(statement))

        assert len(df) == 2
        assert df.iloc[0]["description"] == "Test Store"
        assert df.iloc[0]["amount"] == pytest.approx(-125.50)

    def test_symlink_inside_root_pointing_inside_root_still_works(self, root):
        statement = root / "statement.csv"
        statement.write_text(CSV_CONTENT)
        link = root / "link.csv"
        link.symlink_to(statement)

        df = ea.load_statement(str(link))

        assert len(df) == 2


class TestLegitimatePdf:
    def test_valid_pdf_inside_approved_root(self, root):
        statement = root / "statement.pdf"
        statement.write_bytes(_minimal_pdf_bytes("01/02/2025 Test Store -125.50"))

        df = ea.load_statement(str(statement))

        assert len(df) == 1
        assert df.iloc[0]["description"] == "Test Store"
        assert df.iloc[0]["amount"] == pytest.approx(-125.50)


class TestTraversalRejected:
    def test_parent_traversal_rejected(self, root, tmp_path):
        outside = tmp_path / "secret.csv"
        outside.write_text(CSV_CONTENT)

        with pytest.raises(ValueError, match="outside the approved Finance directory"):
            ea.load_statement(str(root / ".." / "secret.csv"))

    def test_parent_traversal_to_missing_file_still_rejected(self, root):
        # containment is checked before existence: a missing file outside
        # the root must not leak through as a "not found" path probe
        with pytest.raises(ValueError, match="outside the approved Finance directory"):
            ea.load_statement(str(root / ".." / "missing.csv"))

    def test_absolute_outside_root_rejected(self, root, tmp_path):
        outside = tmp_path / "secret.csv"
        outside.write_text(CSV_CONTENT)

        with pytest.raises(ValueError, match="outside the approved Finance directory"):
            ea.load_statement(str(outside))

    def test_symlink_escaping_root_rejected(self, root, tmp_path):
        outside = tmp_path / "secret.csv"
        outside.write_text(CSV_CONTENT)
        link = root / "link.csv"
        link.symlink_to(outside)

        with pytest.raises(ValueError, match="outside the approved Finance directory"):
            ea.load_statement(str(link))


class TestPreservedBehavior:
    def test_nonexistent_inside_root_still_reports_not_found(self, root):
        with pytest.raises(FileNotFoundError):
            ea.load_statement(str(root / "missing.csv"))

    def test_unsupported_extension_still_rejected(self, root):
        note = root / "notes.txt"
        note.write_text("not a statement")

        with pytest.raises(ValueError, match="Unsupported file type"):
            ea.load_statement(str(note))

    def test_unavailable_root_fails_closed(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ea, "STATEMENT_ROOT", tmp_path / "no-such-dir")

        with pytest.raises(ValueError, match="unavailable"):
            ea.load_statement(str(tmp_path / "no-such-dir" / "statement.csv"))


class TestLegitimateCaller:
    def test_interactive_cli_flow_still_works(self, root, monkeypatch, capsys):
        statement = root / "statement.csv"
        statement.write_text(CSV_CONTENT)
        answers = iter([str(statement), "0"])
        monkeypatch.setattr("builtins.input", lambda *args, **kwargs: next(answers))

        ea.run_expense_analyzer()

        out = capsys.readouterr().out
        assert "Test Store" in out or "Track" in out


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
