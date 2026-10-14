"""S3 media client — upload, signed URLs, delete, list.

Uses boto3. Credentials are resolved via standard AWS chain
(env vars, IAM role, etc.). Bucket and region come from settings.
"""

from __future__ import annotations

import logging
from typing import Any

from infalette_config import get_settings

logger = logging.getLogger(__name__)


class S3Client:
    """Thin wrapper around boto3 S3 for infalette media."""

    def __init__(
        self,
        bucket: str | None = None,
        region: str | None = None,
        endpoint_url: str | None = None,
    ) -> None:
        settings = get_settings()
        # settings.s3 is introduced in settings.py update; fallback to email.s3 for compat
        s3_settings = getattr(settings, "s3", None)
        if s3_settings is not None:
            default_bucket = s3_settings.bucket
            default_region = s3_settings.region
            default_endpoint = s3_settings.endpoint
        else:
            # legacy fallback
            default_bucket = getattr(settings.email, "s3_bucket", None)
            default_region = getattr(settings.email, "aws_region", "ap-south-1")
            default_endpoint = getattr(settings.email, "s3_endpoint", None)

        self.bucket = bucket or default_bucket
        self.region = region or default_region or "ap-south-1"
        self.endpoint_url = endpoint_url or default_endpoint
        self._client = None  # lazy

    def _get_client(self):
        """Lazy boto3 client creation."""
        if self._client is not None:
            return self._client
        try:
            import boto3  # type: ignore
        except ImportError as e:
            raise RuntimeError("boto3 is required for S3Client. Add it to dependencies.") from e

        kwargs: dict[str, Any] = {"region_name": self.region}
        if self.endpoint_url:
            kwargs["endpoint_url"] = self.endpoint_url
        self._client = boto3.client("s3", **kwargs)
        return self._client

    # ------------------------------------------------------------------ #
    # Core operations
    # ------------------------------------------------------------------ #

    def upload_file(
        self,
        file_obj: bytes | Any,
        key: str,
        content_type: str | None = None,
        extra_args: dict[str, Any] | None = None,
    ) -> dict:
        """Upload a file to S3.

        Args:
            file_obj: bytes or file-like object.
            key: S3 key (path) to store the object.
            content_type: MIME type.
            extra_args: additional boto3 ExtraArgs.

        Returns:
            dict with bucket, key, and etag.
        """
        if not self.bucket:
            raise ValueError("S3 bucket is not configured. Set S3_BUCKET env var.")

        client = self._get_client()
        args: dict[str, Any] = dict(extra_args or {})
        if content_type:
            args["ContentType"] = content_type

        # Normalize file_obj to bytes if needed
        if isinstance(file_obj, (bytes, bytearray)):
            import io

            file_obj = io.BytesIO(file_obj)

        # Use upload_fileobj for streaming
        client.upload_fileobj(file_obj, self.bucket, key, ExtraArgs=args or None)

        logger.info("s3_upload bucket=%s key=%s", self.bucket, key)
        return {"bucket": self.bucket, "key": key, "region": self.region}

    def get_signed_url(
        self,
        key: str,
        expires_in: int = 3600,
        method: str = "get_object",
    ) -> str:
        """Generate a presigned URL for an S3 object.

        Args:
            key: S3 key.
            expires_in: seconds until expiry (default 3600).
            method: boto3 operation (get_object or put_object).

        Returns:
            Presigned URL string.
        """
        if not self.bucket:
            raise ValueError("S3 bucket is not configured.")
        client = self._get_client()
        url = client.generate_presigned_url(
            ClientMethod=method,
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires_in,
        )
        logger.debug("s3_presigned bucket=%s key=%s expires=%s", self.bucket, key, expires_in)
        return url

    def get_presigned_post(
        self,
        key: str,
        expires_in: int = 3600,
        content_type: str | None = None,
        max_size: int | None = None,
    ) -> dict:
        """Generate a presigned POST for direct browser upload.

        Returns dict with url and fields for multipart form.
        """
        if not self.bucket:
            raise ValueError("S3 bucket is not configured.")
        client = self._get_client()
        conditions = []
        fields: dict[str, str] = {}
        if content_type:
            fields["Content-Type"] = content_type
            conditions.append(["starts-with", "$Content-Type", content_type.split("/")[0]])
        if max_size:
            conditions.append(["content-length-range", 1, max_size])
        resp = client.generate_presigned_post(
            Bucket=self.bucket,
            Key=key,
            Fields=fields or None,
            Conditions=conditions or None,
            ExpiresIn=expires_in,
        )
        return resp

    def delete_file(self, key: str) -> dict:
        """Delete an object from S3."""
        if not self.bucket:
            raise ValueError("S3 bucket is not configured.")
        client = self._get_client()
        client.delete_object(Bucket=self.bucket, Key=key)
        logger.info("s3_delete bucket=%s key=%s", self.bucket, key)
        return {"bucket": self.bucket, "key": key, "deleted": True}

    def list_files(
        self,
        prefix: str = "",
        max_keys: int = 100,
        continuation_token: str | None = None,
    ) -> dict:
        """List objects under a prefix.

        Returns:
            dict with files, count, and next_token if truncated.
        """
        if not self.bucket:
            raise ValueError("S3 bucket is not configured.")
        client = self._get_client()
        kwargs: dict[str, Any] = {"Bucket": self.bucket, "Prefix": prefix, "MaxKeys": max_keys}
        if continuation_token:
            kwargs["ContinuationToken"] = continuation_token
        resp = client.list_objects_v2(**kwargs)
        contents = resp.get("Contents", []) or []
        files = [
            {
                "key": obj["Key"],
                "size": obj["Size"],
                "last_modified": obj["LastModified"].isoformat() if hasattr(obj["LastModified"], "isoformat") else str(obj["LastModified"]),
                "etag": obj.get("ETag"),
            }
            for obj in contents
        ]
        return {
            "bucket": self.bucket,
            "prefix": prefix,
            "count": len(files),
            "files": files,
            "is_truncated": resp.get("IsTruncated", False),
            "next_token": resp.get("NextContinuationToken"),
        }

    # ------------------------------------------------------------------ #
    # Convenience
    # ------------------------------------------------------------------ #

    def head_object(self, key: str) -> dict:
        """Check if object exists and return metadata."""
        if not self.bucket:
            raise ValueError("S3 bucket is not configured.")
        client = self._get_client()
        resp = client.head_object(Bucket=self.bucket, Key=key)
        return {
            "key": key,
            "content_type": resp.get("ContentType"),
            "content_length": resp.get("ContentLength"),
            "last_modified": resp.get("LastModified"),
            "etag": resp.get("ETag"),
        }
