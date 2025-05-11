"""
resize_icon.py

Utility script to resize PNG images for use as status icons in SCLogAnalyzer.

Usage:
    python resize_icon.py --input input.png --output output.png --size 8

Dependencies:
    pip install pillow

"""
import argparse
from PIL import Image

def resize_png(input_path, output_path, size):
    with Image.open(input_path) as img:
        img = img.convert("RGBA")
        img = img.resize((size, size), Image.LANCZOS)
        img.save(output_path, format="PNG")
        print(f"Saved resized icon to {output_path} ({size}x{size}px)")

def main():
    parser = argparse.ArgumentParser(description="Resize a PNG image to a square icon of given size.")
    parser.add_argument('--input', required=True, help='Path to input PNG file')
    parser.add_argument('--output', required=True, help='Path to output PNG file')
    parser.add_argument('--size', type=int, default=8, help='Icon size in pixels (default: 8)')
    args = parser.parse_args()
    resize_png(args.input, args.output, args.size)

if __name__ == "__main__":
    main()
