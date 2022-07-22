import unittest
from pathlib import Path

from fastapi.testclient import TestClient
import peewee

from main import create_tables, app ,IMAGES_FOLDER

IMAGES_FOLDER = 'temp_images'
URL = "localhost:8080"


class MyTestCase(unittest.TestCase):
    def setUpClass(cls) -> None:
        cls.db = peewee.SqliteDatabase('test_images.db')
        cls.client = TestClient(app)
        cls.image_folder = 'test_images'
        cls.temp_folder = IMAGES_FOLDER
        Path(cls.temp_folder).mkdir(parents=True, exist_ok=True)
        create_tables(cls.db)

    def test_image_upload(self):
        filename = '1 (1).JPG'
        with open(Path.joinpath(self.image_folder, filename)) as img:
            response = self.client.post(URL, files={"file": ("test_image_01", img, "image/jpeg")})

    def test_something(self):
        self.assertEqual(True, False)  # add assertion here


if __name__ == '__main__':
    unittest.main()
