"""MinIO client singleton instance."""

from typing import Any

import boto3

from app.clients.base import ClientManager
from app.core.settings import config


class MinioManager(ClientManager[Any]):
    """Singleton manager for the MinIO (S3) client."""

    _bucket_name: str = "ingestion-bucket"

    async def _create_client(self) -> Any:
        client = boto3.client(
            "s3",
            endpoint_url=config.MINIO_HOST,
            aws_access_key_id=config.MINIO_ACCESS_KEY,
            aws_secret_access_key=config.MINIO_SECRET_KEY,
            region_name="us-east-1",
        )
        self._ensure_bucket(client)
        return client

    def _ensure_bucket(self, client: Any) -> None:
        try:
            client.head_bucket(Bucket=self._bucket_name)
        except client.exceptions.NoSuchBucket:
            client.create_bucket(Bucket=self._bucket_name)

    def upload_file(self, file_data: Any, object_name: str) -> str:
        self.client.put_object(
            Bucket=self._bucket_name,
            Key=object_name,
            Body=file_data,
            ContentType="application/octet-stream",
        )
        return object_name

    def download_file(self, object_name: str, file_path: str) -> None:
        self.client.download_file(
            Bucket=self._bucket_name, Key=object_name, Filename=file_path
        )

    def delete_file(self, object_name: str) -> None:
        self.client.delete_object(Bucket=self._bucket_name, Key=object_name)


_minio_singleton = MinioManager()


def get_minio_handler() -> MinioManager:
    return _minio_singleton
