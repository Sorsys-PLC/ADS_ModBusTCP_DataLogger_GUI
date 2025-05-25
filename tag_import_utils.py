def parse_productivity_csv(file_path, existing_tags):
    import csv

    new_tags = []
    duplicates = []
    skip_no_addr = skip_unsupported = 0

    existing_keys = {
        (t["address"], t["type"].lower()) for t in existing_tags
    }

    try:
        with open(file_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            for _ in range(2):  # Skip header/comment lines
                next(reader, None)

            for row in reader:
                if not row or len(row) < 17:
                    continue

                tag_name = row[1].strip()
                modbus_start = row[4].strip()
                data_type = row[16].strip() if len(row) > 16 else ""

                if not modbus_start:
                    skip_no_addr += 1
                    continue

                if tag_name.endswith("()"):
                    continue

                base_type = data_type.lstrip("AR0123456789")
                if "STR" in base_type or "STRUCT" in base_type or not base_type:
                    skip_unsupported += 1
                    continue

                # Handle coils
                if base_type in ("C", "SBR", "MST", "DO", "DI"):
                    tag_type = "Coil"
                    address = int(modbus_start) - 1
                    if address == 0:
                        continue  # SKIP trigger coil
                else:
                    tag_type = "Register"
                    raw_address = int(modbus_start) - 400001
                    if raw_address % 2 != 0 or raw_address < 0:
                        skip_unsupported += 1
                        continue
                    address = raw_address // 2  # Align to 32-bit boundary

                tag_key = (address, tag_type.lower())

                tag = {
                    "name": tag_name,
                    "address": address,
                    "type": tag_type,
                    "enabled": True
                }

                if tag_key in existing_keys:
                    duplicates.append(tag)
                else:
                    new_tags.append(tag)

    except Exception as e:
        return None, None, str(e)

    result = {
        "imported": len(new_tags),
        "skipped_no_address": skip_no_addr,
        "skipped_unsupported": skip_unsupported,
        "skipped_duplicates": len(duplicates)
    }

    return new_tags, duplicates, result
