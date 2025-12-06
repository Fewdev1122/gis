from flask import Flask, request, render_template
import easyocr
import torch
import numpy as np
from PIL import Image, ImageOps
import io
import base64
import exifread

# --- ส่วนจัดการ HEIC ---
# พยายามใช้ pillow_heif ก่อนเพราะเสถียรกว่าและแก้ปัญหา cffi struct size mismatch ได้
try:
    import pillow_heif
    pillow_heif.register_heif_opener() # ลงทะเบียนกับ PIL ให้เปิด HEIC ได้เลย
    USE_PILLOW_HEIF = True
    print("Using pillow-heif for HEIC support.")
except ImportError:
    USE_PILLOW_HEIF = False
    print("pillow-heif not found. Falling back to pyheif (may be unstable).")

# ลอง import pyheif ไว้เป็น fallback (ถ้าไม่มี pillow-heif)
try:
    import pyheif
    HAS_PYHEIF = True
except ImportError:
    HAS_PYHEIF = False
# ---------------------

app = Flask(__name__)

# ตรวจสอบ GPU
use_gpu = torch.cuda.is_available()
print(f"Using GPU: {use_gpu}")
reader = easyocr.Reader(['th','en'], gpu=use_gpu)

# ฟังก์ชันแปลง HEIC กรณีใช้ pyheif (Legacy Fallback)
def pyheif_to_jpeg_bytes(file_bytes):
    if not HAS_PYHEIF:
        raise ImportError("pyheif not installed")
        
    try:
        heif_file = pyheif.read(io.BytesIO(file_bytes))
        img = Image.frombytes(
            heif_file.mode,
            heif_file.size,
            heif_file.data,
            "raw",
            heif_file.mode,
            heif_file.stride,
        )
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        return buf.getvalue()
    except Exception as e:
        # ดักจับ Error CFFI/Struct Mismatch ที่นี่
        print(f"pyheif internal error: {e}")
        raise e

# ฟังก์ชันช่วยโหลดภาพที่ปลอดภัย (Safe Load)
def load_image_safe(file_bytes):
    # 1. ลองเปิดแบบปกติ (รวมถึง HEIC ถ้ามี pillow-heif register ไว้แล้ว)
    try:
        img = Image.open(io.BytesIO(file_bytes))
        img.load() # บังคับโหลดเพื่อเช็คไฟล์
        return img
    except Exception as e_open:
        # print(f"Standard open failed: {e_open}")
        
        # 2. ถ้าเปิดไม่ได้ และไม่มี pillow-heif ให้ลองใช้ pyheif แบบ Manual
        if not USE_PILLOW_HEIF and HAS_PYHEIF:
            try:
                print("Attempting manual pyheif conversion...")
                jpg_bytes = pyheif_to_jpeg_bytes(file_bytes)
                img = Image.open(io.BytesIO(jpg_bytes))
                img.load()
                return img
            except Exception as e_heif:
                print(f"Manual pyheif conversion failed: {e_heif}")
                return None
        else:
            print(f"Cannot open image. pillow-heif: {USE_PILLOW_HEIF}, pyheif: {HAS_PYHEIF}")
            return None

# ดึง GPS จาก EXIF
def get_gps_from_exif(file_bytes):
    try:
        tags = exifread.process_file(io.BytesIO(file_bytes), details=False)
        
        if 'GPS GPSLatitude' not in tags or 'GPS GPSLongitude' not in tags:
            return None, None

        lat_ref = tags.get('GPS GPSLatitudeRef').printable
        lat = tags.get('GPS GPSLatitude').values
        lon_ref = tags.get('GPS GPSLongitudeRef').printable
        lon = tags.get('GPS GPSLongitude').values

        def dms_to_decimal(dms, ref):
            decimal = float(dms[0].num)/dms[0].den + \
                      float(dms[1].num)/dms[1].den/60 + \
                      float(dms[2].num)/dms[2].den/3600
            if ref in ['S','W']:
                decimal = -decimal
            return decimal

        latitude = dms_to_decimal(lat, lat_ref)
        longitude = dms_to_decimal(lon, lon_ref)
        return latitude, longitude
    except Exception as e:
        print(f"GPS Error: {e}")
        return None, None

# OCR ด้วย EasyOCR
def extract_text_from_image(file_bytes):
    try:
        img = load_image_safe(file_bytes)
        
        if img is None:
            return "Error: Cannot identify/open image file. Please install 'pillow-heif'."

        # หมุนภาพตาม EXIF Orientation
        img = ImageOps.exif_transpose(img)
        img = img.convert('RGB')
        
        img_np = np.array(img)
        
        result = reader.readtext(img_np)
        
        text = "\n".join([t for bbox, t, prob in result])
        return text.strip()
    except Exception as e:
        print("OCR Error:", e)
        return f"Error reading text: {str(e)}"

# แปลงเป็น base64 เพื่อแสดงภาพ
def file_to_base64(file_bytes):
    try:
        img = load_image_safe(file_bytes)
        
        if img is None:
            return base64.b64encode(file_bytes).decode('utf-8')

        img = ImageOps.exif_transpose(img)
        img = img.convert('RGB')
        
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        return base64.b64encode(buf.getvalue()).decode('utf-8')
    except:
        return base64.b64encode(file_bytes).decode('utf-8')

@app.route("/", methods=["GET","POST"])
def index():
    gps = None
    ocr_text = None
    img_base64 = None

    if request.method == "POST":
        file = request.files.get('image')
        if file:
            file_bytes = file.read()
            
            gps = get_gps_from_exif(file_bytes)
            ocr_text = extract_text_from_image(file_bytes)
            img_base64 = file_to_base64(file_bytes)

    return render_template("index.html", gps=gps, ocr_text=ocr_text, img_base64=img_base64)

if __name__ == "__main__":
    app.run(debug=True)