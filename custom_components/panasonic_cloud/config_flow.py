"""Config flow for Panasonic MirAIe integration."""
from __future__ import annotations

import base64
import json
import logging
from typing import Any, cast

import aiohttp

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN,
    AUTH_URL,
    TOKEN_URL,
    CLIENT_ID,
    CLIENT_SECRET,
    OAUTH_SCOPE,
)

_LOGGER = logging.getLogger(__name__)


class PanasonicMirAIeOAuth2Implementation(
    config_entry_oauth2_flow.LocalOAuth2Implementation
):
    """Panasonic MirAIe OAuth2 implementation.

    Token requests (both initial exchange and refresh) require:
    - Basic Auth header: base64(client_id:client_secret)
    - tenantId: panasonic header
    - client_id in POST body
    - client_secret NOT in POST body
    """

    def __init__(self, hass: Any) -> None:
        """Initialize."""
        super().__init__(
            hass=hass,
            domain=DOMAIN,
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            authorize_url=AUTH_URL,
            token_url=TOKEN_URL,
        )

    @property
    def name(self) -> str:
        """Name of the implementation."""
        return "Panasonic MirAIe"

    @property
    def extra_authorize_data(self) -> dict:
        """Extra data for the authorize URL."""
        return {"scope": OAUTH_SCOPE}

    def _build_auth_headers(self) -> dict[str, str]:
        """Build headers with Basic Auth and tenantId for token requests."""
        credentials = f"{self.client_id}:{self.client_secret}"
        basic_auth = base64.b64encode(
            credentials.encode("utf-8")
        ).decode("utf-8")
        return {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {basic_auth}",
            "tenantId": "panasonic",
            "Accept": "application/json",
        }

    async def _token_request(self, data: dict) -> dict:
        """Make a token request with Basic Auth and tenantId header.

        Handles both initial token exchange and token refresh.
        """
        session = async_get_clientsession(self.hass)
        headers = self._build_auth_headers()

        # Only send client_id in body, NOT client_secret
        body_data = {k: v for k, v in data.items() if k != "client_secret"}
        body_data["client_id"] = self.client_id

        _LOGGER.debug(
            "Token request to %s with grant_type=%s",
            self.token_url,
            body_data.get("grant_type", "unknown"),
        )

        try:
            resp = await session.post(
                self.token_url, headers=headers, data=body_data
            )
            resp_text = await resp.text()

            _LOGGER.debug(
                "Token response status=%s body=%s",
                resp.status,
                resp_text[:300],
            )

            if resp.status >= 400:
                _LOGGER.error(
                    "Token request failed (%s): %s",
                    resp.status,
                    resp_text[:300],
                )
                resp.raise_for_status()

            # Parse JSON manually (server may return wrong content-type)
            try:
                result = json.loads(resp_text)
            except json.JSONDecodeError:
                _LOGGER.error(
                    "Token response is not valid JSON: %s", resp_text[:300]
                )
                raise aiohttp.ClientResponseError(
                    request_info=resp.request_info,
                    history=(),
                    status=resp.status,
                    message="Invalid JSON in token response",
                )

            if "error" in result:
                _LOGGER.error(
                    "Token error: %s - %s",
                    result.get("error"),
                    result.get("error_description", ""),
                )
                raise aiohttp.ClientResponseError(
                    request_info=resp.request_info,
                    history=(),
                    status=400,
                    message=result.get("error_description", result["error"]),
                )

            # Fix scope field: HA expects string, Panasonic returns object
            if isinstance(result.get("scope"), dict):
                result["scope"] = ""

            _LOGGER.info(
                "Token %s successful",
                "refresh" if data.get("grant_type") == "refresh_token"
                else "exchange",
            )
            return cast(dict, result)

        except aiohttp.ClientResponseError:
            raise
        except Exception as err:
            _LOGGER.error("Token request error: %s", err)
            raise

    async def _async_refresh_token(self, token: dict) -> dict:
        """Refresh a token using the same custom headers.

        Override parent to ensure refresh also uses Basic Auth + tenantId.
        """
        new_token = await self._token_request(
            {
                "grant_type": "refresh_token",
                "client_id": self.client_id,
                "refresh_token": token["refresh_token"],
            }
        )
        return {**token, **new_token}


class PanasonicMirAIeOAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler,
    domain=DOMAIN,
):
    """Handle a config flow for Panasonic MirAIe."""

    DOMAIN = DOMAIN
    VERSION = 1

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return _LOGGER

    @property
    def extra_authorize_data(self) -> dict:
        """Extra data for the authorize URL."""
        return {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        config_entry_oauth2_flow.async_register_implementation(
            self.hass,
            DOMAIN,
            PanasonicMirAIeOAuth2Implementation(self.hass),
        )
        return await self.async_step_pick_implementation(user_input)

    async def async_oauth_create_entry(
        self, data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Create an entry for the flow."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title="Panasonic MirAIe",
            data=data,
        )
