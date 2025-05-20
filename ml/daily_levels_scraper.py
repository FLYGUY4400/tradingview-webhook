import easyocr
import cv2
import os
import re
import csv

def clean_and_split_lines(lines):
    data = []
    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Match leading number (with optional decimal)
        match = re.match(r"^([0-9]{3,5}(?:\.\d{1,2})?)\s*(.*)$", line)
        if match:
            value = match.group(1)
            label = match.group(2).strip().upper() or "UNKNOWN"
        else:
            match = re.search(r"([0-9]{3,5}(?:\.\d{1,2})?)", line)
            if match:
                value = match.group(1)
                label = line.replace(value, "").strip().upper() or "UNKNOWN"
            else:
                continue  # Skip if no number found

        # Skip unwanted labels
        if label in {"(", ")", "UNKNOWN"}:
            continue

        data.append((value, label))
    return data

def extract_text_from_image(image_path: str, output_file: str = "csv/daily_levels.csv"):
    if not os.path.exists(image_path):
        print(f"File not found: {image_path}")
        return

    image = cv2.imread(image_path)
    if image is None:
        print("Could not read the image.")
        return

    reader = easyocr.Reader(['en'], gpu=False)
    results = reader.readtext(image_path)

    raw_lines = [text.strip() for (_, text, _) in results]
    cleaned_data = clean_and_split_lines(raw_lines)

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Value', 'Label'])
        writer.writerows(cleaned_data)

    print(f"Wrote {len(cleaned_data)} entries to {output_file}")

if __name__ == "__main__":
    extract_text_from_image("images/image.png")  # Replace with your actual image
