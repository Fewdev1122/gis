from flask import Flask, request, render_template
import exifread
import easyocr
import numpy as np
import cv2
import torch
import base64

app = Flask(__name__)

use_gpu = torch.cuda.is_available()
reader = easyocr.Reader(['th','en'], gpu=use_gpu)

def get_gps_from_exif(file):
    try:
        tags = exifread.process_file(file, details=False)
        lat_ref = tags['GPS GPSLatitudeRef'].printable
        lat = tags['GPS GPSLatitude'].values
        lon_ref = tags['GPS GPSLongitudeRef'].printable
        lon = tags['GPS GPSLongitude'].values

        def dms_to_decimal(dms, ref):
            decimal = float(dms[0].num)/dms[0].den + \
                      float(dms[1].num)/dms[1].den/60 + \
                      float(dms[2].num)/dms[2].den/3600
            if ref in ['S', 'W']:
                decimal = -decimal
            return decimal

        latitude = dms_to_decimal(lat, lat_ref)
        longitude = dms_to_decimal(lon, lon_ref)
        return latitude, longitude
    except KeyError:
        return None, None

def extract_text_from_image_easyocr(file):
    try:
        file_bytes = np.frombuffer(file.read(), np.uint8)
        img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        if img is None:
            return "Error: ไม่สามารถ decode image ได้"
        result = reader.readtext(img)
        text = "\n".join([t for bbox, t, prob in result])
        return text.strip()
    except Exception as e:
        print("OCR Error:", e)
        return None

def file_to_base64(file):
    file.seek(0)
    data = file.read()
    return base64.b64encode(data).decode('utf-8')

@app.route("/", methods=["GET", "POST"])
def index():
    gps = None
    ocr_text = None
    img_base64 = None
    if request.method == "POST":
        file = request.files['image']
        if file:
            # แปลงไฟล์เป็น base64 เพื่อแสดงภาพ
            img_base64 = file_to_base64(file)

            # ดึง GPS
            file.seek(0)
            gps = get_gps_from_exif(file)

            # ดึง OCR
            file.seek(0)
            ocr_text = extract_text_from_image_easyocr(file)

    return render_template("index.html", gps=gps, ocr_text=ocr_text, img_base64=img_base64)

if __name__ == "__main__":
    app.run(debug=True)
