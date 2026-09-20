# importing the nessary modules
from pathlib import Path

# master Root!
FOX_SPACE_ROOT = Path(__file__).resolve().parent

# retun the root dir of fox's isolated system!
def get_fox_space():
    return FOX_SPACE_ROOT

def ensure_fox_space():
    directories = (
        "system",
        "apps",
        "workspace",
        "storage",
        "config",
        "trash"
    )

    for directory in directories:
        (FOX_SPACE_ROOT / directory).mkdir(parents = True, exist_ok = True)

    return FOX_SPACE_ROOT