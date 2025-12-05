from flask import Flask, request, render_template
import exifread

app = Flask(__name__)

def get_gps_from_exif(file):
    tags = exifread.process_file(file, details=False)
    try:
        lat_ref = tags['GPS GPSLatitudeRef'].printable
        lat = tags['GPS GPSLatitude'].values
        lon_ref = tags['GPS GPSLongitudeRef'].printable
        lon = tags['GPS GPSLongitude'].values

        # แปลง DMS → Decimal
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

@app.route("/", methods=["GET", "POST"])
def index():
    gps = None
    if request.method == "POST":
        file = request.files['image']
        gps = get_gps_from_exif(file)
    return render_template("index.html", gps=gps)

if __name__ == "__main__":
    app.run(debug=True)
