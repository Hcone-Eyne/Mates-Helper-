"""Tests for File_Manager/preferences.py."""

import sys
import os
import json
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from File_Manager.preferences import DEFAULT_RULES, category_for, record_override, _load, _save


class TestPreferencesDefaults:
    """Test DEFAULT_RULES dictionary."""

    def test_default_rules_contains_common_extensions(self):
        assert ".pdf" in DEFAULT_RULES
        assert ".docx" in DEFAULT_RULES
        assert ".py" in DEFAULT_RULES
        assert ".png" in DEFAULT_RULES
        assert ".mp3" in DEFAULT_RULES
        assert ".mp4" in DEFAULT_RULES
        assert ".zip" in DEFAULT_RULES

    def test_default_rules_categories(self):
        assert DEFAULT_RULES[".pdf"] == "Documents"
        assert DEFAULT_RULES[".py"] == "Code"
        assert DEFAULT_RULES[".png"] == "Images"
        assert DEFAULT_RULES[".mp3"] == "Audio"
        assert DEFAULT_RULES[".mp4"] == "Video"
        assert DEFAULT_RULES[".zip"] == "Archives"

    def test_default_rules_no_empty_values(self):
        for ext, cat in DEFAULT_RULES.items():
            assert cat
            assert isinstance(cat, str)


class TestCategoryFor:
    """Test category_for function."""

    def test_known_extension_returns_category(self):
        assert category_for(".pdf") == "Documents"
        assert category_for(".PY") == "Code"  # case insensitive
        assert category_for(".Png") == "Images"
        assert category_for(".MP3") == "Audio"

    def test_unknown_extension_returns_other(self):
        assert category_for(".xyz") == "Other"
        assert category_for(".unknown") == "Other"
        assert category_for("") == "Other"

    def test_extension_without_dot(self):
        # The function expects extensions with dot prefix
        assert category_for("pdf") == "Other"
        assert category_for("py") == "Other"

    def test_override_takes_precedence(self):
        # Test by directly manipulating the prefs file
        import File_Manager.preferences as prefs_module
        original_path = prefs_module.PREFS_PATH
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"overrides": {".xyz": "CustomCategory"}}, f)
            temp_path = Path(f.name)
        
        try:
            prefs_module.PREFS_PATH = temp_path
            # Reload the module's _load function will pick up the new path
            assert category_for(".xyz") == "CustomCategory"
        finally:
            prefs_module.PREFS_PATH = original_path
            temp_path.unlink(missing_ok=True)


class TestRecordOverride:
    """Test record_override function."""

    def test_record_override_creates_file(self):
        import File_Manager.preferences as prefs_module
        original_path = prefs_module.PREFS_PATH
        
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir) / "user_profs.json"
            prefs_module.PREFS_PATH = temp_path
            
            record_override(".test", "TestCategory")
            
            assert temp_path.exists()
            with open(temp_path) as f:
                data = json.load(f)
            assert data["overrides"][".test"] == "TestCategory"
        
        prefs_module.PREFS_PATH = original_path

    def test_record_override_lowercases_extension(self):
        import File_Manager.preferences as prefs_module
        original_path = prefs_module.PREFS_PATH
        
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir) / "user_profs.json"
            prefs_module.PREFS_PATH = temp_path
            
            record_override(".TEST", "TestCategory")
            
            with open(temp_path) as f:
                data = json.load(f)
            assert ".test" in data["overrides"]
            assert data["overrides"][".test"] == "TestCategory"
        
        prefs_module.PREFS_PATH = original_path

    def test_record_override_updates_existing(self):
        import File_Manager.preferences as prefs_module
        original_path = prefs_module.PREFS_PATH
        
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir) / "user_profs.json"
            prefs_module.PREFS_PATH = temp_path
            
            record_override(".test", "FirstCategory")
            record_override(".test", "SecondCategory")
            
            with open(temp_path) as f:
                data = json.load(f)
            assert data["overrides"][".test"] == "SecondCategory"
        
        prefs_module.PREFS_PATH = original_path


class TestLoadSave:
    """Test _load and _save internal functions."""

    def test_load_returns_empty_when_no_file(self):
        import File_Manager.preferences as prefs_module
        original_path = prefs_module.PREFS_PATH
        
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir) / "nonexistent.json"
            prefs_module.PREFS_PATH = temp_path
            
            result = _load()
            assert result == {"overrides": {}}
        
        prefs_module.PREFS_PATH = original_path

    def test_load_reads_existing_file(self):
        import File_Manager.preferences as prefs_module
        original_path = prefs_module.PREFS_PATH
        
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir) / "user_profs.json"
            prefs_module.PREFS_PATH = temp_path
            
            with open(temp_path, 'w') as f:
                json.dump({"overrides": {".custom": "CustomCat"}}, f)
            
            result = _load()
            assert result["overrides"][".custom"] == "CustomCat"
        
        prefs_module.PREFS_PATH = original_path

    def test_save_writes_file(self):
        import File_Manager.preferences as prefs_module
        original_path = prefs_module.PREFS_PATH
        
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir) / "user_profs.json"
            prefs_module.PREFS_PATH = temp_path
            
            _save({"overrides": {".saved": "SavedCat"}})
            
            assert temp_path.exists()
            with open(temp_path) as f:
                data = json.load(f)
            assert data["overrides"][".saved"] == "SavedCat"
        
        prefs_module.PREFS_PATH = original_path