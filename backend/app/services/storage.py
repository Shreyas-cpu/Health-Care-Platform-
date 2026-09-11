import boto3
from backend.app.core.config import settings
from botocore.client import Config


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION,
        config=Config(signature_version="s3v4"),
    )


class StorageService:
    def generate_presigned_upload_url(
        self,
        bucket_name: str,
        s3_key: str,
        content_type: str = "application/pdf",
        expires_in: int = 3600,
    ) -> str:
        client = get_s3_client()
        url = client.generate_presigned_url(
            ClientMethod="put_object",
            Params={"Bucket": bucket_name, "Key": s3_key, "ContentType": content_type},
            ExpiresIn=expires_in,
        )
        return url

    def generate_presigned_download_url(
        self, bucket_name: str, s3_key: str, expires_in: int = 3600
    ) -> str:
        client = get_s3_client()
        url = client.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": bucket_name, "Key": s3_key},
            ExpiresIn=expires_in,
        )
        return url

    def upload_bytes(
        self,
        bucket_name: str,
        s3_key: str,
        data: bytes,
        content_type: str = "application/pdf",
    ) -> str:
        """Upload raw bytes to S3/MinIO and return the object key."""
        client = get_s3_client()
        # Ensure bucket exists in local/dev MinIO environments.
        try:
            client.head_bucket(Bucket=bucket_name)
        except Exception:
            try:
                client.create_bucket(Bucket=bucket_name)
            except Exception:
                pass
        client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=data,
            ContentType=content_type,
        )
        return s3_key


storage_service = StorageService()
