# Image Processing Web Application

A Flask-based web application that provides three main functionalities for image processing:

1. **Image Optimizer**
   - Upload multiple images
   - Automatically optimizes image size while maintaining quality
   - Shows before/after size comparison
   - Supports various image formats (JPG, PNG, etc.)
   - Displays compression ratio and file size statistics

2. **Background Remover**
   - Upload multiple images
   - Automatically removes image backgrounds
   - Optimizes the resulting images
   - Shows size statistics and compression ratio
   - Exports as PNG with transparency
   - Includes post-processing for better edge quality

3. **Image Cloner**
   - Input any website URL
   - Downloads all images from the website
   - Filters out small images and icons
   - Shows image previews and sizes
   - Supports bulk download
   - Handles various image sources (direct images, background images)

## Technologies Used

- **Backend:**
  - Flask (Python web framework)
  - rembg (Background removal)
  - Pillow (Image processing)
  - Playwright (Web scraping)
  - BeautifulSoup4 (HTML parsing)

- **Frontend:**
  - Bootstrap 5 (UI framework)
  - JavaScript (AJAX, DOM manipulation)
  - HTML/CSS

## Installation

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # For Linux/MacOS
source venv/Scripts/activate  # For Windows
```

2. Install Python requirements:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python app.py
```

4. Open your web browser and navigate to:
```
http://localhost:5000
```

## Usage
1. Click the upload area or drag and drop images onto it
2. Select one or multiple image files
3. Click "Check Sizes" to view the dimensions and file sizes
4. Results will be displayed below the upload area 