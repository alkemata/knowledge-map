"""Fetch private, aggregate WP Statistics reports for administrators."""

import logging

import httpx

from .config import get_settings

logger = logging.getLogger(__name__)
URL = "https://alkemata.com/wp-json/alkemata-analytics/v1/summary"


def get_wordpress_statistics(days: int) -> dict | None:
    token = get_settings().wordpress_stats_token
    if not token:
        return None
    try:
        response = httpx.get(
            URL, params={"days": days}, headers={"Authorization": f"Bearer {token}"}, timeout=5,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("source") != "WP Statistics" or not isinstance(payload.get("daily"), list):
            raise ValueError("Unexpected WordPress statistics response")
        return payload
    except (httpx.HTTPError, ValueError) as error:
        logger.warning("WordPress statistics unavailable: %s", type(error).__name__)
        return None
