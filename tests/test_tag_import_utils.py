import unittest
import os
import csv
from io import StringIO

# Adjust the path to import tag_import_utils from the parent directory
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from tag_import_utils import parse_productivity_csv

class TestTagImportUtils(unittest.TestCase):

    def test_parse_productivity_csv_empty_input(self):
        csv_content = ""
        existing_tags = []
        new_tags, duplicates, result, errors = parse_productivity_csv(csv_content, existing_tags)
        self.assertEqual(new_tags, [])
        self.assertEqual(duplicates, [])
        self.assertEqual(result["added"], 0)
        self.assertEqual(result["skipped"], 0)
        self.assertEqual(result["errors"], 0)
        self.assertEqual(errors, [])

    def test_parse_productivity_csv_header_only(self):
        csv_content = "Tag Name,Data Type,Address,Description\n"
        existing_tags = []
        new_tags, duplicates, result, errors = parse_productivity_csv(csv_content, existing_tags)
        self.assertEqual(new_tags, [])
        self.assertEqual(duplicates, [])
        self.assertEqual(result["added"], 0)
        self.assertEqual(result["skipped"], 0) # Header is skipped
        self.assertEqual(result["errors"], 0)
        self.assertEqual(errors, [])

    def test_parse_productivity_csv_valid_tags(self):
        csv_content = (
            "Tag Name,Data Type,Address,Description\n"
            "Coil1,Discrete,B0,Test Coil 1\n"
            "Reg1,Int16,W0,Test Register 1\n"
            "Reg2,Int32,L0,Test Register 2\n" # L0 for Int32
            "Reg3,Real,F0,Test Register 3\n"  # F0 for Real
        )
        existing_tags = []
        new_tags, duplicates, result, errors_list = parse_productivity_csv(csv_content, existing_tags)
        
        expected_new_tags = [
            {"name": "Coil1", "type": "Coil", "address": 0, "description": "Test Coil 1", "enabled": True, "scale": 1.0},
            {"name": "Reg1", "type": "Register", "address": 0, "description": "Test Register 1", "enabled": True, "scale": 1.0},
            {"name": "Reg2", "type": "Register", "address": 0, "description": "Test Register 2", "enabled": True, "scale": 1.0}, # Address parsed from L0
            {"name": "Reg3", "type": "Register", "address": 0, "description": "Test Register 3", "enabled": True, "scale": 1.0}, # Address parsed from F0
        ]
        
        self.assertEqual(len(new_tags), 4)
        for i, tag in enumerate(expected_new_tags):
            self.assertDictContainsSubset(tag, new_tags[i])

        self.assertEqual(duplicates, [])
        self.assertEqual(result["added"], 4)
        self.assertEqual(result["skipped"], 1) # Header
        self.assertEqual(result["errors"], 0)
        self.assertEqual(errors_list, [])


    def test_parse_productivity_csv_duplicates_and_existing(self):
        csv_content = (
            "Tag Name,Data Type,Address,Description\n"
            "ExistingTag1,Discrete,B0,Desc1\n" # Duplicate of existing
            "NewCoil,Discrete,B1,Desc2\n"
            "NewCoil,Int16,W1,Desc3\n"         # Duplicate within CSV (name collision)
        )
        existing_tags = [
            {"name": "ExistingTag1", "type": "Coil", "address": 100, "description": "Old Desc"}
        ]
        new_tags, duplicates_list, result, errors_list = parse_productivity_csv(csv_content, existing_tags)
        
        self.assertEqual(len(new_tags), 1)
        self.assertDictContainsSubset(
            {"name": "NewCoil", "type": "Coil", "address": 1, "description": "Desc2"}, 
            new_tags[0]
        )
        
        self.assertEqual(len(duplicates_list), 2) # ExistingTag1 and the second NewCoil
        self.assertIn("ExistingTag1", [d["name"] for d in duplicates_list])
        # The second NewCoil is skipped as a duplicate name from CSV
        self.assertTrue(any(d["name"] == "NewCoil" and "Duplicate tag name found in CSV" in d["reason"] for d in duplicates_list))


        self.assertEqual(result["added"], 1)
        self.assertEqual(result["skipped"], 3) # Header + 2 duplicates
        self.assertEqual(result["errors"], 0)
        self.assertEqual(errors_list, [])


    def test_parse_productivity_csv_invalid_and_missing_data(self):
        csv_content = (
            "Tag Name,Data Type,Address,Description\n"
            "ValidCoil,Discrete,B0,Valid\n"
            "InvalidTypeTag,UnknownType,W0,Invalid Type\n" # Unsupported type
            "MissingAddressTag,Int16,,Missing Address\n"   # Missing address
            ",Discrete,B1,Missing Name\n"                  # Missing name
            "TagWithBadAddress,Discrete,XYZ,Bad Address Format\n" # Bad address format
            "TooFewColumns,Discrete\n"                      # Line with too few columns
            "\n"                                           # Empty line
        )
        existing_tags = []
        new_tags, duplicates, result, errors_list = parse_productivity_csv(csv_content, existing_tags)

        self.assertEqual(len(new_tags), 1)
        self.assertDictContainsSubset(
            {"name": "ValidCoil", "type": "Coil", "address": 0, "description": "Valid"},
            new_tags[0]
        )
        
        self.assertEqual(duplicates, [])
        self.assertEqual(result["added"], 1)
        # Skipped: Header, Empty line
        # Errors: InvalidTypeTag, MissingAddressTag, Missing Name, TagWithBadAddress, TooFewColumns
        self.assertEqual(result["skipped"], 2) 
        self.assertEqual(result["errors"], 5)

        self.assertEqual(len(errors_list), 5)
        error_reasons = [e['reason'] for e in errors_list]
        self.assertIn("Unsupported data type: UnknownType", error_reasons)
        self.assertIn("Address missing or invalid format", error_reasons) # For MissingAddressTag
        self.assertIn("Tag name missing", error_reasons)
        self.assertIn("Address missing or invalid format", error_reasons) # For TagWithBadAddress (XYZ)
        self.assertIn("Incorrect number of columns", error_reasons)


    def test_parse_productivity_csv_address_parsing(self):
        csv_content = (
            "Tag Name,Data Type,Address,Description\n"
            "CoilB10,Discrete,B10,Coil at B10\n"
            "RegW5,Int16,W5,Register at W5\n"
            "RegL100,Int32,L100,Register at L100\n"
            "RegF20,Real,F20,Register at F20\n"
            "CoilBit,Discrete,B0.0,Coil bit style (should take B0)\n"
            "RegInvalid,Int16,W,Invalid W address\n"
            "RegInvalidL,Int32,L,Invalid L address\n"
        )
        existing_tags = []
        new_tags, _, result, errors_list = parse_productivity_csv(csv_content, existing_tags)

        self.assertEqual(len(new_tags), 5)
        self.assertDictContainsSubset({"name": "CoilB10", "address": 10}, new_tags[0])
        self.assertDictContainsSubset({"name": "RegW5", "address": 5}, new_tags[1])
        self.assertDictContainsSubset({"name": "RegL100", "address": 100}, new_tags[2])
        self.assertDictContainsSubset({"name": "RegF20", "address": 20}, new_tags[3])
        self.assertDictContainsSubset({"name": "CoilBit", "address": 0}, new_tags[4]) # B0.0 -> B0

        self.assertEqual(result["added"], 5)
        self.assertEqual(result["errors"], 2)
        self.assertEqual(len(errors_list), 2)
        self.assertTrue(any("RegInvalid" in e['tag_name'] and "Address missing or invalid format" in e['reason'] for e in errors_list))
        self.assertTrue(any("RegInvalidL" in e['tag_name'] and "Address missing or invalid format" in e['reason'] for e in errors_list))


    # Helper for assertDictContainsSubset for older Python versions if needed,
    # but unittest.TestCase should have it implicitly via other assertions.
    def assertDictContainsSubset(self, subset, dictionary, msg=None):
        for key, value in subset.items():
            self.assertIn(key, dictionary, msg=f"Key '{key}' not found in {dictionary} (checking subset {subset})")
            self.assertEqual(dictionary[key], value, msg=f"Value for key '{key}' mismatch: expected {value}, got {dictionary[key]} (checking subset {subset})")


if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
