"""
Kite session store.

Saves api_key + access_token to a local JSON file so you can restart
the backend (or reload code) without logging in again during development.

The access_token is NEVER returned to the browser.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from kiteconnect import KiteConnect

from app.config import SESSION_FILE

logger = logging.getLogger(__name__)


class KiteSessionService:
    def __init__(self) -> None:
        self._kite: KiteConnect | None = None
        self._api_key: str | None = None
        self._access_token: str | None = None
        self._user_id: str | None = None
        self._user_name: str | None = None

    @property
    def is_authenticated(self) -> bool:
        return self._kite is not None and self._access_token is not None

    def get_kite(self) -> KiteConnect:
        if not self._kite or not self._access_token:
            raise RuntimeError("Not authenticated. Please log in first.")
        return self._kite

    def status(self) -> dict[str, Any]:
        return {
            "authenticated": self.is_authenticated,
            "user_id": self._user_id,
            "user_name": self._user_name,
        }

    def login(self, api_key: str, api_secret: str, request_token: str) -> dict[str, Any]:
        """Exchange request_token for access_token and persist the session."""
        kite = KiteConnect(api_key=api_key.strip())
        session = kite.generate_session(
            request_token.strip(),
            api_secret=api_secret.strip(),
        )

        access_token = session["access_token"]
        kite.set_access_token(access_token)

        profile = kite.profile()
        user_id = str(profile.get("user_id", session.get("user_id", "")))
        user_name = str(profile.get("user_name", ""))

        self._kite = kite
        self._api_key = api_key.strip()
        self._access_token = access_token
        self._user_id = user_id
        self._user_name = user_name

        self._save_to_disk(
            {
                "api_key": self._api_key,
                "access_token": access_token,
                "user_id": user_id,
                "user_name": user_name,
            }
        )

        # Return only safe fields — never the access_token
        return {
            "user_id": user_id,
            "user_name": user_name,
        }

    def logout(self) -> None:
        self._kite = None
        self._api_key = None
        self._access_token = None
        self._user_id = None
        self._user_name = None
        if SESSION_FILE.exists():
            SESSION_FILE.unlink()
            logger.info("Cleared saved Kite session file.")

    def try_restore(self) -> bool:
        """
        Load a previously saved session from disk and verify it still works.
        Returns True if restore succeeded.
        """
        data = self._load_from_disk()
        if not data:
            return False

        api_key = data.get("api_key")
        access_token = data.get("access_token")
        if not api_key or not access_token:
            return False

        try:
            kite = KiteConnect(api_key=api_key)
            kite.set_access_token(access_token)
            profile = kite.profile()  # validates the token

            self._kite = kite
            self._api_key = api_key
            self._access_token = access_token
            self._user_id = str(profile.get("user_id", data.get("user_id", "")))
            self._user_name = str(profile.get("user_name", data.get("user_name", "")))

            # Refresh cached profile fields on disk
            self._save_to_disk(
                {
                    "api_key": self._api_key,
                    "access_token": self._access_token,
                    "user_id": self._user_id,
                    "user_name": self._user_name,
                }
            )
            logger.info("Restored Kite session for user %s", self._user_id)
            return True
        except Exception as exc:
            logger.warning("Saved session is invalid; clearing it. (%s)", exc)
            self.logout()
            return False

    def get_profile(self) -> dict[str, Any]:
        kite = self.get_kite()
        profile = kite.profile()
        return {
            "user_name": str(profile.get("user_name", "")),
            "user_id": str(profile.get("user_id", "")),
            "products": list(profile.get("products") or []),
            "exchanges": list(profile.get("exchanges") or []),
            "email": profile.get("email"),
            "broker": profile.get("broker"),
        }

    def get_portfolio(self) -> dict[str, Any]:
        """Holdings and open positions. Never returns tokens or account secrets."""
        kite = self.get_kite()
        holdings_raw = kite.holdings() or []
        positions_raw = kite.positions() or {}
        net_raw = positions_raw.get("net") or []

        holdings = [self._holding_row(item) for item in holdings_raw]
        holdings.sort(key=lambda row: abs(row["pnl"]), reverse=True)

        positions = [
            self._position_row(item)
            for item in net_raw
            if int(item.get("quantity") or 0) != 0
        ]
        positions.sort(key=lambda row: abs(row["pnl"]), reverse=True)

        invested = sum(row["invested_value"] for row in holdings)
        current = sum(row["current_value"] for row in holdings)
        pnl = sum(row["pnl"] for row in holdings)
        day_pnl = sum(row["day_pnl"] for row in holdings)

        return {
            "summary": {
                "holdings_count": len(holdings),
                "open_positions": len(positions),
                "invested_value": round(invested, 2),
                "current_value": round(current, 2),
                "pnl": round(pnl, 2),
                "pnl_pct": round((pnl / invested) * 100, 2) if invested else 0.0,
                "day_pnl": round(day_pnl, 2),
            },
            "holdings": holdings,
            "positions": positions,
        }

    @staticmethod
    def _money(value: Any) -> float:
        try:
            return round(float(value or 0), 2)
        except (TypeError, ValueError):
            return 0.0

    def _holding_row(self, item: dict[str, Any]) -> dict[str, Any]:
        quantity = int(item.get("quantity") or 0) + int(item.get("t1_quantity") or 0)
        average = self._money(item.get("average_price"))
        last = self._money(item.get("last_price"))
        invested = round(average * quantity, 2)
        current = round(last * quantity, 2)
        return {
            "symbol": str(item.get("tradingsymbol") or ""),
            "exchange": str(item.get("exchange") or ""),
            "quantity": quantity,
            "average_price": average,
            "last_price": last,
            "invested_value": invested,
            "current_value": current,
            "pnl": self._money(item.get("pnl")),
            "day_change_pct": self._money(item.get("day_change_percentage")),
            "day_pnl": round(self._money(item.get("day_change")) * quantity, 2),
        }

    def _position_row(self, item: dict[str, Any]) -> dict[str, Any]:
        quantity = int(item.get("quantity") or 0)
        return {
            "symbol": str(item.get("tradingsymbol") or ""),
            "exchange": str(item.get("exchange") or ""),
            "product": str(item.get("product") or ""),
            "quantity": quantity,
            "average_price": self._money(item.get("average_price")),
            "last_price": self._money(item.get("last_price")),
            "pnl": self._money(item.get("pnl")),
            "realised": self._money(item.get("realised")),
            "unrealised": self._money(item.get("unrealised")),
        }

    def _save_to_disk(self, payload: dict[str, Any]) -> None:
        SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        SESSION_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        logger.info("Saved Kite session to %s", SESSION_FILE)

    def _load_from_disk(self) -> dict[str, Any] | None:
        if not SESSION_FILE.exists():
            return None
        try:
            return json.loads(SESSION_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Could not read session file: %s", exc)
            return None


# Single shared instance for the whole app
kite_session = KiteSessionService()
