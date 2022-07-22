import json
import os
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import status
from fastapi.testclient import TestClient
import peewee

from image_model import Image
from main import create_tables, drop_tables, app, IMAGES_FOLDER

IMAGES_FOLDER = 'temp_images'
URL = "http://localhost:8080"


class MyTestCase(unittest.TestCase):
    db = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.db = peewee.SqliteDatabase('images.db')
        cls.client = TestClient(app)
        cls.image_folder = 'test_images'
        cls.temp_folder = IMAGES_FOLDER
        create_tables(cls.db)

    @classmethod
    def tearDownClass(cls) -> None:
        drop_tables(cls.db)

    def setUp(self) -> None:
        shutil.rmtree('images', ignore_errors=True)
        Image.delete().execute()

    @patch("PIL.Image.Image.save")
    def test_image_upload(self, mocked_save):
        filename = '1 (1).JPG'
        with open(Path(self.image_folder).joinpath(filename), 'rb') as img:
            response = self.client.post(URL + "/images", files={"files": ("test_image_01.jpg", img, "image/jpeg")})
            self.assertEqual(status.HTTP_201_CREATED, response.status_code)
            response_content = json.loads(response.content)
            signature = response_content['signatures'][0]

            mocked_save.assert_called_with(f'images\\{signature}\\test_image_01.jpg')

    def test_get_image(self):
        filename = '1 (1).JPG'

        with open(Path(self.image_folder).joinpath(filename), 'rb') as img:
            response = self.client.post(URL + "/images", files={"files": ("test_image_01.jpg", img, "image/jpeg")})
            self.assertEqual(status.HTTP_201_CREATED, response.status_code)
            response_content = json.loads(response.content)
            signature = response_content['signatures'][0]
            response = self.client.get(URL + f"/images/{signature}")

            self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_image_thumbnail(self):
        filename = '1 (1).JPG'

        with open(Path(self.image_folder).joinpath(filename), 'rb') as img:
            response = self.client.post(URL + "/images", files={"files": ("test_image_01.jpg", img, "image/jpeg")})
            self.assertEqual(status.HTTP_201_CREATED, response.status_code)
            response_content = json.loads(response.content)
            signature = response_content['signatures'][0]
            response = self.client.get(URL + f"/images/{signature}?is_thumbnail=True")

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(os.path.exists(f"images\\{signature}\\test_image_01_thumb.jpg"))

    def test_delete_image(self):
        filename = '1 (1).JPG'

        with open(Path(self.image_folder).joinpath(filename), 'rb') as img:
            response = self.client.post(URL + "/images", files={"files": ("test_image_01.jpg", img, "image/jpeg")})
            self.assertEqual(status.HTTP_201_CREATED, response.status_code)
            response_content = json.loads(response.content)
            signature = response_content['signatures'][0]

            response = self.client.delete(f"/images/{signature}")

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertFalse(os.path.exists(f"images\\{signature}"))

    def test_get_geo_images(self):
        filenames = ['1 (1).jpg', '2 (1).jpg']

        files = [open(Path(self.image_folder).joinpath(fname), 'rb') for fname in filenames]
        files_to_upload = [(fname, f, "image/jpeg") for fname, f in zip(filenames, files)]

        self.client.post(URL + "/images", files=[("files", ftuple) for ftuple in files_to_upload])

        [file.close() for file in files]

        response = self.client.get(URL + "/images?max_lat=53-52-35.2455&min_lat=53-52-35.233&max_lon=1-54-16.85&min_lon=1-54-16.844&lat_ref=N&lon_ref=W")

        self.assertEqual(response.status_code, status.HTTP_200_OK)


if __name__ == '__main__':
    unittest.main()
