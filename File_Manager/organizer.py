# this program decides which category folder a file belongs in and moves it there
# cmd: python organizer.py
# cmd: from organizer import organize_file; organize_file(Path("./some-file.pdf"))
# cmd: from organizer import move_and_learn; move_and_learn(Path("./some-file.pdf"), "Notes")

# importing necessary modules
import shutil
from pathlib import Path

from File_Manager import db, preferences

# initialising those paths
VAULT_ROOT = Path(__file__).resolve().parent / "Vault"
INBOX = VAULT_ROOT / "Inbox"  # can be used like drag-and-drop

# defining categories
CATEGORIES = ["Documents", "Notes", "Code", "Images", "Audio", "Video", "Archives", "Other"]

# this function creates the main inbox and all category folders if they don't already exist.
def ensure_vault():
    INBOX.mkdir(parents=True, exist_ok=True)
    for cat in CATEGORIES:
        (VAULT_ROOT / cat).mkdir(parents=True, exist_ok=True)

# this function reads a file and returns the first 500 characters of its text. If it can't read the file, it returns an empty string.
def _snippet(path, max_chars=500):
    try:
        return path.read_text(errors="ignore")[:max_chars]
    except Exception:
        return ""

# this function is responsible for automatically organizes a file into the correct category folder based on its file extension
def organize_file(path: Path):
    # cmd: organize_file(Path("/path/to/file.pdf"))
    # finding the file extension and the category linked to it
    ext = path.suffix.lower()
    category = preferences.category_for(ext)
    dest_dir = VAULT_ROOT / category
    dest_dir.mkdir(parents=True, exist_ok=True)

    # making a new name when a file with the same name already exists
    dest_path = dest_dir / path.name
    counter = 1
    while dest_path.exists():
        dest_path = dest_dir / f"{path.stem}_{counter}{path.suffix}"
        counter += 1

    # moving the file and saving its details in the database
    shutil.move(str(path), str(dest_path))
    stat = dest_path.stat()
    db.upsert_file(dest_path, dest_path.name, ext, category, stat.st_size, stat.st_mtime, _snippet(dest_path))
    return dest_path, category

# this function is responsible for manually moves a file to a chosen category, handles duplicate filenames, remembers that category choice for that file type
def move_and_learn(current_path: Path, new_category: str):
    # cmd: move_and_learn(Path("/path/to/file.pdf"), "Documents")
    # using Other when the selected category is not allowed
    new_category = new_category if new_category in CATEGORIES else "Other"
    dest_dir = VAULT_ROOT / new_category
    dest_dir.mkdir(parents=True, exist_ok=True)

    # preparing the destination path and handling duplicate filenames
    dest_path = dest_dir / current_path.name
    if dest_path.exists():
        suffix = current_path.suffix.lower()
        base = current_path.stem
        counter = 1
        while dest_path.exists():
            dest_path = dest_dir / f"{base}_{counter}{suffix}"
            counter += 1

    # moving the file and remembering the user's category choice
    shutil.move(str(current_path), str(dest_path))
    preferences.record_override(current_path.suffix, new_category)

    # updating the database with the file's new location
    stat = dest_path.stat()
    db.remove_file(current_path)
    db.upsert_file(dest_path, dest_path.name, current_path.suffix.lower(), new_category,
    stat.st_size, stat.st_mtime, _snippet(dest_path))
    return dest_path


if __name__ == "__main__":
    ensure_vault()
   