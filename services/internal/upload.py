"""Local filesystem upload storage for statement files."""

import hashlib
import logging
import os
import uuid
from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile

from services.domain.exceptions import DomainValidationError

logger = logging.getLogger(__name__)


class UploadService:
    """Store uploaded statement files under MEDIA_ROOT with validation."""

    def validate_upload(self, uploaded_file: UploadedFile) -> None:
        """
        Validate file size and extension.

        Raises DomainValidationError when validation fails.
        """
        max_bytes = settings.STATEMENT_MAX_UPLOAD_BYTES
        if uploaded_file.size > max_bytes:
            raise DomainValidationError(
                f"File exceeds maximum size of {max_bytes // (1024 * 1024)} MB."
            )

        ext = Path(uploaded_file.name).suffix.lower().lstrip(".")
        allowed = settings.STATEMENT_ALLOWED_EXTENSIONS
        if ext not in allowed:
            raise DomainValidationError(
                f"Unsupported file type '.{ext}'. Allowed: {', '.join(sorted(allowed))}."
            )

    def compute_checksum(self, uploaded_file: UploadedFile) -> str:
        """Return SHA-256 hex digest of the uploaded file contents."""
        digest = hashlib.sha256()
        for chunk in uploaded_file.chunks():
            digest.update(chunk)
        uploaded_file.seek(0)
        return digest.hexdigest()

    def save_upload(
        self,
        user_id: int,
        uploaded_file: UploadedFile,
    ) -> tuple[str, str]:
        """
        Persist an uploaded file under MEDIA_ROOT/statements/{user_id}/.

        Returns (relative_path, checksum).
        """
        self.validate_upload(uploaded_file)
        checksum = self.compute_checksum(uploaded_file)

        ext = Path(uploaded_file.name).suffix.lower()
        relative_dir = Path("statements") / str(user_id)
        absolute_dir = settings.MEDIA_ROOT / relative_dir
        absolute_dir.mkdir(parents=True, exist_ok=True)
        if os.name != "nt":
            os.chmod(absolute_dir, 0o750)

        filename = f"{uuid.uuid4().hex}{ext}"
        relative_path = str(relative_dir / filename)
        absolute_path = settings.MEDIA_ROOT / relative_path

        with open(absolute_path, "wb") as dest:
            for chunk in uploaded_file.chunks():
                dest.write(chunk)
        if os.name != "nt":
            os.chmod(absolute_path, 0o640)

        logger.info(
            "Statement file saved user_id=%s path=%s size=%s",
            user_id,
            relative_path,
            uploaded_file.size,
        )
        return relative_path, checksum

    def delete_file(self, relative_path: str) -> None:
        """Remove a stored file if it exists."""
        absolute_path = settings.MEDIA_ROOT / relative_path
        if absolute_path.is_file():
            absolute_path.unlink()
            logger.info("Deleted statement file path=%s", relative_path)

    def absolute_path(self, relative_path: str) -> Path:
        """Resolve a MEDIA_ROOT-relative path to an absolute filesystem path."""
        return settings.MEDIA_ROOT / relative_path
