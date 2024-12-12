from flask import Flask, render_template, request, jsonify, send_file
from rembg import remove
from PIL import Image, ImageFilter, ImageEnhance
import requests
from bs4 import BeautifulSoup
import os
from io import BytesIO
import urllib.parse
import base64
import re
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time
import json
from playwright.sync_api import sync_playwright

app = Flask(__name__)

# Ensure the upload and download directories exist
UPLOAD_FOLDER = 'uploads'
DOWNLOAD_FOLDER = 'downloads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

def format_size(size_bytes):
    kb = size_bytes / 1024
    mb = kb / 1024
    if mb < 1:
        return f'{kb:.2f} KB'
    return f'{mb:.2f} MB'

def resize_image(img, max_size=1200):
    """Resize image while maintaining aspect ratio"""
    width, height = img.size
    if max(width, height) > max_size:
        ratio = max_size / max(width, height)
        new_size = (int(width * ratio), int(height * ratio))
        return img.resize(new_size, Image.Resampling.LANCZOS)
    return img

def remove_background(img):
    """Remove background using rembg"""
    # Convert image to bytes
    img_byte = BytesIO()
    img.save(img_byte, format='PNG')
    img_byte.seek(0)
    
    # Remove background
    output = remove(img_byte.read())
    
    # Convert back to PIL Image
    result = Image.open(BytesIO(output))
    
    # Apply some post-processing
    enhancer = ImageEnhance.Contrast(result)
    result = enhancer.enhance(1.2)
    
    # Smooth edges
    result = result.filter(ImageFilter.SMOOTH_MORE)
    
    return result

def aggressive_optimize(img, format_type):
    """Aggressively optimize image size while maintaining acceptable quality"""
    quality_levels = [80, 60, 40, 20]
    best_size = float('inf')
    best_buffer = None
    target_size = 300 * 1024  # Target 300KB
    
    for quality in quality_levels:
        buffer = BytesIO()
        if format_type == 'PNG':
            img.save(buffer, format='PNG', optimize=True, quality=quality)
        else:
            img.save(buffer, format='JPEG', quality=quality, optimize=True)
        
        size = buffer.tell()
        if size < best_size:
            best_size = size
            best_buffer = buffer
        
        if size < target_size:
            break
    
    if best_size > target_size:
        scale_factors = [0.9, 0.8, 0.7, 0.6]
        for scale in scale_factors:
            new_size = (int(img.size[0] * scale), int(img.size[1] * scale))
            resized_img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            buffer = BytesIO()
            if format_type == 'PNG':
                resized_img.save(buffer, format='PNG', optimize=True)
            else:
                resized_img.save(buffer, format='JPEG', quality=60, optimize=True)
            
            size = buffer.tell()
            if size < best_size:
                best_size = size
                best_buffer = buffer
            
            if size < target_size:
                break
    
    return best_buffer, best_size

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/optimize_images', methods=['POST'])
def optimize_images_endpoint():
    if 'images[]' not in request.files:
        return jsonify({'error': 'No images provided'})
    
    files = request.files.getlist('images[]')
    remove_bg = request.form.get('remove_bg') == 'true'
    results = []
    
    for file in files:
        try:
            # Read the original image and get its size
            img = Image.open(file)
            file.seek(0, os.SEEK_END)
            original_size = file.tell()
            file.seek(0)
            
            # Process the image
            img = resize_image(img)
            
            if remove_bg:
                img = remove_background(img)
                format_type = 'PNG'
            else:
                format_type = 'JPEG'
                if img.mode == 'RGBA':
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[3])
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
            
            # Optimize the image
            optimized_buffer, size_bytes = aggressive_optimize(img, format_type)
            
            # Convert to base64
            optimized_buffer.seek(0)
            img_str = base64.b64encode(optimized_buffer.getvalue()).decode()
            
            # Generate filename
            original_name = os.path.splitext(file.filename)[0]
            suffix = '_nobg' if remove_bg else '_optimized'
            optimized_filename = f"{original_name}{suffix}.{format_type.lower()}"
            
            # Calculate compression ratio
            compression_ratio = ((original_size - size_bytes) / original_size) * 100
            
            results.append({
                'success': True,
                'original_name': file.filename,
                'data': f'data:image/{format_type.lower()};base64,{img_str}',
                'size': format_size(size_bytes),
                'original_size': format_size(original_size),
                'compression_ratio': f'{compression_ratio:.1f}%',
                'filename': optimized_filename,
                'type': f'image/{format_type.lower()}'
            })
        except Exception as e:
            results.append({
                'success': False,
                'original_name': file.filename,
                'error': str(e)
            })
    
    return jsonify({'results': results})

