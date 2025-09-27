import base64
from PIL import Image
from io import BytesIO
import os

# This script will help process the image you provide
def split_image_to_grid(img, output_dir='grid_output'):
    # Create output directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    width, height = img.size
    
    # Calculate the size of each grid cell
    cell_width = width // 3
    cell_height = height // 3
    
    # Split into 9 parts (3x3 grid)
    count = 1
    for row in range(3):
        for col in range(3):
            # Calculate the box coordinates
            left = col * cell_width
            top = row * cell_height
            right = left + cell_width
            bottom = top + cell_height
            
            # Crop the image
            cropped = img.crop((left, top, right, bottom))
            
            # Save the cropped image
            output_path = os.path.join(output_dir, f'grid_{count:02d}.png')
            cropped.save(output_path, 'PNG')
            print(f'Saved: {output_path} (Size: {cropped.size})')
            count += 1
    
    print(f'\nSuccessfully split image into 9 parts in {output_dir}/')
    
    # Create a preview montage showing the grid layout
    preview = Image.new('RGBA', (cell_width * 3 + 20, cell_height * 3 + 20), (255, 255, 255, 0))
    
    count = 1
    for row in range(3):
        for col in range(3):
            piece_path = os.path.join(output_dir, f'grid_{count:02d}.png')
            piece = Image.open(piece_path)
            preview.paste(piece, (col * cell_width + col * 10, row * cell_height + row * 10))
            count += 1
    
    preview_path = os.path.join(output_dir, 'preview_grid.png')
    preview.save(preview_path)
    print(f'Preview saved: {preview_path}')
    
    return output_dir

print("Image splitting script ready!")
print("Please save your image as 'input.png' and run:")
print("python3 -c \"from PIL import Image; import process_image; img = Image.open('input.png'); process_image.split_image_to_grid(img)\"")
