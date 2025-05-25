# tag_import_dialog.py

from tkinter import filedialog, messagebox, Toplevel, Label, Button
from tag_import_utils import parse_productivity_csv
import logging # Added

# It's better if the logger is passed in, but have a fallback if not.
# This module-level logger will be used by show_duplicate_dialog if no parent_logger is given.
module_logger = logging.getLogger(__name__) # Get logger named after the module
if not module_logger.hasHandlers() and not logging.getLogger().hasHandlers(): # Basic config if no handlers on this or root
    # This basicConfig is a fallback for standalone module usage,
    # but typically the main app's logging config will cover this.
    logging.basicConfig(level=logging.INFO, 
                        format='%(asctime)s - %(levelname)s - [%(module)s.%(funcName)s:%(lineno)d] - %(message)s')


def show_duplicate_dialog(conflict_name: str, new_name: str, addr: int, 
                          tag_type: str, parent_logger: logging.Logger = None) -> str | None:
    """
    Displays a modal dialog to the user for resolving a duplicate tag conflict.

    This dialog is shown when importing tags from a CSV and a tag is found
    that conflicts with an existing tag (same address and type). The user can
    choose to overwrite the existing tag with the new one, skip the new tag,
    or apply the choice to all subsequent duplicates ("Overwrite All", "Skip All").
    A "Cancel Import" option is also provided.

    Args:
        conflict_name: The name of the existing tag that conflicts.
        new_name: The name of the new tag from the CSV that is causing the conflict.
        addr: The Modbus address where the conflict occurs.
        tag_type: The type of the tag (e.g., "Coil", "Register").
        parent_logger: An optional logger instance. If None, a module-level
                       logger is used.

    Returns:
        A string representing the user's choice: "overwrite", "skip",
        "overwrite_all", "skip_all", "cancel", or None if the dialog is
        closed without making a choice (though current setup forces a choice).
    """
    logger = parent_logger if parent_logger else module_logger
    logger.info(f"Showing duplicate dialog: Existing='{conflict_name}', New='{new_name}', Address={addr}, Type='{tag_type}'")
    
    choice = {"value": None} # Use a mutable type to pass choice out of callback
    win = Toplevel()
    win.title("Duplicate Tag Resolution") # More descriptive title
    win.grab_set()
    Label(win, text=(
        f"Duplicate tag at {tag_type} address {addr} already exists as '{conflict_name}'.\n"
        f"Do you want to overwrite it with '{new_name}'?\n\n"
        "Choose an option below:"
    )).pack(padx=20, pady=10)

    def set_choice(val):
        choice["value"] = val
        win.destroy()

    Button(win, text="Overwrite This", command=lambda: set_choice("overwrite")).pack(fill='x')
    Button(win, text="Skip This", command=lambda: set_choice("skip")).pack(fill='x')
    Button(win, text="Overwrite All", command=lambda: set_choice("overwrite_all")).pack(fill='x')
    Button(win, text="Skip All", command=lambda: set_choice("skip_all")).pack(fill='x')
    Button(win, text="Cancel Import", command=lambda: set_choice("cancel")).pack(side="bottom", fill='x', pady=(5,0))

    win.wait_window() # Wait for the dialog to be closed
    user_choice = choice["value"]
    logger.info(f"User choice in duplicate dialog for '{new_name}': {user_choice}")
    return user_choice

