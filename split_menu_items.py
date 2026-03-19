import os
from typing import Iterable, Tuple

from PIL import Image, ImageStat


TARGET_FOLDERS = ["frames"]

# Points from your menu selection:
COLOR_BG = (5, 15, 27)
COLOR_ITEM = (6, 28, 129)

# The "average color" might only apply to part of the slice height
# (menu icons often occupy only a band), so we support averaging over a band.
# 0.0-1.0 => entire slice height.
MEAN_Y_START_FRAC_DEFAULT = 0.0
MEAN_Y_END_FRAC_DEFAULT = 1.0

# If the first pass kept nothing, we'll try a narrower band automatically.
MEAN_Y_START_FRAC_FALLBACK = 0.25
MEAN_Y_END_FRAC_FALLBACK = 0.75


def squared_dist(a: Tuple[float, float, float], b: Tuple[int, int, int]) -> float:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2


def iter_input_images(folder_path: str) -> Iterable[str]:
    # Prefer previously produced crops, since that matches the "split each of these images" request.
    cropped = sorted(
        [
            fn
            for fn in os.listdir(folder_path)
            if fn.lower().endswith(".png") and fn.lower().startswith("icons_")
        ]
    )
    if cropped:
        for fn in cropped:
            yield os.path.join(folder_path, fn)
        return

    # Fallback: process any image files.
    valid_exts = (".jpg", ".jpeg", ".png", ".webp")
    for fn in sorted(os.listdir(folder_path)):
        if fn.lower().endswith(valid_exts):
            yield os.path.join(folder_path, fn)


def crop_and_select_slices(
    input_path: str,
    output_dir: str,
    top_scores: list,
    counters: dict,
    mean_y_start_frac: float,
    mean_y_end_frac: float,
    save_debug_all_parts: bool = False,
) -> None:
    stem = os.path.splitext(os.path.basename(input_path))[0]

    with Image.open(input_path) as img:
        rgb = img.convert("RGB")
        width, height = rgb.size

        # Split into 5 equal top-to-bottom regions using the full width.
        # This avoids additional cropping beyond the intended "5 pieces" split.
        if height < 5:
            print(f"Skipped (too short): {input_path} size={width}x{height}")
            counters["slices_skipped_too_narrow"] += 5
            return

        base_h = height // 5
        if base_h <= 0:
            print(
                f"Skipped (invalid region height): {input_path} size={width}x{height}"
            )
            counters["slices_skipped_too_narrow"] += 5
            return

        for part_idx in range(5):
            y0 = part_idx * base_h
            # Last part takes the remaining pixels so total height is fully covered.
            y1 = (part_idx + 1) * base_h if part_idx < 4 else height

            slice_img = rgb.crop((0, y0, width, y1))
            slice_w, slice_h = slice_img.size

            # Compute average color over a (possibly smaller) vertical band inside the square.
            y0_local = int(round(slice_h * mean_y_start_frac))
            y1_local = int(round(slice_h * mean_y_end_frac))
            y0_local = max(0, min(slice_h, y0_local))
            y1_local = max(0, min(slice_h, y1_local))
            if y1_local <= y0_local:
                continue

            mean_region = slice_img.crop((0, y0_local, slice_w, y1_local))
            stat = ImageStat.Stat(mean_region)
            mean_rgb = (stat.mean[0], stat.mean[1], stat.mean[2])

            d_bg = squared_dist(mean_rgb, COLOR_BG)
            d_item = squared_dist(mean_rgb, COLOR_ITEM)

            # Higher score => closer to item color than to background.
            score = d_bg - d_item
            keep = score > 0

            out_name = f"selected_{stem}_part_{part_idx + 1}.png"
            out_path = os.path.join(output_dir, out_name)

            if keep:
                slice_img.save(out_path)
                counters["slices_kept"] += 1
            elif save_debug_all_parts:
                # Optional debug behavior: save non-selected parts separately.
                debug_name = f"discarded_{stem}_part_{part_idx + 1}.png"
                slice_img.save(os.path.join(output_dir, debug_name))

            counters["slices_processed"] += 1
            top_scores.append(
                (
                    score,
                    input_path,
                    part_idx + 1,
                    tuple(round(x, 2) for x in mean_rgb),
                    d_bg,
                    d_item,
                )
            )


def main() -> None:
    base_dir = os.path.dirname(os.path.abspath(__file__))

    # If false, only "selected_*" images are written.
    save_debug_all_parts = False

    def run_pass(mean_y_start_frac: float, mean_y_end_frac: float) -> dict:
        total_counters = {
            "input_images_processed": 0,
            "slices_processed": 0,
            "slices_kept": 0,
            "slices_skipped_too_narrow": 0,
        }

        for folder in TARGET_FOLDERS:
            folder_path = os.path.join(base_dir, folder)
            if not os.path.exists(folder_path):
                print(f"Folder not found: {folder_path}")
                continue

            folder_counters = {
                "input_images_processed": 0,
                "slices_processed": 0,
                "slices_kept": 0,
                "slices_skipped_too_narrow": 0,
            }
            top_scores: list = []
            input_paths = list(iter_input_images(folder_path))

            print(
                f"Processing folder `{folder}`: {len(input_paths)} input(s) (mean band y={mean_y_start_frac:.2f}..{mean_y_end_frac:.2f})"
            )

            for input_path in input_paths:
                folder_counters["input_images_processed"] += 1
                total_counters["input_images_processed"] += 1
                crop_and_select_slices(
                    input_path=input_path,
                    output_dir=folder_path,
                    save_debug_all_parts=save_debug_all_parts,
                    top_scores=top_scores,
                    counters=folder_counters,
                    mean_y_start_frac=mean_y_start_frac,
                    mean_y_end_frac=mean_y_end_frac,
                )

            # Per-folder summary
            top_scores.sort(key=lambda x: x[0], reverse=True)
            print(
                f"Folder `{folder}` summary: slices_processed={folder_counters['slices_processed']}, slices_kept={folder_counters['slices_kept']}"
            )
            if top_scores:
                print(f"Top item-like slices in `{folder}` (score=d_bg-d_item):")
                for row in top_scores[:5]:
                    score, input_path, part_num, mean_rgb, d_bg, d_item = row
                    print(
                        f"  score={round(score,2)} file={os.path.basename(input_path)} part={part_num} mean={mean_rgb} d_bg={round(d_bg,2)} d_item={round(d_item,2)}"
                    )

            total_counters["slices_processed"] += folder_counters["slices_processed"]
            total_counters["slices_kept"] += folder_counters["slices_kept"]
            total_counters["slices_skipped_too_narrow"] += folder_counters[
                "slices_skipped_too_narrow"
            ]

        # Overall summary
        print(
            f"Overall summary: input_images_processed={total_counters['input_images_processed']}, slices_processed={total_counters['slices_processed']}, slices_kept={total_counters['slices_kept']}"
        )
        return total_counters

    first_pass = run_pass(
        mean_y_start_frac=MEAN_Y_START_FRAC_DEFAULT,
        mean_y_end_frac=MEAN_Y_END_FRAC_DEFAULT,
    )

    if first_pass["slices_kept"] == 0:
        print(
            "No slices were kept in the full-height pass; retrying with a narrower mean band."
        )
        run_pass(
            mean_y_start_frac=MEAN_Y_START_FRAC_FALLBACK,
            mean_y_end_frac=MEAN_Y_END_FRAC_FALLBACK,
        )


if __name__ == "__main__":
    main()
