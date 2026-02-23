import os
from PIL import Image

def crop_encyclopedia():
    folders = ["commodities", "equipment", "weapons"]
    crop_box = (790, 178, 790 + 748, 178 + 502)

    base_dir = os.path.dirname(os.path.abspath(__file__))

    for folder in folders:
        folder_path = os.path.join(base_dir, folder)
        if not os.path.exists(folder_path):
            print(f"Folder not found: {folder_path}")
            continue

        for filename in os.listdir(folder_path):
            if filename.lower().endswith(('.jpg')):
                file_path = os.path.join(folder_path, filename)
                try:
                    with Image.open(file_path) as img:
                        cropped = img.crop(crop_box)
                        # Load data to ensure we can close the file before saving
                        cropped.load()
                    
                    cropped.save(file_path)
                    print(f"Cropped: {file_path}")
                except Exception as e:
                    print(f"Failed to process {file_path}: {e}")


def break_up_encyclopedia() -> None:
    folders = ["commodities", "equipment", "weapons"]
    base_dir = os.path.dirname(os.path.abspath(__file__))

    for folder in folders:
        folder_path = os.path.join(base_dir, folder)
        if not os.path.exists(folder_path):
            print(f"Folder not found: {folder_path}")
            continue

        # Sort files to ensure deterministic ordering of items
        # Exclude files that match the output pattern to avoid reprocessing
        files = sorted([f for f in os.listdir(folder_path) if f.lower().endswith('.jpg') and not f.startswith(f"{folder}_item_")])
        
        item_idx = 1
        for filename in files:
            file_path = os.path.join(folder_path, filename)
            try:
                with Image.open(file_path) as img:
                    width, height = img.size
                    step = height // 5
                    for i in range(5):
                        # Crop format: (left, top, right, bottom)
                        item = img.crop((0, i * step, width, (i + 1) * step))
                        item.save(os.path.join(folder_path, f"{folder}_item_{item_idx}.jpg"))
                        item_idx += 1
                print(f"Processed {filename}")
            except Exception as e:
                print(f"Failed to process {file_path}: {e}")


def main() -> None:
    # crop_encyclopedia()
    break_up_encyclopedia()


if __name__ == "__main__":
    main()
