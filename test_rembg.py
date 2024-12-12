from rembg import remove
from PIL import Image

# Load input image
input_path = "input.png"  # replace with your image path
output_path = "output.png"

# Load image
input_image = Image.open(input_path)

# Remove background
output_image = remove(input_image)

# Save result
output_image.save(output_path) 