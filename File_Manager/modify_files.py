import shutil
import threading
from pathlib import Path

from agent.fox.runtime.executor import FileActionExecutor
from agent.fox.security import FoxSecurityBoundary, FoxSecurityError

from . import db, organizer
from .organizer import CATEGORIES, VAULT_ROOT, _snippet

_DEFAULT_VAULT_ROOT = VAULT_ROOT
_FS_LOCK = threading.RLock()


def _get_vault_root() -> Path:
    if VAULT_ROOT != _DEFAULT_VAULT_ROOT:
        return Path(VAULT_ROOT)
    if organizer.VAULT_ROOT != _DEFAULT_VAULT_ROOT:
        return Path(organizer.VAULT_ROOT)
    return Path(VAULT_ROOT)


def _vault_executor(root: Path) -> tuple[FoxSecurityBoundary, FileActionExecutor]:
    boundary = FoxSecurityBoundary(root, create=True, enforce_area_policy=False)
    return boundary, FileActionExecutor(boundary)


# this function handles the path, like assign the correct path and stores it in vault.
def _resolve_inside_vault(path, *, allow_trash: bool = False):
    if path is None or not str(path).strip():
        raise ValueError("Path is outside the File Manager Vault: empty path")

    root_raw = _get_vault_root().expanduser()
    root = root_raw.resolve()
    root.mkdir(parents=True, exist_ok=True)

    raw_candidate = Path(path).expanduser()
    candidate = raw_candidate if raw_candidate.is_absolute() else (root_raw / raw_candidate)

    if candidate.is_symlink() or raw_candidate.is_symlink():
        raise ValueError(
            f"Path is outside the File Manager Vault (symlink not allowed): {path}"
        )

    boundary, _ = _vault_executor(root)
    try:
        resolved = boundary.validate_path(candidate, must_exist=False)
    except FoxSecurityError as exc:
        raise ValueError(
            f"Path is outside the File Manager Vault: {path}"
        ) from exc

    try:
        rel = resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            f"Path is outside the File Manager Vault: {path}"
        ) from exc

    cur = root
    for part in rel.parts:
        cur = cur / part
        if cur.is_symlink():
            raise ValueError(
                f"Path is outside the File Manager Vault (symlink not allowed): {path}"
            )

    if not allow_trash and boundary.is_trash_path(resolved):
        raise ValueError(
            f"Path is inside Vault trash; use restore_file: {path}"
        )

    return resolved

# this function is ment for create a file/folder location where the new item can be saved without overwriting and prevent the clashing of the file..... 
def _unique_destination(path_destination):

    # the path!
    path_destination = Path(path_destination)

    # check if its exists
    if not path_destination.exists():
        return path_destination

    counter = 1

    while True:
        candidate = (
            path_destination.parent/ f"{path_destination.stem}_{counter}{path_destination.suffix}"
        ) # and / is a feature of pathlib not division

        if not candidate.exists():
            return candidate

        counter += 1

# this function is used to move files inside of the vault
def move_file(source, destination):
    with _FS_LOCK:
        # getting data from another function!
        source = _resolve_inside_vault(source)
        destination = _resolve_inside_vault(destination)

        # checks for exists of file
        if not source.exists():
            raise FileNotFoundError(source)

        # checks in dir!
        if source.is_dir():
            raise IsADirectoryError(source)

        destination.parent.mkdir(parents=True, exist_ok=True)

        destination = _unique_destination(destination)

        shutil.move(str(source), str(destination))

        try:
            db.remove_file(source)
        except Exception:
            pass

        stat = destination.stat()

        try:
            db.upsert_file(
                destination,
                destination.name,
                destination.suffix.lower(),
                destination.parent.name,
                stat.st_size,
                stat.st_mtime
            )
        except Exception:
            pass

        return destination

