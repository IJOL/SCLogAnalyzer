#!/usr/bin/env python
from PIL import Image, ImageDraw, ImageFont
import os
import sys
import subprocess
import tempfile

def extract_icon_from_exe(exe_path, output_path, text="LOG", text_color=(255, 0, 0, 255)):
    """
    Extract the icon from an executable file
    Args:
        exe_path: Path to the executable file
        output_path: Path where to save the extracted icon
        text: Text to add to the icon (default: "LOG")
        text_color: Color of the text (default: red)
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # For Windows, we can use PowerShell to extract the icon
        if sys.platform == "win32":
            # Create a temporary .ico file
            with tempfile.NamedTemporaryFile(suffix='.ico', delete=False) as temp_file:
                temp_path = temp_file.name
            
            # PowerShell command to extract icon
            ps_command = f"""
            Add-Type -AssemblyName System.Drawing
            $icon = [System.Drawing.Icon]::ExtractAssociatedIcon('{exe_path}')
            $icon.ToBitmap().Save('{temp_path}')
            """
            
            # Run PowerShell command
            subprocess.run(["powershell", "-Command", ps_command], capture_output=True)
            
            # Load the icon and convert it
            if os.path.exists(temp_path):
                add_text_to_icon(temp_path, output_path, text, text_color)
                os.remove(temp_path)
                return True
        else:
            print("Icon extraction is currently only supported on Windows.")
            return False
            
    except Exception as e:
        print(f"Failed to extract icon: {e}")
        return False

def add_text_to_icon(icon_path, output_path, text, text_color):
    """
    Add text to an existing icon
    Args:
        icon_path: Path to the original icon
        output_path: Path where to save the modified icon
        text: Text to add to the icon
        text_color: Color of the text (RGBA)
    """
    try:
        # Open the icon
        icon = Image.open(icon_path)
        
        # Convert icon to a list of images (in case it contains multiple sizes)
        if hasattr(icon, 'n_frames') and icon.n_frames > 1:
            images = []
            for i in range(icon.n_frames):
                icon.seek(i)
                img = icon.copy()
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')
                images.append(img)
        else:
            if icon.mode != 'RGBA':
                icon = icon.convert('RGBA')
            images = [icon]
        
        # Add text to each image
        for i, img in enumerate(images):
            draw = ImageDraw.Draw(img)
            
            # Choose font size based on image size
            size = min(img.width, img.height)
            font_size = max(10, size // 4)  # Adjust font size for readability
            
            try:
                font = ImageFont.truetype("arial.ttf", font_size)
            except IOError:
                font = ImageFont.load_default()
            
            # Calculate text position (centered)
            left, top, right, bottom = font.getbbox(text)
            text_width = right - left
            text_height = bottom - top
            
            # Position text in center
            position = ((img.width - text_width) // 2, (img.height - text_height) // 2 - top)
            
            # Draw the text with a slight shadow for better visibility
            draw.text((position[0]+1, position[1]+1), text, fill=(0, 0, 0, 180), font=font)
            draw.text(position, text, fill=text_color, font=font)
            
            images[i] = img
        
        # Save as .ico file
        images[0].save(
            output_path,
            format='ICO',
            sizes=[(image.width, image.height) for image in images],
            append_images=images[1:]
        )
        
        print(f"Modified icon saved successfully at: {output_path}")
        return True
    
    except Exception as e:
        print(f"Failed to add text to icon: {e}")
        return False

def create_icon(output_path):
    """
    Create a simple icon for SCLogAnalyzer
    Args:
        output_path: Path where to save the icon file
    """
    # Define image sizes for the icon (Windows icons typically include multiple sizes)
    sizes = [16, 32, 48, 64, 128, 256]
    
    # Create a list to store different size images
    images = []
    
    for size in sizes:
        # Create a blank image with transparency
        image = Image.new('RGBA', (size, size), color=(0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        
        # Draw a blue circle background
        circle_color = (30, 100, 200, 255)  # Blue color
        draw.ellipse([(0, 0), (size, size)], fill=circle_color)
        
        # Try to add text "SC" in the middle
        try:
            # Try to use a built-in font with appropriate size
            font_size = size // 2
            try:
                font = ImageFont.truetype("arial.ttf", font_size)
            except IOError:
                # Fallback to default font if arial.ttf is not available
                font = ImageFont.load_default()
            
            # Calculate text position to center it
            text = "SC"
            # Use textbbox instead of textsize (which is deprecated)
            left, top, right, bottom = font.getbbox(text)
            text_width = right - left
            text_height = bottom - top
            position = ((size - text_width) // 2, (size - text_height) // 2 - top)  # Adjust for baseline
            
            # Draw the text in white
            draw.text(position, text, fill=(255, 255, 255, 255), font=font)
        except Exception as e:
            # Fallback if font rendering fails
            print(f"Font rendering failed for size {size}: {e}")
            # Draw a simple white cross instead
            line_width = max(1, size // 16)
            draw.line([(size//4, size//2), (3*size//4, size//2)], fill=(255, 255, 255, 255), width=line_width)
            draw.line([(size//2, size//4), (size//2, 3*size//4)], fill=(255, 255, 255, 255), width=line_width)
        
        images.append(image)
    
    # Save as .ico file
    images[0].save(
        output_path,
        format='ICO',
        sizes=[(image.width, image.height) for image in images],
        append_images=images[1:]
    )
    
    print(f"Icon created successfully at: {output_path}")

def create_star_citizen_icon(output_path):
    """
    Create an icon based on StarCitizen.exe with "LOG" text
    Args:
        output_path: Path where to save the icon file
    """
    sc_exe_path = r"E:\Roberts Space Industries\StarCitizen\LIVE\Bin64\StarCitizen.exe"
    
    if not os.path.exists(sc_exe_path):
        print(f"StarCitizen executable not found at: {sc_exe_path}")
        return False
    
    print(f"Extracting icon from StarCitizen: {sc_exe_path}")
    return extract_icon_from_exe(sc_exe_path, output_path, "LOG", (255, 0, 0, 255))

if __name__ == "__main__":
    # Get the directory of the script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Set the output path for the icon
    output_path = os.path.join(script_dir, "SCLogAnalyzer.ico")
    
    # Try to create icon from StarCitizen.exe first
    if create_star_citizen_icon(output_path):
        print("StarCitizen icon extracted and modified successfully.")
    # Check if user provided a custom exe path
    elif len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        print(f"Extracting icon from: {sys.argv[1]}")
        if extract_icon_from_exe(sys.argv[1], output_path):
            print("Icon extraction and modification completed.")
        else:
            print("Falling back to creating a new icon...")
            create_icon(output_path)
    else:
        # Create a new icon
        create_icon(output_path)
