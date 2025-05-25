import customtkinter as ctk
import json
import os
import re
from tkinter import messagebox
import csv
from tkinter import filedialog, messagebox
from tag_import_utils import parse_productivity_csv
from tag_import_dialog import import_tags_from_csv_gui
from tkinter import ttk



import logging # Added
# from main import APP_LOGGER_NAME # Or pass APP_LOGGER_NAME for fallback

class TagConfiguratorTab(ctk.CTkFrame):
    """
    A CustomTkinter frame providing UI for configuring PLC tags.

    This tab allows users to:
    - Add new tags with specified name, Modbus address, and type (Coil/Register).
    - Edit existing tags' properties.
    - Remove tags from the configuration.
    - Enable or disable individual tags for logging.
    - View the list of configured tags in a treeview.
    - Import tags from a CSV file (Productivity Suite format).
    - Save the tag configuration to `plc_logger_config.json`.

    It performs real-time validation for duplicate tag names and duplicate
    address/type combinations to prevent invalid configurations. Unsaved changes
    are tracked and highlighted.

    Attributes:
        app: Reference to the main `TagEditorApp` instance.
        logger: Logger instance for logging messages.
        tags (list[dict]): A list of tag dictionaries, representing the current
                           tag configuration being edited.
        unsaved_changes (bool): Flag indicating if there are unsaved modifications
                                to the tag list.
        selected_tag_index (int | None): Index of the currently selected tag in the
                                         treeview, or None if no tag is selected.
    """
    def __init__(self, master, app, logger_instance: logging.Logger = None, **kwargs):
        """
        Initializes the TagConfiguratorTab.

        Args:
            master: The parent widget.
            app: The main application instance (`TagEditorApp`).
            logger_instance: An optional logger instance. If None, a new logger
                             specific to this tab will be created.
            **kwargs: Additional keyword arguments for `ctk.CTkFrame`.
        """
        super().__init__(master, **kwargs)
        self.app = app
        # Use the passed logger instance, or get one if not provided
        self.logger = logger_instance if logger_instance else logging.getLogger("PLCLoggerApp_TagConfiguratorTab") # Fallback
        if not logger_instance:
            self.logger.warning("No central logger provided to TagConfiguratorTab; using fallback.")
            if not self.logger.hasHandlers(): # Basic config for fallback
                ch = logging.StreamHandler()
                ch.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(module)s - %(message)s'))
                self.logger.addHandler(ch)
                self.logger.setLevel(logging.DEBUG)

        self.logger.debug("Initializing TagConfiguratorTab")
        self.tags = []
        self.unsaved_changes = False
        self.selected_tag_index = None
        self.create_widgets()
        self.load_tags()

    def create_widgets(self):
        """Creates and arranges all UI widgets within the TagConfiguratorTab."""
        self.logger.debug("Creating TagConfiguratorTab widgets.")
        tooltip_font = ("Arial", 10, "italic") # Common font for tooltips
        form_frame = ctk.CTkFrame(self)
        form_frame.pack(padx=10, pady=10, fill="x")

        self.name_var = ctk.StringVar()
        self.name_entry = ctk.CTkEntry(form_frame, placeholder_text="Tag Name", textvariable=self.name_var)
        self.name_entry_tooltip = ctk.CTkLabel(form_frame, text="Enter a unique name for the tag", font=tooltip_font, text_color="gray")
        self.name_entry.grid(row=0, column=0, padx=5, pady=5)
        self.name_entry_tooltip.grid(row=1, column=0, padx=5, pady=(0, 10))

        self.name_entry.bind("<FocusOut>", self.on_name_entry_focus_out)
        self.name_var.trace_add("write", self.on_name_entry_change)

        self.address_entry = ctk.CTkEntry(form_frame, placeholder_text="Address")
        self.address_entry_tooltip = ctk.CTkLabel(form_frame, text="Integer address (e.g., 0, 1, 100)", font=tooltip_font, text_color="gray")
        self.address_entry.grid(row=0, column=1, padx=5, pady=5)
        self.address_entry_tooltip.grid(row=1, column=1, padx=5, pady=(0, 10))

        self.type_option = ctk.CTkOptionMenu(form_frame, values=["Coil", "Register"])
        self.type_option.set("Coil")
        # Improved tooltip
        self.type_option_tooltip = ctk.CTkLabel(form_frame, text="Select Modbus data type (Coil or Register)", font=tooltip_font, text_color="gray")
        self.type_option.grid(row=0, column=2, padx=5, pady=5)
        self.type_option_tooltip.grid(row=1, column=2, padx=5, pady=(0, 10))

        self.enabled_var = ctk.BooleanVar(value=True)
        self.enabled_checkbox = ctk.CTkCheckBox(form_frame, text="Enabled", variable=self.enabled_var)
        self.enabled_checkbox_tooltip = ctk.CTkLabel(form_frame, text="Uncheck to disable tag without deleting", font=tooltip_font, text_color="gray")
        self.enabled_checkbox.grid(row=0, column=3, padx=5, pady=5)
        self.enabled_checkbox_tooltip.grid(row=1, column=3, padx=5, pady=(0, 10))

        button_frame = ctk.CTkFrame(self)
        button_frame.pack(padx=10, pady=(0, 10), fill="x")

        self.add_button = ctk.CTkButton(button_frame, text="Add Tag", command=self.add_tag)
        self.add_button.pack(side="left", padx=5)

        self.edit_button = ctk.CTkButton(button_frame, text="Edit Tag", command=self.edit_tag)
        self.edit_button.pack(side="left", padx=5)

        self.remove_button = ctk.CTkButton(button_frame, text="Remove Tag", command=self.remove_tag)
        self.remove_button.pack(side="left", padx=5)

        self.save_button = ctk.CTkButton(button_frame, text="Save Tags", command=self.save_tags)
        self.save_button.pack(side="left", padx=5)

        # Add "Import Tags from CSV" button
        self.import_button = ctk.CTkButton(
            button_frame,
            text="Import Tags from CSV",
            command=self.import_tags_from_csv)  # We will define this method next
        self.import_button.pack(side="left", padx=5)


        #self.tag_display = ctk.CTkTextbox(self, width=800, height=200)
        #self.tag_display.pack(padx=10, pady=10, fill="both", expand=True)
        #self.tag_display.bind("<Button-1>", self.on_tag_display_click)
        #self.tag_display.configure(state="disabled")

        self.tree = ttk.Treeview(self, columns=("Name", "Type", "Address", "Enabled"), show="headings", height=8)

        self.tree.heading("Name", text="Name")
        self.tree.heading("Type", text="Type")
        self.tree.heading("Address", text="Address")
        self.tree.heading("Enabled", text="Enabled")

        self.tree.column("Name", width=200)
        self.tree.column("Type", width=100, anchor="center")
        self.tree.column("Address", width=100, anchor="center")
        self.tree.column("Enabled", width=100, anchor="center")

        self.tree.pack(padx=10, pady=10, fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)


    def import_tags_from_csv(self):
        """
        Opens a dialog to import tags from a CSV file.

        Uses `tag_import_dialog.import_tags_from_csv_gui` to handle the
        file selection and parsing process. Updates the tag display and marks
        changes as unsaved upon successful import. May trigger a stop/start of
        the main application's logging if tags are modified.
        """
        self.logger.info("Import Tags from CSV button clicked.")
        import_tags_from_csv_gui(
            self.tags, # This list will be modified in place by the dialog
            update_callback=lambda: (
                self.logger.info("Import dialog finished. Updating tag display and marking unsaved changes."),
                self.update_tag_display(),
                setattr(self, "unsaved_changes", True), # Mark changes as unsaved
                self.save_button.configure(fg_color="#FFA500") # Highlight save button
            ),
            app_stop_start=lambda: (
                self.logger.info("Requesting app stop/start for tag import changes."),
                self.app.stop_logging(), 
                self.app.start_logging()
            ),
            parent_logger=self.logger # Pass the logger to the dialog
        )

    def clean_tag_name(self, name: str) -> str:
        """
        Cleans a tag name by stripping leading/trailing whitespace and
        normalizing internal spaces to a single space.

        Args:
            name: The tag name string to clean.

        Returns:
            The cleaned tag name string.
        """
        name = name.strip()
        name = re.sub(r'\s+', ' ', name) # Replace multiple spaces with a single space
        return name

    def update_tag_display(self, highlight_index: int = None):
        """
        Refreshes the Treeview widget with the current list of tags.

        Optionally highlights a specific tag in the list.

        Args:
            highlight_index: The index of the tag to highlight in the tree.
                             If None, no tag is specifically highlighted.
        """
        self.logger.debug(f"Updating tag display. Highlighting index: {highlight_index}")
        # Clear the tree
        for row in self.tree.get_children():
            self.tree.delete(row)

        # Populate the tree with current tags
        for idx, tag in enumerate(self.tags):
            values = (
                tag.get("name", ""), # Use .get for safety
                tag.get("type", "N/A"),
                tag.get("address", "N/A"),
                "Yes" if tag.get("enabled", True) else "No"
            )
            # Use index as IID for simplicity, ensure it's a string
            tag_id = self.tree.insert("", "end", iid=str(idx), values=values)
            
            if idx == highlight_index:
                self.tree.selection_set(tag_id) # Select the item
                self.tree.focus(tag_id)         # Set focus to the item
                self.tree.see(tag_id)           # Ensure item is visible


    def on_tree_select(self, event):
        """
        Callback for when a tag is selected in the Treeview.

        Populates the input fields (name, address, type, enabled) with the
        details of the selected tag and updates `self.selected_tag_index`.

        Args:
            event: The event object (unused).
        """
        selected_items = self.tree.selection()
        if not selected_items: # Should not happen if event is selection, but good check
            self.logger.debug("Tree selection event, but no items selected.")
            return
        
        selected_iid = selected_items[0] # Get the IID of the selected item
        idx = int(selected_iid) # IID was set to string of index
        
        if 0 <= idx < len(self.tags):
            self.selected_tag_index = idx
            tag = self.tags[idx]
            self.logger.debug(f"Tag selected in tree: Index {idx}, Data: {tag}")

            self.name_var.set(tag.get('name', ''))
            self.address_entry.delete(0, "end")
            self.address_entry.insert(0, str(tag.get('address', '')))
            self.type_option.set(tag.get('type', 'Coil'))
            self.enabled_var.set(tag.get("enabled", True))
        else:
            self.logger.error(f"Tree selection returned invalid index: {idx} for tags list of length {len(self.tags)}")
            self.selected_tag_index = None


    def get_selected_tag_index_from_cursor(self, event):
        """
        Determines which tag is clicked in the (now removed) CTkTextbox display.
        This method is obsolete as the display is now a Treeview.
        Kept for reference if old display logic needs to be reviewed.
        """
        self.logger.warning("get_selected_tag_index_from_cursor called, but it's obsolete with Treeview.")
        return None


    def on_tag_display_click(self, event):
        """
        Callback for clicks on the (now removed) CTkTextbox tag display.
        This method is obsolete as the display is now a Treeview.
        The `on_tree_select` method handles selections from the Treeview.
        """
        self.logger.warning("on_tag_display_click called, but it's obsolete with Treeview.")
        pass # Functionality moved to on_tree_select for Treeview


    def add_tag(self):
        """
        Adds a new tag to the configuration list based on data from input fields.

        Validates the input for:
        - Non-empty tag name.
        - Integer address.
        - Duplicate address/type combination among existing tags.
        - Duplicate name (case-insensitive) among existing tags.

        If validation passes, the tag is added, UI is updated, and unsaved
        changes are flagged.
        """
        name = self.clean_tag_name(self.name_entry.get())
        try:
            address_str = self.address_entry.get()
            if not address_str: # Check for empty address string
                messagebox.showerror("Invalid Address", "Address cannot be empty.")
                self.logger.warning("Add tag attempt failed: Address field empty.")
                return
            address = int(address_str)
        except ValueError:
            messagebox.showerror("Invalid Address", "Address must be an integer.")
            self.logger.warning(f"Add tag attempt failed: Invalid address format '{address_str}'.")
            return
        tag_type = self.type_option.get()
        enabled = self.enabled_var.get()

        if not name:
            messagebox.showerror("Missing Name", "Please enter a tag name.")
            self.logger.warning("Add tag attempt failed: Tag name missing.")
            return

        # Check for duplicate address/type combo
        for tag in self.tags:
            if tag["address"] == address and tag["type"] == tag_type:
                err_msg = f"Another tag ('{tag['name']}') already uses address {address} as a {tag_type}."
                messagebox.showerror("Duplicate Address", err_msg)
                self.logger.warning(f"Add tag failed: {err_msg}")
                return

        # Check for duplicate name (case-insensitive)
        for tag in self.tags:
            if self.clean_tag_name(tag["name"]).lower() == name.lower():
                err_msg = f"Another tag already uses the name '{name}' (case-insensitive)."
                messagebox.showerror("Duplicate Name", err_msg)
                self.name_entry_tooltip.configure(text=f"Name '{name}' already exists!", text_color="red")
                if hasattr(self.name_entry, 'configure'): self.name_entry.configure(border_color="red")
                self.logger.warning(f"Add tag failed: {err_msg}")
                return
        
        # If all checks pass, reset name entry visual cues
        self.name_entry_tooltip.configure(text="Enter a unique name for the tag", text_color="gray")
        if hasattr(self.name_entry, 'configure'): self.name_entry.configure(border_color="gray")

        new_tag = {"name": name, "address": address, "type": tag_type, "enabled": enabled, "scale": 1.0, "description": ""} # Add defaults
        self.tags.append(new_tag)
        self.logger.info(f"Tag added: {new_tag}")
        self.unsaved_changes = True
        self.save_button.configure(fg_color="#FFA500")
        self.update_tag_display(highlight_index=len(self.tags)-1) # Highlight the newly added tag
        self.selected_tag_index = None # Deselect after adding

    def edit_tag(self):
        if self.selected_tag_index is None or not (0 <= self.selected_tag_index < len(self.tags)):
            messagebox.showerror("No Tag Selected", "Please select a tag from the list to edit.")
            self.logger.warning("Edit tag attempt failed: No tag selected.")
            return

        name = self.clean_tag_name(self.name_entry.get())
        try:
            address_str = self.address_entry.get()
            if not address_str:
                messagebox.showerror("Invalid Address", "Address cannot be empty.")
                self.logger.warning("Edit tag failed: Address field empty.")
                return
            address = int(address_str)
        except ValueError:
            messagebox.showerror("Invalid Address", "Address must be an integer.")
            self.logger.warning(f"Edit tag failed: Invalid address format '{address_str}'.")
            return

        tag_type = self.type_option.get()
        enabled = self.enabled_var.get()

        # Check for duplicate name (ignore self)
        for idx, tag in enumerate(self.tags):
            if idx != self.selected_tag_index and self.clean_tag_name(tag["name"]).lower() == name.lower():
                err_msg = f"Another tag already uses the name '{name}' (case-insensitive)."
                messagebox.showerror("Duplicate Name", err_msg)
                self.name_entry_tooltip.configure(text=f"Name '{name}' already exists!", text_color="red")
                if hasattr(self.name_entry, 'configure'): self.name_entry.configure(border_color="red")
                self.logger.warning(f"Edit tag failed for tag '{self.tags[self.selected_tag_index]['name']}': {err_msg}")
                return

        # Check for duplicate address/type combo (ignore self)
        for idx, tag in enumerate(self.tags):
            if idx != self.selected_tag_index and tag["address"] == address and tag["type"] == tag_type:
                err_msg = f"Another tag ('{tag['name']}') already uses address {address} as a {tag_type}."
                messagebox.showerror("Duplicate Address", err_msg)
                self.logger.warning(f"Edit tag failed for tag '{self.tags[self.selected_tag_index]['name']}': {err_msg}")
                return
        
        self.name_entry_tooltip.configure(text="Enter a unique name for the tag", text_color="gray")
        if hasattr(self.name_entry, 'configure'): self.name_entry.configure(border_color="gray")

        # Update the tag, preserving other potential fields like 'description' or 'scale'
        original_tag = self.tags[self.selected_tag_index]
        original_tag.update({
            "name": name,
            "address": address,
            "type": tag_type,
            "enabled": enabled
        })
        self.logger.info(f"Tag at index {self.selected_tag_index} edited to: {original_tag}")

        self.unsaved_changes = True
        self.save_button.configure(fg_color="#FFA500") # Highlight save button
        self.update_tag_display(highlight_index=self.selected_tag_index) # Re-highlight edited tag
        self.app.tags = self.tags.copy() # Update main app's tag list reference




    def on_name_entry_focus_out(self, event=None):
        """
        Checks for duplicate tag names when the name entry loses focus.
        Updates tooltip and border color as needed.
        """
        name = self.clean_tag_name(self.name_entry.get())
        if not name:
            self.name_entry_tooltip.configure(
                text="Enter a unique name for the tag",
                text_color="gray"
            )
            if hasattr(self.name_entry, 'configure'): self.name_entry.configure(border_color="gray")
            return

        # Check against current selected tag if editing, otherwise check all
        is_editing = self.selected_tag_index is not None
        
        for idx, tag_item in enumerate(self.tags):
            if is_editing and idx == self.selected_tag_index:
                continue # Skip check against self when editing
            if self.clean_tag_name(tag_item["name"]).lower() == name.lower():
                self.name_entry_tooltip.configure(text=f"Name '{name}' already exists!", text_color="red")
                if hasattr(self.name_entry, 'configure'): self.name_entry.configure(border_color="red")
                self.logger.debug(f"Name entry focus out: Duplicate name '{name}' found.")
                return # Found a duplicate

        # If no duplicate found (or it's the same tag being edited and name hasn't changed to another existing one)
        self.name_entry_tooltip.configure(text="Enter a unique name for the tag", text_color="gray")
        if hasattr(self.name_entry, 'configure'): self.name_entry.configure(border_color="gray")
        self.logger.debug(f"Name entry focus out: Name '{name}' appears unique or unchanged for current edit.")


    def on_name_entry_change(self, *args):
        """
        Callback when the content of the name entry field changes.

        Triggers `on_name_entry_focus_out` to perform real-time validation
        for duplicate names.
        """
        self.logger.debug(f"Name entry changed: {self.name_var.get()}")
        self.on_name_entry_focus_out()

    def save_tags(self):
        """
        Saves the current list of configured tags to the `plc_logger_config.json` file.

        Performs final validation checks for duplicate names (case-insensitive)
        and duplicate address/type combinations before saving. Updates the main
        application's tag list and resets the unsaved changes flag.
        """
        self.logger.info("Save Tags button clicked.")
        
        # Final validation for duplicate names (case-insensitive)
        name_counts = {}
        for tag in self.tags:
            cleaned_name_lower = self.clean_tag_name(tag["name"]).lower()
            name_counts[cleaned_name_lower] = name_counts.get(cleaned_name_lower, 0) + 1
        
        duplicate_names = [name for name, count in name_counts.items() if count > 1]
        if duplicate_names:
            err_msg = f"Cannot save. Duplicate tag names found (case-insensitive): {', '.join(duplicate_names)}"
            messagebox.showerror("Duplicate Names", err_msg)
            self.logger.error(f"Save tags failed: {err_msg}")
            return

        # Final validation for duplicate address/type combinations
        address_type_map = {}
        for tag in self.tags:
            # Ensure address is an int for the key, as it might be string from entry before proper add/edit
            try:
                tag_address_int = int(tag["address"])
            except ValueError:
                # This case should ideally not happen if tags are added/edited through UI with validation
                self.logger.error(f"Tag '{tag['name']}' has non-integer address '{tag['address']}' during save. Skipping save.")
                messagebox.showerror("Save Error", f"Tag '{tag['name']}' has an invalid address. Please correct it before saving.")
                return

            key = (tag_address_int, tag["type"])
            if key in address_type_map:
                existing_tag_name = address_type_map[key]
                err_msg = (f"Cannot save. Tags '{tag['name']}' and '{existing_tag_name}' "
                           f"share the same address {key[0]} and type '{key[1]}'.")
                messagebox.showerror("Duplicate Address/Type", err_msg)
                self.logger.error(f"Save tags failed: {err_msg}")
                return
            address_type_map[key] = tag["name"]

        # Proceed with saving if all validations pass
        config_file_path = "plc_logger_config.json" # TODO: Use utils.CONFIG_FILE
        try:
            self.logger.debug(f"Attempting to read existing config from {config_file_path} before saving tags.")
            if os.path.exists(config_file_path):
                with open(config_file_path, "r") as f:
                    config = json.load(f)
            else: # If config file doesn't exist, create one with current global settings
                self.logger.info(f"{config_file_path} not found. Creating new one with current global settings.")
                config = {"global_settings": self.app.global_settings, "tags": []} 
            
            config["tags"] = self.tags # Update only the tags part of the config
            
            with open(config_file_path, "w") as f:
                json.dump(config, f, indent=4)
            
            self.logger.info(f"Tags saved successfully to {config_file_path}. {len(self.tags)} tags written.")
            messagebox.showinfo("Saved", f"Tags saved to {config_file_path}")
            
            self.app.tags = self.tags.copy() # Update main app's list
            self.unsaved_changes = False
            # Reset save button color to default
            self.save_button.configure(fg_color=("#1f6aa5", "#144870"), hover_color=("#1786c6", "#1a5e89"))
            self.app.update_tag_filter_dropdown() # Refresh main GUI's tag filter dropdown
        except Exception as e:
            self.logger.error(f"Error saving tags to {config_file_path}: {e}", exc_info=True)
            messagebox.showerror("Error Saving", f"An error occurred while saving tags:\n{e}")

    def remove_tag(self):
        """
        Removes the currently selected tag from the `self.tags` list and updates the UI.

        Requires a tag to be selected in the Treeview. Prompts for confirmation
        before deletion.
        """
        if self.selected_tag_index is None or not (0 <= self.selected_tag_index < len(self.tags)):
            messagebox.showerror("No Tag Selected", "Please select a tag from the list to remove.")
            self.logger.warning("Remove tag attempt failed: No tag selected.")
            return

        tag_to_remove = self.tags[self.selected_tag_index]
        self.logger.debug(f"Attempting to remove tag: {tag_to_remove}")

        confirm = messagebox.askyesno(
            "Confirm Deletion",
            f"Are you sure you want to remove tag: {tag_to_remove['name']} [{tag_to_remove['type']} @ {tag_to_remove['address']}]?"
        )
        if confirm:
            removed_tag = self.tags.pop(self.selected_tag_index)
            self.logger.info(f"Tag removed: {removed_tag}")
            self.unsaved_changes = True
            self.save_button.configure(fg_color="#FFA500") # Highlight save button
            self.update_tag_display() # Refresh treeview
            self.selected_tag_index = None # Clear selection
            # Clear input fields after removal
            self.name_var.set("")
            self.address_entry.delete(0, "end")
            self.type_option.set("Coil") # Reset to default
            self.enabled_var.set(True)
        else:
            self.logger.info("Tag removal cancelled by user.")


    def load_tags(self):
        """
        Loads tags from the main application's tag list (`self.app.tags`) into this tab.

        This method is typically called during tab initialization to synchronize its
        tag list with the global application state. It updates the Treeview display
        and resets the `unsaved_changes` flag.
        """
        self.tags = self.app.tags.copy() # Get a copy from the main app instance
        self.logger.info(f"Loading tags into configurator tab from main app. {len(self.tags)} tags loaded.")
        self.update_tag_display()
        self.unsaved_changes = False # Reset unsaved changes flag after loading
        # Reset save button color to default
        self.save_button.configure(
                fg_color=("#1f6aa5", "#144870"),
                hover_color=("#1786c6", "#1a5e89")
            )
