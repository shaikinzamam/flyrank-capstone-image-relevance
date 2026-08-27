import hmac
import re
import secrets
from datetime import UTC, datetime
from hashlib import sha256

from app.models.workspace import ApiCredential, Workspace
from app.repositories.auth import AuthRepository


class InvalidApiCredentialError(Exception):
    pass


LOCAL_DEMO_CREDENTIAL_NAME = "local demo credential"
_DEMO_API_KEY_PATTERN = re.compile(r"^frk_[A-Za-z0-9_-]{32,}$")
_PLACEHOLDER_MARKERS = (
    "your_current",
    "replace-me",
    "replace_me",
    "changeme",
    "change_me",
    "placeholder",
    "example",
)


def validate_demo_api_key(api_key: str | None) -> str:
    """Validate the plaintext key used only to provision the local demo."""
    value = (api_key or "").strip()
    lowered = value.lower()
    if not value:
        raise ValueError("DEMO_API_KEY is required for the local demo")
    if any(marker in lowered for marker in _PLACEHOLDER_MARKERS):
        raise ValueError("DEMO_API_KEY must not be a placeholder value")
    if not _DEMO_API_KEY_PATTERN.fullmatch(value):
        raise ValueError(
            "DEMO_API_KEY must start with 'frk_' and contain at least "
            "32 URL-safe key characters"
        )
    return value


def hash_api_key(api_key: str) -> str:
    return sha256(api_key.encode("utf-8")).hexdigest()


def generate_api_key() -> str:
    return f"frk_{secrets.token_urlsafe(32)}"


class AuthenticationService:
    """Authenticate high-entropy bearer keys stored only as SHA-256 digests."""

    def __init__(self, repository: AuthRepository) -> None:
        self._repository = repository

    def authenticate(self, api_key: str) -> Workspace:
        supplied_hash = hash_api_key(api_key)
        credential = self._repository.get_active_credential(supplied_hash)
        if credential is None or not hmac.compare_digest(
            credential.key_hash, supplied_hash
        ):
            raise InvalidApiCredentialError("Invalid API credential")
        workspace = self._repository.get_workspace(credential.workspace_id)
        if workspace is None:
            raise InvalidApiCredentialError("Invalid API credential")
        return workspace


class CredentialService:
    def __init__(self, repository: AuthRepository) -> None:
        self._repository = repository

    def create(
        self, workspace: Workspace, *, name: str, api_key: str | None = None
    ) -> tuple[ApiCredential, str]:
        plaintext = api_key or generate_api_key()
        credential = ApiCredential(
            workspace_id=workspace.id,
            key_hash=hash_api_key(plaintext),
            key_prefix=plaintext[:12],
            name=name,
        )
        self._repository.add(credential)
        self._repository.commit()
        self._repository.refresh(credential)
        return credential, plaintext

    def reconcile_local_demo(
        self, workspace: Workspace, *, api_key: str
    ) -> ApiCredential:
        """Make one supplied key the sole active local-demo credential."""
        key_hash = hash_api_key(api_key)
        matching = self._repository.get_credential(key_hash)
        if matching is not None and matching.workspace_id != workspace.id:
            raise RuntimeError("DEMO_API_KEY already belongs to another workspace")

        now = datetime.now(UTC)
        for credential in self._repository.get_workspace_credentials_by_name(
            workspace.id, LOCAL_DEMO_CREDENTIAL_NAME
        ):
            if credential is not matching and (
                credential.active or credential.revoked_at is None
            ):
                credential.active = False
                credential.revoked_at = now

        if matching is None:
            matching = ApiCredential(
                workspace_id=workspace.id,
                key_hash=key_hash,
                key_prefix=api_key[:12],
                name=LOCAL_DEMO_CREDENTIAL_NAME,
            )
            self._repository.add(matching)
        else:
            matching.key_prefix = api_key[:12]
            matching.name = LOCAL_DEMO_CREDENTIAL_NAME
            matching.active = True
            matching.revoked_at = None

        self._repository.commit()
        self._repository.refresh(matching)
        return matching
