# thi progam is used to remember how i like files organised, so Fox guess will be improved over the time@

# importing nessary moduels
import json
from pathlib import Path

# setting up path route with pathlib
PREFS_PATH = Path(__file__).resolve().parent / "user_profs.json"

# File organisation Rules
DEFAULT_RULES = {
    ".pdf": "Documents", ".docx": "Documents", ".doc": "Documents", ".txt": "Notes",
    ".md": "Notes", ".csv": "Documents", ".xlsx": "Documents",
    ".py": "Code", ".js": "Code", ".ipynb": "Code", ".java": "Code", ".c": "Code", ".cpp": "Code",
    ".png": "Images", ".jpg": "Images", ".jpeg": "Images", ".gif": "Images", ".svg": "Images",
    ".mp3": "Audio", ".wav": "Audio", ".m4a": "Audio",
    ".mp4": "Video", ".mov": "Video", ".mkv": "Video",
    ".zip": "Archives", ".tar": "Archives", ".gz": "Archives", ".rar": "Archives",
}

# this function is going to load the preference from json file
def _load():
    if PREFS_PATH.exists():
        return json.loads(PREFS_PATH.read_text())
    return {"overrides": {}}

# this function is used to save preferences
def _save(prefs):
    PREFS_PATH.write_text(json.dumps(prefs, indent = 2))

# this function used to determine the category for a file extension
def category_for(ext):
    prefs = _load()
    ext = ext.lower()
    if ext in prefs["overrides"]:
        return prefs["overrides"][ext]
    return DEFAULT_RULES.get(ext, "Other")

# this function going to store records (user defined category OVERRIDED!)
def record_override(ext, category):
    prefs = _load()
    prefs["overrides"][ext.lower()] = category
    _save(prefs)