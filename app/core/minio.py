import io

from minio import Minio

from app.core.settings import config


class MinioHandler:
    def __init__(self):
        self.client = Minio(
            endpoint=config.MINIO_HOST,
            access_key=config.MINIO_ACCESS_KEY,
            secret_key=config.MINIO_SECRET_KEY,
            secure=False,
        )
        self.bucket_name = "ingestion-bucket"
        self._ensure_bucket()

    def get_file_stream(self, object_name: str) -> io.BytesIO:
        """
        Downloads file into an in-memory byte stream.
        WARNING: High RAM usage for large files.
        """
        response = None
        try:
            # get_object returns a stream response
            response = self.client.get_object(self.bucket_name, object_name)

            # Read the entire response into memory
            file_data = io.BytesIO(response.read())

            # Reset cursor to the beginning so it can be read again
            file_data.seek(0)
            return file_data
        finally:
            # Always close the MinIO network response connection
            if response:
                response.close()
                response.release_conn()

    def _ensure_bucket(self):
        """Make sure the bucket exists on startup."""
        if not self.client.bucket_exists(self.bucket_name):
            self.client.make_bucket(self.bucket_name)

    def upload_file(self, file_data, size: int, object_name: str):
        """Uploads a stream to MinIO."""
        self.client.put_object(
            bucket_name=self.bucket_name,
            object_name=object_name,
            data=file_data,
            length=size,
            content_type="application/octet-stream",
        )
        return object_name

    def download_file(self, object_name: str, file_path: str):
        """Downloads file from MinIO to local disk (for processing)."""
        self.client.fget_object(
            bucket_name=self.bucket_name, object_name=object_name, file_path=file_path
        )

    def delete_file(self, object_name: str):
        """Cleanup after processing."""
        self.client.remove_object(self.bucket_name, object_name)


# Create a singleton instance
minio_handler = MinioHandler()
