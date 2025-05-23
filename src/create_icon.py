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
        icon_images = []
        if hasattr(icon, 'n_frames') and icon.n_frames > 1:
            for i in range(icon.n_frames):
                icon.seek(i)
                img = icon.copy()
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')
                icon_images.append(img)
        else:
            if icon.mode != 'RGBA':
                icon = icon.convert('RGBA')
            icon_images = [icon]
        
        # Standard sizes we want in our final icon
        standard_sizes = [16, 32, 48, 64, 128, 256]
        
        # Check existing sizes and identify missing ones
        existing_sizes = [(img.width, img.height) for img in icon_images]
        print(f"Extracted icon sizes: {existing_sizes}")
        
        # Final images list with all required sizes
        images = []
        
        # Process each standard size
        for size in standard_sizes:
            # Check if this size already exists
            existing_img = None
            for img in icon_images:
                if img.width == size and img.height == size:
                    existing_img = img
                    break
            
            # If size doesn't exist, create it by resizing the closest larger image
            if existing_img is None:
                # Find the closest larger image to resize from
                source_img = None
                for img in sorted(icon_images, key=lambda x: x.width):
                    if img.width >= size:
                        source_img = img
                        break
                
                # If no larger image, use the largest available
                if source_img is None and icon_images:
                    source_img = max(icon_images, key=lambda x: x.width)
                
                # Resize the source image to create the missing size
                if source_img:
                    existing_img = source_img.resize((size, size), Image.Resampling.LANCZOS)
                    print(f"Created missing size: {size}x{size}")
                else:
                    # Fallback: create a new blank image
                    existing_img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
                    print(f"Created blank image for size: {size}x{size}")
            
            # Add to our final list
            images.append(existing_img)
        
        # Add text to each image
        for i, img in enumerate(images):
            draw = ImageDraw.Draw(img)
            
            # Choose font size based on image size - using smaller ratio for better fit
            size = min(img.width, img.height)
            font_size = max(8, size // 5)  # Smaller ratio to ensure text fits better
            
            try:
                font = ImageFont.truetype("arial.ttf", font_size)
            except IOError:
                font = ImageFont.load_default()
            
            # Calculate text position (centered)
            left, top, right, bottom = font.getbbox(text)
            text_width = right - left
            text_height = bottom - top
            
            # Adjust position to ensure text is properly centered
            # For small sizes, we might need additional adjustments
            position_x = (img.width - text_width) // 2
            position_y = (img.height - text_height) // 2 - (top // 2)  # Adjusted vertical alignment
            
            # For very small icons, move text up slightly to be more visible
            if size <= 32:
                position_y = max(1, position_y - 1)
            
            # Draw the text with a slight shadow for better visibility
            # For small icons, we might skip the shadow to avoid blurriness
            if size > 32:
                draw.text((position_x+1, position_y+1), text, fill=(0, 0, 0, 180), font=font)
            
            draw.text((position_x, position_y), text, fill=text_color, font=font)
        
        # Save as .ico file with all the sizes
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
