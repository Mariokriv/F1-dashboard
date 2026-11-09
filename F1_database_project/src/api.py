"""Small client for the Ergast-compatible Jolpica F1 API."""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class F1ApiError(RuntimeError):
    """Raised when the F1 API cannot be reached or returns invalid data."""


class F1Api:
    """Fetch paginated data from Jolpica's Ergast-compatible API."""

    def __init__(
        self,
        base_url: str = "https://api.jolpi.ca/ergast/f1",
        timeout: int = 30,
        page_size: int = 1000,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.page_size = page_size

    def get(self, path: str, **params: str | int) -> dict:
        query = urlencode({key: value for key, value in params.items() if value is not None})
        url = f"{self.base_url}/{path.strip('/')}.json"
        if query:
            url = f"{url}?{query}"
        request = Request(url, headers={"Accept": "application/json", "User-Agent": "F1-dashboard/1.0"})
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.load(response)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            raise F1ApiError(f"Unable to fetch {url}: {error}") from error
        if not isinstance(payload, dict):
            raise F1ApiError(f"Unexpected response from {url}")
        return payload

    def get_all(self, path: str, **params: str | int) -> list[dict]:
        """Return all rows from an Ergast collection, following pagination."""
        offset = 0
        rows: list[dict] = []
        collection_name = path.rstrip("/").split("/")[-1].capitalize()
        if collection_name == "Qualifying":
            collection_name = "QualifyingResults"
        while True:
            payload = self.get(path, limit=self.page_size, offset=offset, **params)
            mr_data = payload.get("MRData", {})
            total = int(mr_data.get("total", 0))
            limit = int(mr_data.get("limit", self.page_size))
            collection = self._find_collection(mr_data, collection_name)
            rows.extend(collection)
            if not collection or len(rows) >= total or limit <= 0:
                return rows
            offset += limit

    @staticmethod
    def _find_collection(value: object, collection_name: str) -> list[dict]:
        if isinstance(value, dict):
            candidate = value.get(collection_name)
            if isinstance(candidate, list):
                return candidate
            for child in value.values():
                found = F1Api._find_collection(child, collection_name)
                if found:
                    return found
        elif isinstance(value, list):
            for child in value:
                found = F1Api._find_collection(child, collection_name)
                if found:
                    return found
        return []