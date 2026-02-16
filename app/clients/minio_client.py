"""MinIO client singleton instance."""

import io
from typing import Optional

import boto3

from app.core.settings import config


class MinioManager:
    """Singleton class for MinIO client to ensure single instance across the application."""

    _instance: Optional["MinioManager"] = None
    _client = None
    _initialized: bool = False
    _bucket_name: str = "ingestion-bucket"

    def __new__(cls) -> "MinioManager":
        """Ensure only one instance is created."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def initialize(self) -> None:
        """Initialize the MinIO client. Must be called before accessing the client."""
        if not self.__class__._initialized:
            self._client = self._create_client()
            self._ensure_bucket()
            self.__class__._initialized = True

    def _create_client(self):
        """Create and configure the MinIO (S3) client."""
        return boto3.client(
            "s3",
            endpoint_url=config.MINIO_HOST,
            aws_access_key_id=config.MINIO_ACCESS_KEY,
            aws_secret_access_key=config.MINIO_SECRET_KEY,
            region_name="us-east-1",
        )

    def _ensure_bucket(self):
        """Make sure the bucket exists on startup."""
        try:
            self.client.head_bucket(Bucket=self._bucket_name)
        except self.client.exceptions.NoSuchBucket:
            self.client.create_bucket(Bucket=self._bucket_name)

    @property
    def client(self):
        """Get the MinIO client instance."""
        if self._client is None:
            raise RuntimeError(
                "MinIO client not initialized. Call 'minio_manager.initialize()' first."
            )
        return self._client

    def get_file_stream(self, object_name: str) -> io.BytesIO:
        """
        Downloads file into an in-memory byte stream.
        WARNING: High RAM usage for large files.
        TODO: Come back to this later and just write to disk
        """
        try:
            response = self.client.get_object(Bucket=self._bucket_name, Key=object_name)
            file_data = io.BytesIO(response["Body"].read())
            file_data.seek(0)
            return file_data
        except Exception as e:
            raise Exception(f"Failed to download {object_name}: {str(e)}")

    def upload_file(self, file_data, size: int, object_name: str):
        """Uploads a stream to MinIO."""
        self.client.put_object(
            Bucket=self._bucket_name,
            Key=object_name,
            Body=file_data,
            ContentType="application/octet-stream",
        )
        return object_name

    def download_file(self, object_name: str, file_path: str):
        """Downloads file from MinIO to local disk (for processing)."""
        self.client.download_file(
            Bucket=self._bucket_name, Key=object_name, Filename=file_path
        )

    def delete_file(self, object_name: str):
        """Cleanup after processing."""
        self.client.delete_object(Bucket=self._bucket_name, Key=object_name)

    def close(self) -> None:
        """Clean up the MinIO client."""
        if self._client:
            self.__class__._initialized = False
            self.__class__._instance = None
            self._client = None


# Create a singleton instance
_minio_singleton = MinioManager()


def get_minio_handler() -> "MinioManager":
    """
    Get the singleton MinIO handler instance.

    Returns:
        MinioManager: The singleton MinIO handler instance.
    """
    return _minio_singleton
