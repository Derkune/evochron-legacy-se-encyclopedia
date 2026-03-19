import argparse
import glob
import json
import os
import sys
from typing import Iterable, Optional

from PIL import Image
from google import genai


DEFAULT_MODEL = "gemini-1.5-pro"
DEFAULT_MAX_OUTPUT_TOKENS = 4096


def build_prompt(lang: str) -> str:
    # Encourage "OCR-like" behavior and keep output strictly to text.
    return (
        "Extract ALL text from the image as accurately as possible. "
        "Preserve the original layout as best as possible using line breaks. "
        "Return plain text ONLY (no markdown, no explanations, no quotes). "
        f"Language context: {lang}."
    )


def expand_paths(patterns: Iterable[str]) -> Iterable[str]:
    for p in patterns:
        # Expand globs like *.jpg (works on Windows when user quotes patterns).
        if any(ch in p for ch in ["*", "?", "["]):
            for match in glob.glob(p, recursive=True):
                yield match
        else:
            yield p


def extract_text(
    client: genai.Client,
    image_path: str,
    model: str,
    prompt: str,
    max_output_tokens: int,
) -> str:
    with Image.open(image_path) as img:
        # Gemini works better with RGB; also avoids passing file handles around.
        img = img.convert("RGB")

        # google-genai accepts PIL.Image.Image directly as part of `contents`.
        response = client.models.generate_content(
            model=model,
            contents=[img, prompt],
            config={
                "temperature": 0,
                "max_output_tokens": max_output_tokens,
            },
        )

    # GenerateContentResponse provides `.text`.
    text = (getattr(response, "text", None) or "").strip()
    return text


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract text from image files using Google Gemini (via google-genai)."
    )
    parser.add_argument(
        "image_paths",
        nargs="+",
        help="One or more image paths or glob patterns (e.g. commodities/*.jpg).",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Gemini model name (default: {DEFAULT_MODEL}).",
    )
    parser.add_argument(
        "--lang",
        default="English",
        help="Language context to help OCR accuracy (default: English).",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="Gemini API key. If omitted, uses GEMINI_API_KEY or GOOGLE_API_KEY env vars.",
    )
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=DEFAULT_MAX_OUTPUT_TOKENS,
        help=f"Max output tokens for the model (default: {DEFAULT_MAX_OUTPUT_TOKENS}).",
    )
    parser.add_argument(
        "--jsonl-output",
        default=None,
        help="Optional path to write results as JSONL: {path, text}.",
    )
    parser.add_argument(
        "--no-headers",
        action="store_true",
        help="If set, only print extracted text (still separated by a blank line).",
    )

    args = parser.parse_args(argv)

    api_key = args.api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print(
            "Missing API key. Provide --api-key or set GEMINI_API_KEY / GOOGLE_API_KEY env vars.",
            file=sys.stderr,
        )
        return 2

    client = genai.Client(api_key=api_key)
    prompt = build_prompt(args.lang)

    out_fp = None
    if args.jsonl_output:
        out_dir = os.path.dirname(os.path.abspath(args.jsonl_output))
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir, exist_ok=True)
        out_fp = open(args.jsonl_output, "w", encoding="utf-8")

    processed_any = False
    try:
        for path in expand_paths(args.image_paths):
            if not os.path.isfile(path):
                print(f"[skip] Not a file: {path}", file=sys.stderr)
                continue

            processed_any = True
            try:
                text = extract_text(
                    client=client,
                    image_path=path,
                    model=args.model,
                    prompt=prompt,
                    max_output_tokens=args.max_output_tokens,
                )
            except Exception as e:
                print(f"[error] Failed {path}: {e}", file=sys.stderr)
                if out_fp:
                    out_fp.write(json.dumps({"path": path, "text": "", "error": str(e)}, ensure_ascii=False) + "\n")
                continue

            if out_fp:
                out_fp.write(json.dumps({"path": path, "text": text}, ensure_ascii=False) + "\n")
                out_fp.flush()

            if args.no_headers:
                print(text)
                print()
            else:
                print(f"=== {path} ===")
                print(text)
                print()

    finally:
        if out_fp:
            out_fp.close()

    if not processed_any:
        print("No valid image files found.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