# this function is all about copy file into the vault!
def copy_file(source, destination):
    with _FS_LOCK:
        # fetch the required source
        source = _resolve_inside_vault(source)
        destination = _resolve_inside_vault(destination)

        # check for existance
        if not source.exists():
            raise FileNotFoundError(source)

        # checks if its present in dir
        if source.is_dir():
            raise IsADirectoryError(source)

        destination.parent.mkdir(parents=True, exist_ok=True)

        destination = _unique_destination(destination)

        shutil.copy2(str(source), str(destination))

        stat = destination.stat()

        try:
            db.upsert_file(
                destination,
                destination.name,
                destination.suffix.lower(),
                destination.parent.name,
                stat.st_size,
                stat.st_mtime
            )
        except Exception:
            pass

        return destination

# this function is uised to rename file without chaning the directory!
def rename_file(path, new_name):
    with _FS_LOCK:
        # get the path!
        path = _resolve_inside_vault(path)

        # check for file exits
        if not path.exists():
            raise FileNotFoundError(path)

        # check if dir is valid!
        if path.is_dir():
            raise IsADirectoryError(path)

        # checking if the changed name is new name or not
        if not new_name or Path(new_name).name != new_name:
            raise ValueError("new_name must be filename, not a path!")

        destination = path.parent / new_name
        destination = _unique_destination(destination)

        # rename if everything is good!
        path.rename(destination)

        stat = destination.stat()

        try:
            db.upsert_file(
                destination,
                destination.name,
                destination.suffix.lower(),
                destination.parent.name,
                stat.st_size,
                stat.st_mtime
            )
        except Exception:
            pass

        return destination

# this functino handles the delection process of a file!
# Moves the file into Vault trash (.fox_trash) via the shared Fox
# FileActionExecutor rather than permanently unlinking it.
def delete_file(path):
    with _FS_LOCK:
        root = _get_vault_root().expanduser().resolve()
        resolved = _resolve_inside_vault(path, allow_trash=False)

        if resolved == root or resolved.is_dir():
            raise IsADirectoryError(resolved)

        if not resolved.exists():
            raise FileNotFoundError(resolved)

        _, executor = _vault_executor(root)
        try:
            result = executor.execute("delete_file", {"path": str(resolved)})
        except FoxSecurityError as exc:
            raise ValueError(str(exc)) from exc

        try:
            db.remove_file(resolved)
        except Exception:
            pass

        return root / result["trash_path"]


# this function restores a trashed file back into the Vault!
def restore_file(path, destination=None):
    with _FS_LOCK:
        root = _get_vault_root().expanduser().resolve()
        candidate = _resolve_inside_vault(path, allow_trash=True)
        boundary, executor = _vault_executor(root)

        if candidate == root or candidate == boundary.trash_dir:
            raise IsADirectoryError(candidate)

        if boundary.is_trash_path(candidate):
            trash_src = candidate
        else:
            rel = candidate.relative_to(root)
            trash_src = executor.find_trash_entry(rel)

        if trash_src.is_dir():
            raise IsADirectoryError(trash_src)

        if not trash_src.exists():
            raise FileNotFoundError(path)

        args = {"path": str(trash_src)}
        if destination is not None:
            dest_resolved = _resolve_inside_vault(destination, allow_trash=False)
            if dest_resolved == root:
                raise IsADirectoryError(dest_resolved)
            args["destination"] = str(dest_resolved)

        try:
            result = executor.execute("restore_file", args)
        except FoxSecurityError as exc:
            raise ValueError(str(exc)) from exc

        restored_path = root / result["restored_to"]
        stat = restored_path.stat()
        category = restored_path.parent.name
        if category not in CATEGORIES:
            category = "Other"

        try:
            db.upsert_file(
                restored_path,
                restored_path.name,
                restored_path.suffix.lower(),
                category,
                stat.st_size,
                stat.st_mtime,
                _snippet(restored_path),
            )
        except Exception:
            pass

        return restored_path


# this function handles the creating of folder!
def create_folder(path):
    with _FS_LOCK:
        # get the path
        path = _resolve_inside_vault(path)

        # create the folder!
        path.mkdir(parents=True, exist_ok=True)

        return path
