import peewee


class BaseModel(peewee.Model):
    class Meta:
        database = peewee.SqliteDatabase('images.db')


class Image(BaseModel):
    original_timestamp = peewee.CharField(unique=True, index=True)
    filename = peewee.CharField()
    file_dir = peewee.CharField()
    lat_degrees = peewee.IntegerField(index=True)
    lat_minutes = peewee.IntegerField(index=True)
    lat_seconds = peewee.FloatField(index=True)
    lat_ref = peewee.CharField(index=True)
    lon_degrees = peewee.IntegerField(index=True)
    lon_minutes = peewee.IntegerField(index=True)
    lon_seconds = peewee.FloatField(index=True)
    lon_ref = peewee.CharField(index=True)