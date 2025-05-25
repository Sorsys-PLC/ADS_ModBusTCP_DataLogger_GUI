import unittest
import os
import json
import hashlib
from datetime import datetime
from unittest.mock import patch, mock_open

# Adjust the path to import utils from the parent directory
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils import calculate_config_hash, get_db_path, load_config, CONFIG_FILE, PLC_LOGS_DIR, initialize_db

# Temporarily set DB_PATH for tests if it's not already set by initialize_db,
# or if initialize_db has side effects we want to control/avoid in some tests.
# For get_db_path, it relies on PLC_LOGS_DIR which is fine.
# initialize_db() might be needed if other utils functions depend on DB_PATH being set.

class TestUtils(unittest.TestCase):

    def setUp(self):
        # This can be used to ensure a clean state for each test, e.g., removing dummy files
        self.dummy_config_path = CONFIG_FILE # utils.CONFIG_FILE
        if os.path.exists(self.dummy_config_path):
            os.remove(self.dummy_config_path)

    def tearDown(self):
        # Clean up any files created during tests
        if os.path.exists(self.dummy_config_path):
            os.remove(self.dummy_config_path)
        # Could also clean up PLC_LOGS_DIR if tests create many files there,
        # but for now, get_db_path only generates paths, doesn't create files.

    def test_calculate_config_hash(self):
        config1 = {"setting1": "value1", "setting2": 123, "tags": [{"name": "T1", "address": 0}]}
        config2 = {"setting2": 123, "tags": [{"name": "T1", "address": 0}], "setting1": "value1"} # Order should not matter
        config3 = {"setting1": "value1", "setting2": 456, "tags": [{"name": "T2", "address": 1}]}

        hash1 = calculate_config_hash(config1)
        hash2 = calculate_config_hash(config2)
        hash3 = calculate_config_hash(config3)

        self.assertEqual(hash1, hash2, "Hashes for equivalent configs should be the same.")
        self.assertNotEqual(hash1, hash3, "Hashes for different configs should be different.")
        self.assertIsInstance(hash1, str, "Hash should be a string.")
        self.assertEqual(len(hash1), 8, "Hash should be 8 characters long (default).")

        # Test with nested dictionary and list
        nested_config1 = {"setting1": "value1", "nested": {"n1": "v1", "n2": "v2"}, "list": [1, 2, 3]}
        nested_config2 = {"list": [1, 2, 3], "setting1": "value1", "nested": {"n2": "v2", "n1": "v1"}}
        nested_config3 = {"setting1": "value1", "nested": {"n1": "v1", "n2": "DIFFERENT"}, "list": [1, 2, 4]}
        
        hash_n1 = calculate_config_hash(nested_config1)
        hash_n2 = calculate_config_hash(nested_config2)
        hash_n3 = calculate_config_hash(nested_config3)

        self.assertEqual(hash_n1, hash_n2)
        self.assertNotEqual(hash_n1, hash_n3)
        
        # Test with empty config
        empty_config_hash = calculate_config_hash({})
        self.assertIsNotNone(empty_config_hash)
        self.assertEqual(len(empty_config_hash), 8)

    @patch('utils.datetime')
    def test_get_db_path(self, mock_datetime):
        fixed_now = datetime(2024, 1, 15, 12, 0, 0)
        mock_datetime.now.return_value = fixed_now
        
        config_hash = "abcdef12"
        expected_filename = f"plc_data_2024-01-15_120000_config-{config_hash}.db"
        
        # Ensure PLC_LOGS_DIR exists for the test (utils.get_db_path creates it)
        # We can spy on os.makedirs if we want to ensure it's called, but for now, just check path
        
        expected_path = os.path.join(PLC_LOGS_DIR, expected_filename)
        actual_path = get_db_path(config_hash)
        self.assertEqual(actual_path, expected_path)
        
        # Check if the directory was created by get_db_path
        self.assertTrue(os.path.exists(PLC_LOGS_DIR))


    def test_load_config_file_exists_valid_json(self):
        dummy_config_data = {
            "global_settings": {"ip": "10.0.0.1", "port": 5020},
            "tags": [{"name": "MyTag", "address": 10, "type": "Register", "scale": 0.1}]
        }
        with open(self.dummy_config_path, 'w') as f:
            json.dump(dummy_config_data, f, indent=4)

        loaded_data = load_config()
        self.assertEqual(loaded_data, dummy_config_data)

    def test_load_config_file_not_exists(self):
        # Ensure file does not exist (setUp should handle this)
        self.assertFalse(os.path.exists(self.dummy_config_path))

        loaded_data = load_config()
        # It should return the default config structure
        self.assertIn("global_settings", loaded_data)
        self.assertIn("tags", loaded_data)
        self.assertEqual(loaded_data["global_settings"]["ip"], "192.168.0.10") # Check a default value
        self.assertEqual(loaded_data["tags"], [])

    @patch("builtins.open", new_callable=mock_open)
    @patch("json.load")
    @patch("os.path.exists") # Also mock os.path.exists
    def test_load_config_file_exists_invalid_json(self, mock_path_exists, mock_json_load, mock_file_open):
        mock_path_exists.return_value = True # Simulate file exists
        # The actual content read by open doesn't matter here since json.load is mocked
        mock_file_open.return_value.read.return_value = "this is not valid json"
        mock_json_load.side_effect = json.JSONDecodeError("Syntax error", "doc", 0)

        loaded_data = load_config()
        # It should return the default config structure due to JSONDecodeError
        self.assertIn("global_settings", loaded_data)
        self.assertIn("tags", loaded_data)
        self.assertEqual(loaded_data["global_settings"]["port"], 502) # Check another default
        self.assertEqual(loaded_data["tags"], [])
        
        # Ensure that open was called with the correct file path
        mock_file_open.assert_called_once_with(self.dummy_config_path, "r")


    @patch("builtins.open")
    @patch("os.path.exists")
    def test_load_config_file_exists_io_error_on_read(self, mock_path_exists, mock_file_open):
        mock_path_exists.return_value = True
        mock_file_open.side_effect = IOError("Failed to read file")

        loaded_data = load_config()
        # It should return the default config structure due to IOError
        self.assertIn("global_settings", loaded_data)
        self.assertIn("tags", loaded_data)
        self.assertEqual(loaded_data["global_settings"]["polling_interval"], 0.5)
        self.assertEqual(loaded_data["tags"], [])


if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False) # exit=False for running in some environments
                                                            # argv is for compatibility with some test runners
                                                            # if run directly, it's fine.
                                                            # Consider removing if it causes issues with `discover`
                                                            # For `python -m unittest discover tests`, this is fine.