@app.route('/clone-images', methods=['POST'])
def clone_images():
    url = request.form.get('url')
    if not url:
        return jsonify({'error': 'No URL provided'}), 400

    try:
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        downloaded_images = []
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            
            page = context.new_page()
            
            try:
                # Go to URL and wait for network idle
                page.goto(url, wait_until='networkidle')
                
                # Scroll to load all content
                for _ in range(5):
                    page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                    page.wait_for_timeout(1000)
                
                # Get all image URLs
                image_urls = set()
                
                # Get src and data-src from img tags
                for img in page.query_selector_all('img'):
                    try:
                        src = img.get_attribute('src')
                        if src and not src.startswith('data:'):
                            image_urls.add(src)
                        data_src = img.get_attribute('data-src')
                        if data_src and not data_src.startswith('data:'):
                            image_urls.add(data_src)
                    except:
                        continue
                
                # Get background images
                elements = page.query_selector_all('*')
                for element in elements:
                    try:
                        style = page.evaluate('el => window.getComputedStyle(el).backgroundImage', element)
                        if style and style != 'none':
                            url_match = re.search(r'url\(["\']?(.*?)["\']?\)', style)
                            if url_match:
                                image_urls.add(url_match.group(1))
                    except:
                        continue

                # Download images
                session = requests.Session()
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Referer': url
                }

                for img_url in image_urls:
                    try:
                        # Clean up URL
                        if img_url.startswith('//'):
                            img_url = 'https:' + img_url
                        elif not img_url.startswith(('http://', 'https://')):
                            img_url = urllib.parse.urljoin(url, img_url)

                        # Skip small images and icons
                        if any(skip in img_url.lower() for skip in ['icon', 'logo', 'avatar', 'thumb']):
                            continue

                        # Download image
                        img_response = session.get(img_url, headers=headers, verify=False, timeout=10)
                        
                        if img_response.status_code == 200 and 'image' in img_response.headers.get('content-type', ''):
                            # Get file size
                            file_size = len(img_response.content)
                            if file_size < 10 * 1024:  # Skip images smaller than 10KB
                                continue

                            # Generate filename
                            filename = f"image_{len(downloaded_images) + 1}.jpg"
                            filepath = os.path.join(DOWNLOAD_FOLDER, filename)
                            
                            with open(filepath, 'wb') as f:
                                f.write(img_response.content)
                            
                            downloaded_images.append({
                                'url': img_url,
                                'filename': filename,
                                'path': f'/downloads/{filename}',
                                'size': format_size(file_size)
                            })
                    except Exception as e:
                        print(f"Error downloading {img_url}: {str(e)}")
                        continue

            finally:
                browser.close()

        if not downloaded_images:
            return jsonify({'message': 'No images found on the webpage'}), 404

        return jsonify({
            'message': f'Successfully downloaded {len(downloaded_images)} images',
            'images': downloaded_images
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Add route to serve downloaded images
@app.route('/downloads/<path:filename>')
def download_file(filename):
    return send_file(os.path.join(DOWNLOAD_FOLDER, filename))

@app.route('/remove_bg', methods=['POST'])
def remove_bg_endpoint():
    if 'images[]' not in request.files:
        return jsonify({'error': 'No images provided'})
    
    files = request.files.getlist('images[]')
    results = []
    
    for file in files:
        try:
            # Read the original image and get its size
            img = Image.open(file)
            file.seek(0, os.SEEK_END)
            original_size = file.tell()
            file.seek(0)
            
            # Remove background
            img = remove_background(img)
            
            # Resize and optimize
            img = resize_image(img)
            optimized_buffer, size_bytes = aggressive_optimize(img, 'PNG')
            
            # Convert to base64
            optimized_buffer.seek(0)
            img_str = base64.b64encode(optimized_buffer.getvalue()).decode()
            
            # Generate filename
            original_name = os.path.splitext(file.filename)[0]
            output_filename = f"{original_name}_nobg.png"
            
            # Calculate compression ratio
            compression_ratio = ((original_size - size_bytes) / original_size) * 100
            
            results.append({
                'success': True,
                'original_name': file.filename,
                'data': f'data:image/png;base64,{img_str}',
                'size': format_size(size_bytes),
                'original_size': format_size(original_size),
                'compression_ratio': f'{compression_ratio:.1f}%',
                'filename': output_filename,
                'type': 'image/png'
            })
        except Exception as e:
            results.append({
                'success': False,
                'original_name': file.filename,
                'error': str(e)
            })
    
    return jsonify({'results': results})

if __name__ == '__main__':
    app.run(debug=True) 