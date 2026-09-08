# this progam is used to modify files!

# importing the nessary modules
import shutil
from pathlib import Path

from .import db
from .organizer import VAULT_ROOT

# this function handles the path, like assign the correct path and stores it in vault.
def _resolve_inside_vault(path):

    # getting the path
    path = Path(path).expanduser().resolve()
    root = VAULT_ROOT.resolve()

    try:
        path.resolve_to(root)
    except ValueError:
        raise ValueError(
            f"Path is outside the File Manager Vault: {path}"
        )

    return path

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

    # getting data from another function!
    source = _resolve_inside_vault(source)
    destination = _resolve_inside_vault(destination)

    # checks for exists of file
    if not source.exists():
        raise FileNotFoundError(source)

    # checks in dir!
    if source.is_dir():
        raise IsADirectoryError(source)

    destination.parent.mkdir(parent = True, exists_ok = True)

    destination = _unique_destination(destination)

    shutil.move(str(source, str(destination)))

    db.remove_file(source)

    stat = destination.stat()

    db.upsert_file(
        destination,
        destination.name,
        destination.suffix.lower(),
        destination.parent.name,
        stat.st_size,
        stat.st_mtime
    )

    return destination

# this function is all about copy file into the vault!
def copy_file(source, destination):

    # fetch the required source
    source = _resolve_inside_vault(source)
    destination = _resolve_inside_vault(destination)

    # check for existance
    if not source.exists():
        raise FileNotFoundError(source)

    # checks if its present in dir
    if source.is_dir():
        raise IsADirectoryError(source)

    destination.parent.mkdir(parent = True, exist_ok = True)

    destination = _unique_destination(destination)

    shutil.copy2(str(source), str(destination))

    stat = destination.stat()

    db.upsert_file(
        destination,
        destination.name,
        destination.suffix.lower(),
        destination.parent.name,
        stat.st_size,
        stat.st_mtime
    )

    return destination

# this function is uised to rename file without chaning the directory!
def rename_file(path, new_name):

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
    path.rename_file(path)

    stat = destination.stat()

    db.upsert_file(
        destination,
        destination.name,
        destination.suffix.lower(),
        destination.parent.name,
        stat.st_size,
        stat.st_mtime
    )

    return destination

# this functino handles the delection process of a file!
# Todo: This is Permanent Deletion of file, add trash bin feature!
def delete_file(path):

    # get the path!
    path = _resolve_inside_vault(path)

    # check for exits
    if not path.exists():
        return False
    if path.is_dir():
        raise IsADirectoryError(path)

    # executes only if conditions all are good!
    path.unlink()

    db.remove_file(path)

    return True

# this function handles the creating of folder!
def create_folder(path):

    # get the path
    path = _resolve_inside_vault(path)

    # create the folder!
    path.mkdir(parent = True, exist_ok= True)

    return path
