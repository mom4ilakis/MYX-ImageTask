import unittest
from pathlib import Path

from fastapi.testclient import TestClient
import peewee

from main import create_tables, app ,IMAGES_FOLDER

IMAGES_FOLDER = 'temp_images'
URL = "localhost:8080"


class MyTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        db = peewee.SqliteDatabase('test_images.db')
        cls.db = db
        cls.client = TestClient(app)
        cls.image_folder = 'test_images'
        cls.temp_folder = IMAGES_FOLDER
        create_tables(db)

    def test_image_upload(self):
        filename = '1 (1).JPG'
        with open(Path(self.image_folder).joinpath(filename)) as img:
            response = self.client.post(URL, files={"file": ("test_image_01", img, "image/jpeg")})

    def test_something(self):
        self.assertEqual(True, False)  # add assertion here


if __name__ == '__main__':
    unittest.main()
