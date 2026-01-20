"""Xert API client."""

import logging
import time
from dataclasses import dataclass
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)

BASE_URL = "https://www.xertonline.com/oauth"


@dataclass
class XertAPI:
    """Client for Xert API."""

    _session: aiohttp.ClientSession | None = None

    async def __aenter__(self):
        """Async context manager entry."""
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._session:
            await self._session.close()
            self._session = None

    async def _get(self, endpoint: str, token: str, params: dict | None = None) -> dict | list | None:
        """Make authenticated GET request."""
        if not self._session:
            logger.error("API session not initialized")
            return None

        url = f"{BASE_URL}{endpoint}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "XertPoller/1.0",
            "Cache-Control": "no-cache",
        }

        try:
            async with self._session.get(
                url,
                headers=headers,
                params=params,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                elif resp.status == 401:
                    logger.warning("Unauthorized - token may be expired")
                    return None
                else:
                    text = await resp.text()
                    logger.warning("API request failed: %d - %s", resp.status, text[:200])
                    return None
        except Exception as e:
            logger.error("API request error: %s", e)
            return None

    async def get_training_info(self, token: str) -> dict[str, Any] | None:
        """Get training info (fitness signature, status, training load).

        Returns:
            Training info dict with keys: success, signature, status, tl, targetXSS, etc.
        """
        logger.debug("Fetching training info")
        result = await self._get("/training_info", token)
        if isinstance(result, dict):
            if result.get("success"):
                logger.info("Fetched training info successfully")
            else:
                logger.warning("Training info response indicates failure")
            return result
        return None

    async def get_activities(
        self,
        token: str,
        lookback_days: int = 90,
    ) -> dict[str, Any] | None:
        """Get list of activities within lookback period.

        Args:
            token: OAuth access token
            lookback_days: Number of days to look back

        Returns:
            Dict with 'success' and 'activities' keys
        """
        now = int(time.time())
        from_epoch = now - (lookback_days * 24 * 3600)

        logger.debug("Fetching activities (from=%d, to=%d)", from_epoch, now)
        result = await self._get(
            "/activity",
            token,
            params={"from": from_epoch, "to": now},
        )
        if isinstance(result, dict):
            activities = result.get("activities", [])
            logger.info("Fetched %d activities", len(activities) if activities else 0)
            return result
        return None

    async def get_activity_detail(self, token: str, activity_path: str) -> dict[str, Any] | None:
        """Get detailed activity information.

        Args:
            token: OAuth access token
            activity_path: Activity path/ID from the activity list

        Returns:
            Activity details or None on error
        """
        logger.debug("Fetching activity details: %s", activity_path)
        result = await self._get(f"/activity/{activity_path}", token)
        if isinstance(result, dict):
            return result
        return None
