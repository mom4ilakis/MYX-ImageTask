import json
import os
import unittest
from pathlib import Path

from fastapi import status
from fastapi.testclient import TestClient
import peewee

from main import create_tables, drop_tables, app, IMAGES_FOLDER

IMAGES_FOLDER = 'temp_images'
URL = "http://localhost:8080"


class MyTestCase(unittest.TestCase):
    db = None

    @classmethod
    def setUpClass(cls) -> None:
        db = peewee.SqliteDatabase('test_DB_images.db')
        cls.db = db
        cls.client = TestClient(app)
        cls.image_folder = 'test_images'
        cls.temp_folder = IMAGES_FOLDER
        create_tables(db)

    @classmethod
    def tearDownClass(cls) -> None:
        drop_tables(cls.db)

    def test_image_upload(self):
        filename = '1 (1).JPG'
        with open(Path(self.image_folder).joinpath(filename), 'rb') as img:
            response = self.client.post(URL + "/images", files={"files": ("test_image_01.jpg", img, "image/jpeg")})
            self.assertEqual(status.HTTP_201_CREATED, response.status_code)
            response_content = json.loads(response.content)
            signature = response_content['signatures'][0]

            self.assertTrue(os.path.exists(f'images\\{signature}\\test_image_01.jpg'))


if __name__ == '__main__':
    unittest.main()
