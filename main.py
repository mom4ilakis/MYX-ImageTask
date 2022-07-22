import shutil
import os
import zipfile
from io import StringIO
from pathlib import Path
from typing import List

from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

import uvicorn
from fastapi import FastAPI, Response, status, UploadFile
from fastapi.responses import FileResponse

import peewee

from image_model import Image as ImageDB

app = FastAPI()

db = peewee.SqliteDatabase('images.db')

IMAGES_FOLDER = "/images/"
THUMBNAIL_SIZE = (256, 256)


def create_thumbnail(image_path, image_name):
    thumbnail_name = image_name[:-4] + '_thumb.jpg'
    path_to_thumbnail = image_path + thumbnail_name

    if not os.path.exists(thumbnail_name):
        with Image.open(image_path) as img:
            thumbnail = img.copy()
            thumbnail.thumbnail(THUMBNAIL_SIZE)
            thumbnail.save(path_to_thumbnail)

    return path_to_thumbnail, thumbnail_name


def create_image_record(original_timestamp, filename, file_dir, img):
    gps_data = get_gps_data(img)

    record = ImageDB.create(original_timestamp=original_timestamp)

    record.file_dir = file_dir
    record.filename = filename

    record.lat_degrees = gps_data['GPSLatitude'][0]
    record.lat_minutes = gps_data['GPSLatitude'][1]
    record.lat_seconds = gps_data['GPSLatitude'][2]

    record.lon_degrees = gps_data['GPSLongitude'][0]
    record.lon_minutes = gps_data['GPSLongitude'][1]
    record.lon_seconds = gps_data['GPSLongitude'][2]

    record.lat_ref = gps_data['GPSLatitudeRef']
    record.long_ref = gps_data['GPSLongitudeRef']

    record.save()


@app.delete("/images/{image_signature}")
async def delete_image(image_signature: str, response: Response):
    record = ImageDB.select().where(ImageDB.file_signature == image_signature).get()

    if record is None:
        response.status_code = status.HTTP_200_OK
        return {"message": f"File {image_signature} deleted!"}

    path = os.path.join(IMAGES_FOLDER, record.file_signature)

    try:
        shutil.rmtree(path)
        response.status_code = status.HTTP_200_OK
        return {"message": f"File {record.file_signature} deleted!"}
    except Exception:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": f"Failed to delete file: {record.file_signature}"}
    finally:
        record.delete_instance()


@app.post("/images")
async def add_image(files: List[UploadFile], response: Response):
    for file in files:
        try:
            with Image.open(file.file) as img:
                exif_data = get_exif_data(img)
                original_timestamp = exif_data.get("DateTime")
                record = ImageDB.select().where(ImageDB.original_timestamp == original_timestamp).get

                if record is None:
                    file_dir = os.path.join(IMAGES_FOLDER + original_timestamp)

                    create_image_record(original_timestamp, file.filename, file_dir, img)

                    Path(file_dir).mkdir(parents=True, exist_ok=True)

                    img.save(os.path.join(file_dir, file.filename))

        except Exception as e:
            response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            return {"message": e.message}

    response.status_code = status.HTTP_201_CREATED
    return {"message": "Files successfully uploaded"}


@app.get("/images/{image_signature}")
async def get_image(image_signature: str, response: Response, is_thumbnail: str | None = None):
    record = ImageDB.select().where(ImageDB.file_signature == image_signature).get()

    if record is None:
        response.status_code = status.HTTP_404_NOT_FOUND

        return {"message": f"Image with signature: {image_signature} not found!"}

    image_name = record.filename
    image_path = os.path.join(IMAGES_FOLDER, record.file_signature, image_name)

    if os.path.exists(image_path) and os.path.isfile(image_path):
        response.status_code = status.HTTP_200_OK

        if is_thumbnail:
            image_path, image_name = create_thumbnail(image_path, record.filename)

        return FileResponse(image_path, filename=image_name, media_type="image/jpeg")


@app.get("/images")
async def get_geo_images(min_lat: tuple | None = None,
                         min_lon: tuple | None = None,
                         max_lat: tuple | None = None,
                         max_lon: tuple | None = None,
                         lat_ref: str = '',
                         lon_ref: str = ''):

    images = ImageDB.select().where(
        ImageDB.lon_ref == lat_ref,
        ImageDB.lat_ref == lat_ref,

        ImageDB.lat_degrees >= min_lat[0],
        ImageDB.lat_minutes >= min_lat[1],
        ImageDB.lat_seconds >= min_lat[2],

        ImageDB.lat_degrees <= max_lat[0],
        ImageDB.lat_minutes <= max_lat[1],
        ImageDB.lat_seconds <= max_lat[2],

        ImageDB.lon_degrees >= min_lon[0],
        ImageDB.lon_minutes >= min_lon[1],
        ImageDB.lon_seconds >= min_lon[2],

        ImageDB.lon_degrees <= max_lon[0],
        ImageDB.lon_minutes <= max_lon[1],
        ImageDB.lon_seconds <= max_lon[2]
    )

    zip_subdir = "images_archive"
    zip_filename = f"{zip_subdir}.zip"
    buffer = StringIO.StringIO()

    with zipfile.ZipFile(buffer, "w") as zf:
        for image in images:
            zip_path = os.path.join(zip_subdir. image.filename)
            filepath = os.path.join(image.file_dir, image.filename)

            zf.write(filepath, zip_path)

    return Response(buffer.getvalue(), media_type="application/x-zip-compressed")


def get_exif_data(image: Image):
    return {TAGS.get(k): v for k, v in image.getexif().items()}


def get_gps_data(image: Image):
    return {GPSTAGS.get(k): v for k, v in image.getexif().get_ifd(0x8825).items()}


def create_tables(db_to_init):
    with db_to_init:
        db_to_init.create_tables([ImageDB, ImageLock])


if __name__ == '__main__':
    create_tables(db)

    uvicorn.run(app, host='0.0.0.0', port=8080)
