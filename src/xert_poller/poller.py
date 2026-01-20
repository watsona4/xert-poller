"""Main polling orchestration with change detection."""

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass, field
from typing import Any

from .api import XertAPI
from .auth import AuthManager
from .config import Settings
from .webhook import WebhookClient

logger = logging.getLogger(__name__)


def _compute_hash(data: Any) -> str:
    """Compute hash of data for change detection."""
    serialized = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()[:16]


@dataclass
class PollerState:
    """Tracks poller state for change detection."""

    training_info_hash: str = ""
    activities_hash: str = ""
    last_training_info: dict[str, Any] = field(default_factory=dict)
    last_activities: dict[str, Any] = field(default_factory=dict)


class Poller:
    """Main polling orchestrator."""

    def __init__(
        self,
        settings: Settings,
        auth: AuthManager,
        api: XertAPI,
        webhook: WebhookClient,
    ):
        self.settings = settings
        self.auth = auth
        self.api = api
        self.webhook = webhook
        self.state = PollerState()
        self._running = False
        self._tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        """Start the poller."""
        logger.info("Starting Xert poller")
        self._running = True

        # Ensure we have a valid token
        token = await self.auth.ensure_valid_token()
        if not token:
            logger.error("Failed to authenticate - check credentials")
            return

        # Initial fetch and send (always send on startup)
        await self._poll_training_info(force_send=True)
        await self._poll_activities(force_send=True)

        # Start polling tasks
        self._tasks = [
            asyncio.create_task(self._training_info_loop()),
            asyncio.create_task(self._activities_loop()),
        ]

        # Wait for all tasks
        try:
            await asyncio.gather(*self._tasks)
        except asyncio.CancelledError:
            logger.info("Poller tasks cancelled")

    async def stop(self) -> None:
        """Stop the poller."""
        logger.info("Stopping Xert poller")
        self._running = False
        for task in self._tasks:
            task.cancel()

    async def _training_info_loop(self) -> None:
        """Poll training info at configured interval."""
        while self._running:
            await asyncio.sleep(self.settings.training_info_interval)
            await self._poll_training_info()

    async def _activities_loop(self) -> None:
        """Poll activities at configured interval."""
        while self._running:
            await asyncio.sleep(self.settings.activities_interval)
            await self._poll_activities()

    async def _poll_training_info(self, force_send: bool = False) -> None:
        """Poll and process training info data."""
        token = await self.auth.ensure_valid_token()
        if not token:
            logger.warning("No valid token for training info poll")
            return

        data = await self.api.get_training_info(token)
        if data is None:
            return

        # Check for data change
        data_hash = _compute_hash(data)
        if force_send or data_hash != self.state.training_info_hash:
            logger.info("Training info data changed, sending webhook")
            self.state.training_info_hash = data_hash
            self.state.last_training_info = data
            await self.webhook.send_training_info(data)
        else:
            logger.debug("Training info data unchanged")

    async def _poll_activities(self, force_send: bool = False) -> None:
        """Poll and process activities data with full details."""
        token = await self.auth.ensure_valid_token()
        if not token:
            logger.warning("No valid token for activities poll")
            return

        data = await self.api.get_activities(token, lookback_days=self.settings.lookback_days)
        if data is None:
            return

        # Fetch details for each activity (up to 50)
        activities = data.get("activities", [])
        if activities:
            # Sort by start_date descending and take top 50
            sorted_activities = sorted(
                [a for a in activities if a.get("start_date", {}).get("date")],
                key=lambda x: x.get("start_date", {}).get("date", ""),
                reverse=True,
            )[:50]

            enriched_activities = []
            for activity in sorted_activities:
                path = activity.get("path")
                if path:
                    detail = await self.api.get_activity_detail(token, path)
                    if detail and detail.get("success"):
                        # Merge detail data into activity
                        merged = {**activity, **detail}
                        enriched_activities.append(merged)
                    else:
                        enriched_activities.append(activity)
                else:
                    enriched_activities.append(activity)

            data = {"success": data.get("success", True), "activities": enriched_activities}
            logger.info("Enriched %d activities with details", len(enriched_activities))

        # Check for data change
        data_hash = _compute_hash(data)
        if force_send or data_hash != self.state.activities_hash:
            logger.info("Activities data changed, sending webhook")
            self.state.activities_hash = data_hash
            self.state.last_activities = data
            await self.webhook.send_activities(data)
        else:
            logger.debug("Activities data unchanged")


async def run_poller(settings: Settings) -> None:
    """Run the poller with all components."""
    async with AuthManager(
        username=settings.username,
        password=settings.password,
        token_file=settings.token_file,
        refresh_margin=settings.token_refresh_margin,
    ) as auth:
        async with XertAPI() as api:
            async with WebhookClient(
                ha_url=settings.ha_url,
                webhook_id=settings.ha_webhook_id,
                token=settings.ha_token,
            ) as webhook:
                poller = Poller(settings, auth, api, webhook)
                await poller.start()
