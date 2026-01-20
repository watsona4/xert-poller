"""OAuth2 token management for Xert API."""

import base64
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

import aiohttp

logger = logging.getLogger(__name__)

TOKEN_URL = "https://www.xertonline.com/oauth/token"
# Xert uses public client credentials
CLIENT_ID = "xert_public"
CLIENT_SECRET = "xert_public"


def _get_basic_auth_header() -> str:
    """Get Basic Auth header for Xert API."""
    credentials = f"{CLIENT_ID}:{CLIENT_SECRET}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"


@dataclass
class TokenData:
    """OAuth2 token data."""

    access_token: str = ""
    refresh_token: str = ""
    access_expiry: float = 0.0

    def is_access_valid(self, margin: int = 300) -> bool:
        """Check if access token is still valid."""
        return self.access_token and time.time() < (self.access_expiry - margin)


@dataclass
class AuthManager:
    """Manages Xert OAuth2 authentication."""

    username: str
    password: str
    token_file: str
    refresh_margin: int = 300
    _tokens: TokenData = field(default_factory=TokenData)
    _session: aiohttp.ClientSession | None = None

    async def __aenter__(self):
        """Async context manager entry."""
        self._session = aiohttp.ClientSession()
        self._load_tokens()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._session:
            await self._session.close()
            self._session = None

    def _load_tokens(self) -> None:
        """Load tokens from file if exists."""
        path = Path(self.token_file)
        if path.exists():
            try:
                data = json.loads(path.read_text())
                self._tokens = TokenData(
                    access_token=data.get("access_token", ""),
                    refresh_token=data.get("refresh_token", ""),
                    access_expiry=data.get("access_expiry", 0.0),
                )
                logger.info("Loaded tokens from %s", self.token_file)
            except Exception as e:
                logger.warning("Failed to load tokens: %s", e)

    def _save_tokens(self) -> None:
        """Save tokens to file."""
        path = Path(self.token_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "access_token": self._tokens.access_token,
                    "refresh_token": self._tokens.refresh_token,
                    "access_expiry": self._tokens.access_expiry,
                }
            )
        )
        logger.debug("Saved tokens to %s", self.token_file)

    def _parse_token_response(self, data: dict) -> None:
        """Parse and store token response."""
        now = time.time()
        expires_in = data.get("expires_in", 0)
        created_at = data.get("created_at", now)

        self._tokens = TokenData(
            access_token=data.get("access_token", ""),
            refresh_token=data.get("refresh_token", self._tokens.refresh_token),
            access_expiry=created_at + expires_in - 5,
        )
        self._save_tokens()

    async def _password_grant(self) -> bool:
        """Authenticate with username/password."""
        if not self._session:
            return False

        logger.info("Authenticating with password grant")
        try:
            async with self._session.post(
                TOKEN_URL,
                data={
                    "grant_type": "password",
                    "username": self.username,
                    "password": self.password,
                },
                headers={
                    "Authorization": _get_basic_auth_header(),
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self._parse_token_response(data)
                    logger.info("Password grant successful")
                    return True
                else:
                    text = await resp.text()
                    logger.error("Password grant failed: %d - %s", resp.status, text)
                    return False
        except Exception as e:
            logger.error("Password grant error: %s", e)
            return False

    async def _refresh_grant(self) -> bool:
        """Refresh access token using refresh token."""
        if not self._session or not self._tokens.refresh_token:
            return False

        logger.info("Refreshing access token")
        try:
            async with self._session.post(
                TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self._tokens.refresh_token,
                },
                headers={
                    "Authorization": _get_basic_auth_header(),
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self._parse_token_response(data)
                    logger.info("Token refresh successful")
                    return True
                else:
                    text = await resp.text()
                    logger.warning("Token refresh failed: %d - %s", resp.status, text)
                    return False
        except Exception as e:
            logger.warning("Token refresh error: %s", e)
            return False

    async def ensure_valid_token(self) -> str | None:
        """Ensure we have a valid access token, refreshing or re-authenticating as needed.

        Returns the access token if successful, None otherwise.
        """
        # Check if current access token is valid
        if self._tokens.is_access_valid(self.refresh_margin):
            return self._tokens.access_token

        # Try refresh if we have a refresh token
        if self._tokens.refresh_token:
            if await self._refresh_grant():
                return self._tokens.access_token

        # Fall back to password grant
        if await self._password_grant():
            return self._tokens.access_token

        return None

    @property
    def access_token(self) -> str:
        """Get current access token."""
        return self._tokens.access_token
