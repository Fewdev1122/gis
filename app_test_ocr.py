from flask import Flask, request, render_template
import easyocr
import numpy as np
import cv2
import torch  # สำหรับเช็ค GPU

app = Flask(__name__)

# ตรวจสอบว่ามี GPU หรือไม่
use_gpu = torch.cuda.is_available()
print(f"Using GPU: {use_gpu}")

# สร้าง EasyOCR reader
reader = easyocr.Reader(['th', 'en'], gpu=use_gpu)

@app.route("/", methods=["GET", "POST"])
def index():
    ocr_text = None
    if request.method == "POST":
        file = request.files['image']
        if file:
            file_bytes = np.frombuffer(file.read(), np.uint8)
            img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
            if img is None:
                ocr_text = "Error: ไม่สามารถ decode image ได้"
            else:
                result = reader.readtext(img)
                ocr_text = "\n".join([text for bbox, text, prob in result])
    return render_template("index_easyocr.html", ocr_text=ocr_text)

if __name__ == "__main__":
    app.run(debug=True)