def import_tags_from_csv_gui(existing_tags_list: list[dict], 
                             update_callback: callable, 
                             app_stop_start: callable, 
                             parent_logger: logging.Logger = None):
    """
    Manages the GUI process for importing tags from a CSV file.

    This function:
    1. Opens a file dialog for the user to select a CSV file.
    2. Calls `parse_productivity_csv` from `tag_import_utils` to parse the file.
    3. Handles potential errors during parsing and displays error messages.
    4. Processes the successfully parsed tags:
        - Adds unique new tags to the `existing_tags_list`.
        - (Note: The interactive duplicate resolution dialog `show_duplicate_dialog`
          is currently bypassed as the refactored `parse_productivity_csv` aims to
          handle structural duplicates directly. If more nuanced, UI-driven duplicate
          handling is required for name conflicts or other scenarios, the logic
          around `duplicates_info` and calling `show_duplicate_dialog` would need
          to be reinstated and adapted.)
    5. Calls `update_callback` to refresh the UI in the parent tab (e.g., TagConfiguratorTab)
       and mark changes as unsaved.
    6. Calls `app_stop_start` to request a stop and restart of the main application's
       logging service if new tags were added, to ensure they are included.
    7. Displays a summary message to the user about the import results, including
       counts of added tags, skipped tags (with reasons), and any errors.

    Args:
        existing_tags_list: A list of tag dictionaries currently in the application.
                            This list will be modified in place if new tags are added.
        update_callback: A callable that is executed after tags are successfully
                         imported and added, typically to refresh the UI.
        app_stop_start: A callable that stops and starts the main application's
                        logging service.
        parent_logger: An optional logger instance. If None, a module-level
                       logger is used.
    """
    logger = parent_logger if parent_logger else module_logger
    logger.info("Attempting to import tags from CSV via GUI dialog.")

    file_path = filedialog.askopenfilename(
        title="Select Tag CSV File (Productivity Suite Export)",
        filetypes=[("CSV Files", "*.csv")]
    )
    if not file_path:
        logger.info("CSV import cancelled by user (no file selected).")
        return

    logger.info(f"User selected CSV file: {file_path}")

    # parse_productivity_csv now returns: new_tags, duplicates_info, result, errors_list
    parsed_tags, duplicates_info, result_summary, errors_list = parse_productivity_csv(file_path, existing_tags_list)

    if result_summary.get("errors", 0) > 0 and not parsed_tags and not duplicates_info :
        # This condition implies a major failure in parsing, like file not found or completely unreadable.
        # errors_list should contain details.
        error_details_str = "\n".join([f"- {e['reason']}" for e in errors_list[:3]]) # Show first 3 errors
        messagebox.showerror("Import Error", f"Failed to read or parse CSV: {file_path}\nDetails:\n{error_details_str}")
        logger.error(f"CSV import failed for {file_path}. Errors: {errors_list}")
        return

    overwrite_all_choice = False
    skip_all_choice = False
    actually_added_count = 0
    
    # Add initially parsed new tags that are not duplicates yet
    # The `parse_productivity_csv` should ideally only return tags that are not duplicates of existing ones by address/type.
    # It now returns `duplicates_info` for items that conflict with `existing_tags_list` by name or addr/type.
    
    final_tags_to_add = [] # Tags that will be definitely added after resolving conflicts

    # Process non-duplicate new tags first (these are not in duplicates_info from parser)
    for new_tag in parsed_tags:
        final_tags_to_add.append(new_tag)
        actually_added_count +=1
        logger.debug(f"Initially adding new tag (no conflict with existing): {new_tag['name']}")

    # Handle duplicates reported by the parser (these conflicted with existing_tags_list)
    # The `duplicates_info` contains tags from CSV that conflicted with `existing_tags_list`.
    # We need to ask user how to resolve these.
    for dup_info in duplicates_info:
        # `dup_info` is like {"name": "TagName", "reason": "Duplicate address/type..."}
        # We need the actual tag data from the CSV that caused this duplicate entry.
        # This part needs careful handling: parse_productivity_csv should provide the conflicting CSV tag data.
        # For now, let's assume `dup_info` IS the tag from CSV that was a duplicate.
        # This logic needs to be robust based on what `parse_productivity_csv` puts in `duplicates_info`.
        # Assuming `duplicates_info` contains the *tag dictionary* from the CSV that was a duplicate.
        
        csv_tag_data = dup_info # This assumption might be flawed based on previous `parse_productivity_csv` version.
                               # Corrected `parse_productivity_csv` now returns `duplicates_info` as list of dicts with name+reason.
                               # This loop should iterate `parsed_tags` and check against `duplicates_info` if a tag from `parsed_tags` was marked.
                               # However, `parse_productivity_csv` now aims to return ONLY unique new tags in `parsed_tags`.
                               # `duplicates_info` is for user feedback about what was skipped by the parser.
                               # The GUI dialog for duplicates is more about UI-level conflict resolution if needed,
                               # but the parser is already handling most structural duplicates.

        # The current `parse_productivity_csv` is designed to avoid adding tags to `new_tags` if they are duplicates.
        # So, the duplicate dialog here is somewhat redundant if the parser is strict.
        # Let's assume this dialog is for a *second layer* of checks or if the parser's duplicate handling changes.
        # For now, this loop over `duplicates_info` (as if they were tags to potentially add) might be incorrect.
        #
        # REVISITING LOGIC: The `duplicates_info` from the refactored parser contains *reasons* for skipping,
        # not necessarily tags to be re-processed for user dialog.
        # The old `duplicates` list contained tag dicts.
        # The current `import_tags_from_csv_gui` needs to be simpler:
        # 1. Get `parsed_tags` (these are unique new tags).
        # 2. Add them to `existing_tags_list`.
        # 3. Report `result_summary` and `errors_list`.
        # The complex duplicate dialog (`show_duplicate_dialog`) might be removed if parser handles all dup logic.

        # Simplified approach: Add all tags from `parsed_tags` (as they are already filtered by parser)
        # The `duplicates_info` and `errors_list` are for the summary message.
        pass # End of the problematic duplicate handling loop. `final_tags_to_add` already has content from `parsed_tags`.


    if final_tags_to_add:
        existing_tags_list.extend(final_tags_to_add)
        logger.info(f"Added {len(final_tags_to_add)} new unique tags to the main tag list.")
        update_callback() # This will mark unsaved changes and update GUI display
        
        # Restart logging only if tags were actually added that might affect logging
        # (e.g. if logging was active and using the old tag set)
        logger.info("Requesting app stop/start after adding new tags.")
        app_stop_start() 
        
        summary_message = f"Successfully added {len(final_tags_to_add)} new tag(s).\n"
        summary_message += "Changes are not saved until you click 'Save Tags' in the Tag Configurator."
    else:
        summary_message = "No new tags were added."
        if not errors_list and not duplicates_info : # No errors, no duplicates, but also no new tags (e.g. empty CSV or all existing)
             logger.info("No new tags found in CSV or all were already present/skipped by parser.")
        elif errors_list:
             logger.info(f"No new tags added. Errors during parsing: {len(errors_list)}")
        elif duplicates_info: # Only duplicates, no new tags
             logger.info(f"No new tags added. All potential tags were duplicates of existing ones: {len(duplicates_info)}")


    # Build detailed summary message
    details = []
    if result_summary.get("skipped_headers",0): details.append(f"{result_summary['skipped_headers']} header line(s)")
    if result_summary.get("skipped_no_address",0): details.append(f"{result_summary['skipped_no_address']} with no/invalid address")
    if result_summary.get("skipped_unsupported_type",0): details.append(f"{result_summary['skipped_unsupported_type']} of unsupported type")
    if result_summary.get("skipped_trigger_coil",0): details.append(f"{result_summary['skipped_trigger_coil']} system trigger coil(s)")
    # Duplicates skipped by parser:
    if result_summary.get("skipped_duplicates_existing",0): details.append(f"{result_summary['skipped_duplicates_existing']} duplicate of existing (name or addr/type)")
    if result_summary.get("skipped_duplicates_in_csv",0): details.append(f"{result_summary['skipped_duplicates_in_csv']} duplicate within CSV (name)")
    
    if details:
        summary_message += f"\n\nParser Summary:\n- Skipped: {', '.join(details)}."
    
    if errors_list:
        summary_message += f"\n- Errors on {len(errors_list)} row(s). First few errors:"
        for i, err in enumerate(errors_list[:3]): # Show details of first 3 errors
            summary_message += f"\n  - Row (approx. {err.get('line_number', 'N/A')}): Tag '{err.get('tag_name', 'N/A')}' - {err['reason']}"
        if len(errors_list) > 3:
            summary_message += "\n  - ... and more. Check application log for full details."
        logger.warning(f"Import process completed with errors. Error list: {errors_list}")


    logger.info(f"Final import summary: {summary_message.replace('\n', ' | ')}")
    messagebox.showinfo("Import Result", summary_message)
