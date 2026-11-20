"""Default Django file storage: Arvan Object Storage for user uploads."""
from storages.backends.s3boto3 import S3Boto3Storage


class ArvanMediaStorage(S3Boto3Storage):
    """Public objects in the cafeclub-media Arvan bucket."""

    default_acl = "public-read"
    file_overwrite = False
    querystring_auth = False
    object_parameters = {"CacheControl": "public, max-age=31536000, immutable"}
