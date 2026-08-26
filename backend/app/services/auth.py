import hmac
import secrets
from hashlib import sha256

from app.models.workspace import ApiCredential, Workspace
from app.repositories.auth import AuthRepository


class InvalidApiCredentialError(Exception):
    pass


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
