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
            if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.tiff')):
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


def main() -> None:
    crop_encyclopedia()


if __name__ == "__main__":
    main()
