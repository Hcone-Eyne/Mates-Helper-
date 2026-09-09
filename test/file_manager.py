from pathlib import Path
import shutil
import sys

# this makes the project modules available when the test runs from this folder
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from File_Manager.scanner import scan
from File_Manager.search import search, list_files
from File_Manager.organizer import VAULT_ROOT, ensure_vault, organize_file
from File_Manager.modify_files import (
    rename_file,
    copy_file,
    move_file,
    create_folder,
)


# --------------------------------------------------
# Helpers
# --------------------------------------------------

PASS = 0
FAIL = 0


def test(name, func):
    global PASS, FAIL

    print(f"\n🧪 {name}")

    try:
        result = func()
        print(f"   ✅ PASS")
        if result is not None:
            print(f"   → {result}")
        PASS += 1
    except Exception as exc:
        print(f"   ❌ FAIL")
        print(f"   → {type(exc).__name__}: {exc}")
        FAIL += 1


# --------------------------------------------------
# Setup
# --------------------------------------------------

VAULT = VAULT_ROOT
INBOX = VAULT / "Inbox"
DOCUMENTS = VAULT / "Documents"
NOTES = VAULT / "Notes"


def setup():
    ensure_vault()

    INBOX.mkdir(parents=True, exist_ok=True)

    # Clean only our test files/folders.
    for path in [
        INBOX / "fm_test.txt",
        DOCUMENTS / "fm_test.txt",
        DOCUMENTS / "fm_renamed.txt",
        DOCUMENTS / "fm_copy.txt",
        NOTES / "fm_test.txt",
        NOTES / "fm_renamed.txt",
        NOTES / "fm_renamed_1.txt",
        NOTES / "fm_copy.txt",
    ]:
        if path.exists():
            path.unlink()

    test_folder = VAULT / "TestFolder"
    if test_folder.exists():
        shutil.rmtree(test_folder)

    # Create a fresh test file.
    test_file = INBOX / "fm_test.txt"
    test_file.write_text(
        "File Manager test file.\n"
        "This file exists only for testing Jarvis File Manager.\n"
    )

    return test_file


# --------------------------------------------------
# Tests
# --------------------------------------------------

def test_vault():
    ensure_vault()

    assert VAULT.exists()
    assert INBOX.exists()
    assert DOCUMENTS.exists()

    return f"Vault: {VAULT}"


def test_scan():
    result = scan()

    assert isinstance(result, dict)
    assert "indexed" in result
    assert "removed" in result

    return result


def test_search():
    results = search("fm_test")

    assert len(results) > 0, "Test file was not found in search index"

    return results[0]


def test_organize():
    source = INBOX / "fm_test.txt"

    assert source.exists(), f"Missing test file: {source}"

    destination, category = organize_file(source)

    assert destination.exists()
    assert category == "Notes"

    return {
        "destination": str(destination),
        "category": category,
    }


def test_rename():
    source = DOCUMENTS / "fm_test.txt"

    # .txt should normally be Notes, so this checks where the
    # organizer actually placed it.
    if not source.exists():
        source = VAULT / "Notes" / "fm_test.txt"

    assert source.exists(), f"Could not find organized test file: {source}"

    destination = rename_file(
        source,
        "fm_renamed.txt",
    )

    assert destination.exists()
    assert destination.name == "fm_renamed.txt"

    return destination


def test_copy():
    source = VAULT / "Notes" / "fm_renamed.txt"

    if not source.exists():
        source = DOCUMENTS / "fm_renamed.txt"

    assert source.exists(), f"Missing renamed file: {source}"

    destination = copy_file(
        source,
        source.parent / "fm_copy.txt",
    )

    assert destination.exists()
    assert destination.name == "fm_copy.txt"

    return destination


def test_create_folder():
    folder = VAULT / "TestFolder"

    result = create_folder(folder)

    assert result.exists()
    assert result.is_dir()

    return result


def test_move():
    source = VAULT / "Notes" / "fm_copy.txt"

    if not source.exists():
        source = DOCUMENTS / "fm_copy.txt"

    assert source.exists(), f"Missing copied file: {source}"

    destination = VAULT / "TestFolder" / "fm_copy.txt"

    result = move_file(source, destination)

    assert result.exists()
    assert result.parent.name == "TestFolder"

    return result


def test_final_scan():
    result = scan()

    results = list_files()

    assert isinstance(results, list)

    return {
        "scan": result,
        "indexed_files": len(results),
    }


# --------------------------------------------------
# Run
# --------------------------------------------------

print("=" * 60)
print("        FILE MANAGER TEST SUITE")
print("=" * 60)

print("\n📁 Setting up test environment...")

try:
    setup()
    print("   ✅ Test environment ready")
except Exception as exc:
    print(f"   ❌ Setup failed: {type(exc).__name__}: {exc}")
    sys.exit(1)


test("Vault structure", test_vault)
test("Filesystem scanner", test_scan)
test("File search", test_search)
test("File organizer", test_organize)
test("File rename", test_rename)
test("File copy", test_copy)
test("Folder creation", test_create_folder)
test("File move", test_move)
test("Final index scan", test_final_scan)


# --------------------------------------------------
# Summary
# --------------------------------------------------

print("\n" + "=" * 60)
print("                    SUMMARY")
print("=" * 60)

print(f"✅ Passed : {PASS}")
print(f"❌ Failed : {FAIL}")

if FAIL == 0:
    print("\n🎉 ALL FILE MANAGER TESTS PASSED")
    sys.exit(0)
else:
    print("\n⚠️ SOME TESTS FAILED")
    sys.exit(1)