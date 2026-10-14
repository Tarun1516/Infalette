"""Custom SQLAlchemy types."""

from __future__ import annotations

import uuid
from typing import Any, Optional

from cryptography.fernet import Fernet
from sqlalchemy.types import TypeDecorator, String, TypeDecorator


class UUIDType(TypeDecorator):
    """UUID type that stores as string in DB and returns UUID in Python."""

    impl = String
    cache_ok = True

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    def process_bind_param(self, value: Any, dialect: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return str(value)
        return str(uuid.UUID(value))

    def process_result_value(self, value: Any, dialect: Any) -> Optional[uuid.UUID]:
        if value is None:
            return None
        return uuid.UUID(value)


class EncryptedString(TypeDecorator):
    """Encrypted string type using Fernet symmetric encryption.

    Requires the SECRET_KEY environment variable to be set.
    The key is derived from the secret key using a simple transformation.
    """

    impl = String
    cache_ok = True

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    @staticmethod
    def _get_fernet() -> Fernet:
        """Get Fernet instance from settings."""
        from infalette_config import get_settings

        settings = get_settings()
        key = settings.auth.secret_key.get_secret_value().encode()
        # Derive a valid Fernet key from the secret
        import base64
        import hashlib

        derived = hashlib.sha256(key).digest()
        fernet_key = base64.urlsafe_b64encode(derived)
        return Fernet(fernet_key)

    def process_bind_param(self, value: Any, dialect: Any) -> Optional[str]:
        if value is None:
            return None
        fernet = self._get_fernet()
        return fernet.encrypt(value.encode()).decode()

    def process_result_value(self, value: Any, dialect: Any) -> Optional[str]:
        if value is None:
            return None
        fernet = self._get_fernet()
        return fernet.decrypt(value.encode()).decode()
