import os
from PIL import Image


def crop_folder_images(
    folder_name: str,
    crop_box: tuple[int, int, int, int],
    overwrite: bool = False,
    prefix: str = "",
) -> None:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    folder_path = os.path.join(base_dir, folder_name)

    if not os.path.exists(folder_path):
        print(f"Folder not found: {folder_path}")
        return

    # Include common image types we might encounter in the dataset.
    valid_exts = (".jpg", ".jpeg", ".png", ".webp")

    for filename in os.listdir(folder_path):
        if not filename.lower().endswith(valid_exts):
            continue

        if filename.lower().startswith("icons_"):
            continue

        if filename.lower().startswith("selected_"):
            continue

        file_path = os.path.join(folder_path, filename)
        stem, _ext = os.path.splitext(filename)
        out_name = f"{prefix}{stem}.png"
        out_path = os.path.join(folder_path, out_name)

        if (not overwrite) and os.path.exists(out_path):
            print(f"Skipped (exists): {out_path}")
            continue

        try:
            with Image.open(file_path) as img:
                cropped = img.crop(crop_box)
                # Ensure data is read before the source file handle closes.
                cropped.load()

            cropped.save(out_path)
            print(f"Cropped: {file_path} -> {out_path}")
        except Exception as e:
            print(f"Failed to process {file_path}: {e}")


def main() -> None:
    crop_box = (1005, 773, 1005 + 582, 773 + 204)

    target_folders = ["frames"]

    # Set to True if you want to overwrite existing `cropped_*.png` outputs.
    overwrite = False

    for folder in target_folders:
        crop_folder_images(
            folder, crop_box=crop_box, overwrite=overwrite, prefix="description_"
        )


if __name__ == "__main__":
    main()
