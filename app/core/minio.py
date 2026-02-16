import io

import boto3

from app.core.settings import config


class MinioHandler:
    def __init__(self):
        self.client = boto3.client(
            "s3",
            endpoint_url=config.MINIO_HOST,
            aws_access_key_id=config.MINIO_ACCESS_KEY,
            aws_secret_access_key=config.MINIO_SECRET_KEY,
            region_name="us-east-1",
        )
        self.bucket_name = "ingestion-bucket"
        self._ensure_bucket()

    def get_file_stream(self, object_name: str) -> io.BytesIO:
        """
        Downloads file into an in-memory byte stream.
        WARNING: High RAM usage for large files.
        """
        try:
            response = self.client.get_object(Bucket=self.bucket_name, Key=object_name)
            # Read the entire response into memory
            file_data = io.BytesIO(response["Body"].read())
            # Reset cursor to the beginning so it can be read again
            file_data.seek(0)
            return file_data
        except Exception as e:
            raise Exception(f"Failed to download {object_name}: {str(e)}")

    def _ensure_bucket(self):
        """Make sure the bucket exists on startup."""
        try:
            self.client.head_bucket(Bucket=self.bucket_name)
        except self.client.exceptions.NoSuchBucket:
            self.client.create_bucket(Bucket=self.bucket_name)

    def upload_file(self, file_data, size: int, object_name: str):
        """Uploads a stream to MinIO."""
        self.client.put_object(
            Bucket=self.bucket_name,
            Key=object_name,
            Body=file_data,
            ContentType="application/octet-stream",
        )
        return object_name

    def download_file(self, object_name: str, file_path: str):
        """Downloads file from MinIO to local disk (for processing)."""
        self.client.download_file(
            Bucket=self.bucket_name, Key=object_name, Filename=file_path
        )

    def delete_file(self, object_name: str):
        """Cleanup after processing."""
        self.client.delete_object(Bucket=self.bucket_name, Key=object_name)


# Create a singleton instance
minio_handler = MinioHandler()
