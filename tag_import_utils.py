import csv
import logging

logger = logging.getLogger(__name__) # Module-level logger

def parse_productivity_csv(file_path: str, existing_tags: list[dict]) -> tuple[list[dict], list[dict], dict, list[dict]]:
    """
    Parses a CSV file exported from a Productivity Suite PLC programming software.

    This function is designed to read a CSV file that typically contains tag
    information, including tag names, Modbus addresses, and data types. It
    extracts relevant information to create a list of tag dictionaries suitable
    for use in the PLC Logger application.

    The function expects a specific CSV structure, typically with:
    - Two header lines to be skipped.
    - Tag Name in column B (index 1).
    - Data Type in column C (index 2).
    - Modbus Start Address in column E (index 4).
    - User ID (often used as description) in column A (index 0).

    It attempts to map PLC data types (e.g., "BOOL", "INT16") to Modbus types
    ("Coil" or "Register") and calculates 0-based Modbus addresses.

    The function handles various scenarios:
    - Skips rows with insufficient columns or empty/invalid tag names/addresses.
    - Skips tags that are function block instances (e.g., "Timer()").
    - Skips tags with Modbus address 0 or specific system coils if defined.
    - Attempts to infer Modbus type (Coil/Register) if not directly clear from data type.
    - Checks for duplicates against `existing_tags` based on address/type and name.
    - Checks for duplicates within the CSV file itself by name.

    Args:
        file_path: The absolute path to the CSV file to parse.
        existing_tags: A list of tag dictionaries that are already configured in the
                       application. This is used for duplicate checking.

    Returns:
        A tuple containing:
        - `new_tags` (list[dict]): A list of newly parsed tag dictionaries that are
          not duplicates of existing tags and are not duplicates within the CSV.
        - `duplicates_info` (list[dict]): A list of dictionaries, where each entry
          provides the name and reason for a tag from the CSV that was skipped
          due to being a duplicate (either of an existing tag or within the CSV).
        - `result` (dict): A dictionary summarizing the parsing outcome with various
          counts (e.g., "added", "skipped_no_address", "errors").
        - `errors_list` (list[dict]): A list of dictionaries detailing rows that
          caused errors during parsing (e.g., insufficient columns, file not found).
    """
    logger.info(f"Starting CSV parsing for file: {file_path}")
    new_tags = []
    duplicates_info = [] # Store info about duplicates, not just the tags themselves
    errors_list = []     # Store info about errors encountered

    # Counters for result summary
    imported_count = 0
    skipped_header_count = 0
    skipped_no_address_count = 0
    skipped_unsupported_type_count = 0
    skipped_trigger_coil_count = 0
    skipped_invalid_address_count = 0
    skipped_duplicate_existing_count = 0
    skipped_duplicate_in_csv_count = 0 # For duplicates within the CSV itself by name
    error_count = 0

    existing_addr_type_keys = {(tag["address"], tag["type"].lower()) for tag in existing_tags}
    existing_names_lower = {tag["name"].lower() for tag in existing_tags}
    
    # Keep track of names already added from this CSV to check for intra-CSV duplicates
    names_from_this_csv_lower = set()

    try:
        with open(file_path, newline='', encoding='utf-8-sig') as csvfile: # Use utf-8-sig for BOM
            reader = csv.reader(csvfile)
            
            # Skip header lines - Productivity Suite CSVs typically have 2 header lines.
            try:
                next(reader) # Skip "Project Name: ..."
                next(reader) # Skip "Tag Database,Exported On: ..."
                skipped_header_count = 2
            except StopIteration:
                logger.warning("CSV file appears to be empty or has less than 2 header lines.")
                # No actual error string to return here, result dict will show 0 imported.
                # To match original behavior of returning error string on generic exception:
                # We could raise a ValueError here, but let's try to return structured info.
                errors_list.append({"tag_name": "N/A", "reason": "CSV file empty or too short (missing headers)."})
                error_count +=1
                # Fall through to return empty lists and result dict below

            line_number = skipped_header_count + 1 # Start counting after headers
            for row in reader:
                line_number += 1
                if not row or len(row) < 17: # Ensure row has enough columns for expected data
                    logger.warning(f"Skipping line {line_number}: Insufficient columns (expected at least 17, got {len(row)}). Row: {row}")
                    errors_list.append({"tag_name": "N/A", "reason": f"Line {line_number}: Insufficient columns."})
                    error_count += 1
                    continue

                tag_name = row[1].strip() # "Tag Name"
                modbus_start_str = row[4].strip() # "Modbus Start"
                # data_type_str = row[16].strip() if len(row) > 16 else "" # "Data Type" - original
                data_type_str = row[2].strip() # "Data Type" is actually column C (index 2) in P3K CSV

                # Skip if tag name is empty or looks like a function block instance
                if not tag_name or tag_name.endswith("()"):
                    logger.debug(f"Skipping line {line_number}: Empty tag name or function block instance '{tag_name}'.")
                    continue

                if not modbus_start_str or modbus_start_str == "0": # No Modbus address or address is 0
                    logger.debug(f"Skipping tag '{tag_name}' (line {line_number}): No Modbus address ('{modbus_start_str}').")
                    skipped_no_address_count += 1
                    continue
                
                # Determine Modbus type and parse address
                # Productivity Suite Modbus Addressing:
                # Coils (Discrete Output/Input): 0xxxxx (e.g., 000001 is address 0)
                # Registers (Holding Registers): 4xxxxx (e.g., 400001 is address 0)
                
                tag_type = None
                address = None

                # Try to determine type from data_type_str first, then from Modbus address prefix
                # P-Series Data Types: Bool, Int8, UInt8, Int16, UInt16, Int32, UInt32, Float32, Float64, String...
                # For Modbus, we are typically interested in Coils (Bool) and Registers (Int16/UInt16/Int32/UInt32/Float32)
                
                # Simplified type mapping based on common Modbus usage
                if data_type_str.upper() in ("BOOL", "BIT"):
                    tag_type = "Coil"
                elif data_type_str.upper() in ("INT16", "UINT16", "INT32", "UINT32", "FLOAT32", "BCD16", "BCD32"): # Common register types
                    tag_type = "Register"
                # Add more specific mappings if needed, e.g. differentiating between Int16 and Int32 for address calculation if needed.
                # The provided code used column 16 (P2000 style?), which is different from P3000/P1000.
                # For P3K CSV, "Data Type" is column C (index 2). "User Data Type" is col D (index 3).
                # The example logic from original code seems to be for P2000 (row[16] and complex base_type logic).
                # This refactoring will assume a P3000/P1000 style CSV for now based on typical exports.
                # If P2000 style is needed, the column indices and type parsing logic would need to be different.

                try:
                    modbus_addr_int = int(modbus_start_str)
                    if 1 <= modbus_addr_int <= 199999: # Typically Coils (0xxxx or 1xxxx in some systems)
                        if tag_type is None: tag_type = "Coil" # Infer if not set by data_type_str
                        address = modbus_addr_int - 1 # 0-based addressing
                        if address == 0 and tag_name.upper() == "SYSTEM_TRIGGER_COIL": # Example: Skip a specific system coil
                             logger.debug(f"Skipping system trigger coil '{tag_name}' at address 0.")
                             skipped_trigger_coil_count +=1
                             continue
                    elif 300001 <= modbus_addr_int <= 399999: # Input Registers (less common for control)
                         if tag_type is None: tag_type = "Register"
                         address = modbus_addr_int - 300001
                    elif 400001 <= modbus_addr_int <= 499999: # Holding Registers
                        if tag_type is None: tag_type = "Register"
                        address = modbus_addr_int - 400001
                    else:
                        logger.warning(f"Skipping tag '{tag_name}' (line {line_number}): Unsupported Modbus address range '{modbus_start_str}'.")
                        skipped_unsupported_type_count += 1
                        continue
                except ValueError:
                    logger.warning(f"Skipping tag '{tag_name}' (line {line_number}): Invalid Modbus address format '{modbus_start_str}'.")
                    skipped_invalid_address_count += 1
                    continue

                if tag_type is None: # If type could not be determined
                    logger.warning(f"Skipping tag '{tag_name}' (line {line_number}): Could not determine tag type from data type '{data_type_str}' or Modbus address '{modbus_start_str}'.")
                    skipped_unsupported_type_count += 1
                    continue
                
                # Create tag dictionary
                # Default scale and description can be added here or by the calling GUI
                tag_dict = {
                    "name": tag_name,
                    "address": address,
                    "type": tag_type,
                    "enabled": True, # Default to enabled
                    "scale": 1.0,    # Default scale
                    "description": row[0].strip() if row and row[0] else "" # "User ID" often used as description
                }

                # Check for duplicates (address/type against existing tags)
                tag_addr_type_key = (tag_dict["address"], tag_dict["type"].lower())
                if tag_addr_type_key in existing_addr_type_keys:
                    logger.info(f"Tag '{tag_name}' (Addr: {address}, Type: {tag_type}) is a duplicate (address/type) of an existing tag. Skipping.")
                    duplicates_info.append({"name": tag_name, "reason": "Duplicate address/type with existing tag."})
                    skipped_duplicate_existing_count += 1
                    continue
                
                # Check for duplicate name (against existing and already processed from this CSV)
                tag_name_lower = tag_name.lower()
                if tag_name_lower in existing_names_lower:
                    logger.info(f"Tag name '{tag_name}' conflicts with an existing tag name (case-insensitive). Skipping.")
                    duplicates_info.append({"name": tag_name, "reason": "Duplicate name (case-insensitive) with existing tag."})
                    skipped_duplicate_existing_count += 1 # Or a different counter if needed
                    continue
                
                if tag_name_lower in names_from_this_csv_lower:
                    logger.info(f"Tag name '{tag_name}' is a duplicate within this CSV file (case-insensitive). Skipping.")
                    duplicates_info.append({"name": tag_name, "reason": "Duplicate name (case-insensitive) within CSV."})
                    skipped_duplicate_in_csv_count += 1
                    continue

                new_tags.append(tag_dict)
                existing_addr_type_keys.add(tag_addr_type_key) # Add to existing keys to check further CSV entries
                names_from_this_csv_lower.add(tag_name_lower) # Add to names from this CSV
                imported_count += 1
                logger.debug(f"Successfully processed tag: {tag_dict}")

    except FileNotFoundError:
        logger.error(f"CSV file not found at path: {file_path}", exc_info=True)
        errors_list.append({"tag_name": "N/A", "reason": f"File not found: {file_path}"})
        error_count += 1
    except csv.Error as e: # Catch errors specific to CSV parsing
        logger.error(f"CSV parsing error in file {file_path} near line {reader.line_num if 'reader' in locals() else 'unknown'}: {e}", exc_info=True)
        errors_list.append({"tag_name": "N/A", "reason": f"CSV parsing error: {e}"})
        error_count += 1
    except Exception as e:
        logger.error(f"Unexpected error parsing CSV file {file_path}: {e}", exc_info=True)
        # For the original function signature that returns error string:
        # return None, None, str(e), None # Keep this if strict adherence to old return on error is needed
        # For structured error reporting:
        errors_list.append({"tag_name": "N/A", "reason": f"Unexpected error: {e}"})
        error_count += 1
        # If an unexpected error occurs, new_tags and duplicates might be partially filled.
        # Decide if they should be cleared or returned as is.
        # For now, returning them as is.

    result = {
        "added": imported_count,
        "skipped_headers": skipped_header_count,
        "skipped_no_address": skipped_no_address_count,
        "skipped_unsupported_type": skipped_unsupported_type_count,
        "skipped_trigger_coil": skipped_trigger_coil_count,
        "skipped_invalid_address": skipped_invalid_address_count,
        "skipped_duplicates_existing": skipped_duplicate_existing_count,
        "skipped_duplicates_in_csv": skipped_duplicate_in_csv_count,
        "errors": error_count # Count of rows that caused an error during processing
    }
    logger.info(f"CSV parsing finished for {file_path}. Result: {result}")
    if errors_list:
        logger.info(f"Errors encountered during parsing: {errors_list}")
    if duplicates_info:
         logger.info(f"Information on skipped duplicates: {duplicates_info}")


    # The original function returned: new_tags, duplicates (list of duplicate tags), result (dict)
    # This refactoring returns: new_tags, duplicates_info (list of dicts with name+reason), result (dict), errors_list (list of dicts with name+reason)
    # To maintain compatibility with existing calls expecting 3 return values:
    # We can return `duplicates_info` as the second param, and `result` as third.
    # The `errors_list` is new. If the caller can handle 4 params, great. Otherwise, it might break.
    # For now, let's stick to 3 return values, combining errors into the result or logging them.
    # The original function on Exception returned: None, None, str(e).
    # Let's try to return the lists and result, and the caller can check result["errors"].
    
    # If the very first try block (file open) fails and returns error string:
    if error_count > 0 and imported_count == 0 and not new_tags and not errors_list:
         # This case tries to simulate the old "return None, None, str(e)" if a top-level exception occurred early.
         # However, with the current structure, errors_list will usually be populated.
         # It might be better to always return the structured info.
         pass # Will fall through to the return below.

    return new_tags, duplicates_info, result, errors_list
