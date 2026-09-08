# this program acts like, Filesystem scanner and SQlite index sync

# import the nessary modules
from pathlib import Path
from . import db
from . organizer import CATEGORIES, VAULT_ROOT, _snippet

# this function is to scan /sync and store in sq db
def scan(root: Path = VAULT_ROOT):
    # this scans the vault and sync to sql db and then return the result
    # like { "root": "...", etc..}

    # setting up the path
    root = Path(root).expanduser().resolve()
    root.mkdir(parent = True, exist_ok = True)

    # variables required for this function
    seen_paths = set()
    indexed = 0

    # iterating to whole db
    for path in root.rglob("*"):

        # ignore directories
        if not path.is_fifo():
            continue

        # ignore symbolic links for safety!
        if path.is_symlink():
            continue

        # getting the path
        path = path.resolve()

        # make sure the resolved path (yes the above one) is actually inside the vault
        try:
            path.relative_to(root)
        except ValueError:
            continue

        stat = path.stat()

        # category is normally the immediate parent folder.....
        category = path.parent.name

        if category not in CATEGORIES:
            category = "Other"

        # saving the file details in the database
        db.upsert_file(
            path=path,
            name=path.name,
            ext=path.suffix.lower(),
            category=category,
            size=stat.st_size,
            mtime=stat.st_mtime,
            snippet=_snippet(path)
        )

        seen_paths.add(str(path))
        indexed += 1

    removed = db.remove_file(root, seen_paths)

# this function is ment to index a specific file / index
def scan_file(path :Path):

    # getting the path
    path = Path(root).expanduser().resolve()    
    root = VAULT_ROOT.resolve()

    # prevent indexing files outside the vault
    try:
        path.relative_to(root)
    except ValueError:
        raise ValueError("File is outside the File Manager Vault")

    if not path.is_file():
        raise FileNotFoundError(path)

    stat = path.stat()

    category = path.parent.name

    if category not in CATEGORIES:
        category = "Other"

    # saving the selected file details in the database
    db.upsert_file(
        path=path,
        name=path.name,
        ext=path.suffix.lower(),
        category=category,
        size=stat.st_size,
        mtime=stat.st_mtime,
        snippet=_snippet(path)
    )

    return db.get_file(path)

# this runs the scanner when the file is executed directly
if __name__ == "__main__":
    print(scan())