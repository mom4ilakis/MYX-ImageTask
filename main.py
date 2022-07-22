import shutil
import os
import zipfile
from io import BytesIO
from pathlib import Path
from typing import List

from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

import uvicorn
from fastapi import FastAPI, Response, status, UploadFile
from fastapi.responses import FileResponse

import peewee

from image_model import Image as ImageModel

app = FastAPI()


IMAGES_FOLDER = "images"
THUMBNAIL_SIZE = (256, 256)


def create_thumbnail(image_path, image_name):
    thumbnail_name = image_name[:-4] + '_thumb.jpg'
    path_to_thumbnail = image_path.split(image_name)[0] + thumbnail_name

    if not os.path.exists(thumbnail_name):
        with Image.open(image_path) as img:
            thumbnail = img.copy()
            thumbnail.thumbnail(THUMBNAIL_SIZE)
            thumbnail.save(path_to_thumbnail)
            thumbnail.close()
            img.close()

    return path_to_thumbnail, thumbnail_name


def create_image_record(original_timestamp, filename, file_dir, img):
    gps_data = get_gps_data(img)

    ImageModel.create(
        original_timestamp=original_timestamp,
        filename=filename,
        file_dir=file_dir,
        lat_degrees=gps_data['GPSLatitude'][0],
        lat_minutes=gps_data['GPSLatitude'][1],
        lat_seconds=gps_data['GPSLatitude'][2],
        lon_degrees=gps_data['GPSLongitude'][0],
        lon_minutes=gps_data['GPSLongitude'][1],
        lon_seconds=gps_data['GPSLongitude'][2],
        lat_ref=gps_data['GPSLatitudeRef'],
        lon_ref=gps_data['GPSLongitudeRef'],
    )


@app.delete("/images/{image_signature}")
async def delete_image(image_signature: str, response: Response):
    record = ImageModel.select().where(ImageModel.original_timestamp == image_signature).get()

    if record is None:
        response.status_code = status.HTTP_200_OK
        return {"message": f"File {image_signature} deleted!"}

    path = os.path.join(IMAGES_FOLDER, record.original_timestamp)

    try:
        shutil.rmtree(path)
        response.status_code = status.HTTP_200_OK
        return {"message": f"File {record.original_timestamp} deleted!"}
    except Exception:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": f"Failed to delete file: {record.file_signature}"}
    finally:
        record.delete_instance()


@app.post("/images")
async def post_image(files: List[UploadFile], response: Response):
    signatures = []
    for file in files:
        try:
            with Image.open(file.file) as img:
                exif_data = get_exif_data(img)
                original_timestamp = exif_data.get("DateTime").replace(" ", "-").replace(":", "-")
                signatures.append(original_timestamp)
                try:
                    record = ImageModel.get(ImageModel.original_timestamp == original_timestamp)
                except peewee.DoesNotExist:
                    record = None

                if record is None:
                    file_dir = os.path.join(IMAGES_FOLDER, original_timestamp)

                    create_image_record(original_timestamp, file.filename, file_dir, img)

                    Path(file_dir).mkdir(parents=True, exist_ok=True)

                    img.save(os.path.join(file_dir, file.filename))
                    img.close()

        except Exception as e:
            response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            return {"message": e}

    response.status_code = status.HTTP_201_CREATED
    return {"message": "Files successfully uploaded", "signatures": signatures}


@app.get("/images/{image_signature}")
async def get_image(image_signature: str, response: Response, is_thumbnail: str | None = None):
    record = ImageModel.select().where(ImageModel.original_timestamp == image_signature).get()

    if record is None:
        response.status_code = status.HTTP_404_NOT_FOUND

        return {"message": f"Image with signature: {image_signature} not found!"}

    image_name = record.filename
    image_path = os.path.join(IMAGES_FOLDER, record.original_timestamp, image_name)

    if os.path.exists(image_path) and os.path.isfile(image_path):
        response.status_code = status.HTTP_200_OK

        if is_thumbnail:
            image_path, image_name = create_thumbnail(image_path, record.filename)

        return FileResponse(image_path, filename=image_name, media_type="image/jpeg")


@app.get("/images")
async def get_geo_images(min_lat: str = '',
                         min_lon: str = '',
                         max_lat: str = '',
                         max_lon: str = '',
                         lat_ref: str = '',
                         lon_ref: str = ''):
    min_lat = convert_from_str(min_lat)
    min_lon = convert_from_str(min_lon)
    max_lat = convert_from_str(max_lat)
    max_lon = convert_from_str(max_lon)

    images = ImageModel.select().where(
        ImageModel.lon_ref == lon_ref,
        ImageModel.lat_ref == lat_ref,

        ImageModel.lat_degrees >= min_lat[0],
        ImageModel.lat_minutes >= min_lat[1],
        ImageModel.lat_seconds >= min_lat[2],

        ImageModel.lat_degrees <= max_lat[0],
        ImageModel.lat_minutes <= max_lat[1],
        ImageModel.lat_seconds <= max_lat[2],

        ImageModel.lon_degrees >= min_lon[0],
        ImageModel.lon_minutes >= min_lon[1],
        ImageModel.lon_seconds >= min_lon[2],

        ImageModel.lon_degrees <= max_lon[0],
        ImageModel.lon_minutes <= max_lon[1],
        ImageModel.lon_seconds <= max_lon[2]
    )

    zip_subdir = "images_archive"
    buffer = BytesIO()

    with zipfile.ZipFile(buffer, "w") as zf:
        for image in images:
            zip_path = os.path.join(zip_subdir, image.filename)
            filepath = os.path.join(image.file_dir, image.filename)

            zf.write(filepath, zip_path)
        zf.close()

    return Response(buffer.getvalue(), media_type="application/x-zip-compressed")


def convert_from_str(str_tuple):
    res = []
    for i, num in enumerate(str_tuple.split('-')):
        if i == 2:
           res.append(float(num))
        else:
            res.append(int(num))

    return tuple(res)


def get_exif_data(image: Image):
    return {TAGS.get(k): v for k, v in image.getexif().items()}


def get_gps_data(image: Image):
    return {GPSTAGS.get(k): v for k, v in image.getexif().get_ifd(0x8825).items()}


def create_tables(db_to_init):
    with db_to_init:
        db_to_init.create_tables([ImageModel])


def drop_tables(db_to_uniti):
    with db_to_uniti:
        db_to_uniti.drop_tables([ImageModel])


if __name__ == '__main__':
    db = peewee.SqliteDatabase('images.db')

    create_tables(db)

    uvicorn.run(app, host='0.0.0.0', port=8080)
