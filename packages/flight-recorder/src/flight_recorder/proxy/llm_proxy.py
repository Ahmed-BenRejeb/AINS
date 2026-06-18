"""httpx transport override that intercepts Cloudflare Workers AI calls.

Drop :class:`RecordingTransport` into any ``httpx.Client`` and every CF Workers
AI ``run`` call flows through it. Behaviour is governed by ``FLIGHT_MODE``:

* ``record``      — forward the call, store the response in the cassette, and
                    write an audit record.
* ``replay``      — return the stored response from the cassette; never call out.
                    A request with no recorded response raises
                    :class:`~flight_recorder.exceptions.CassetteMissError`.
* ``passthrough`` — forward only; record nothing.

Non-CF requests always pass straight through, so the transport is transparent to
unrelated traffic. Usage::

    client = httpx.Client(transport=RecordingTransport(run_id="uuid"))
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import httpx
from trace_core import FlightMode

from ..audit.hash_chain import write_audit_record
from ..config import GENESIS_PREV_HASH, is_cf_workers_ai_url, resolve_mode
from ..exceptions import CassetteMissError
from . import cassette


class RecordingTransport(httpx.BaseTransport):
    """An ``httpx`` transport that records, replays, or passes through CF AI calls."""

    def __init__(
        self,
        run_id: str,
        mode: FlightMode | None = None,
        *,
        inner: httpx.BaseTransport | None = None,
    ) -> None:
        """Create a transport bound to one run.

        Args:
            run_id: UUID of the run being recorded/replayed.
            mode: Override for ``FLIGHT_MODE``; resolved from the env when ``None``.
            inner: Transport used to forward live calls; defaults to a real
                ``httpx.HTTPTransport`` (created lazily so replay never opens a
                socket).
        """
        self.run_id = run_id
        self.mode: FlightMode = resolve_mode(mode)
        self._inner = inner
        self._prev_hash = GENESIS_PREV_HASH
        self._sequence = 0
        self.live_call_count = 0
        """Number of calls actually forwarded to the network — must be 0 in replay."""

    @property
    def inner(self) -> httpx.BaseTransport:
        """The live-forwarding transport, created on first use."""
        if self._inner is None:
            self._inner = httpx.HTTPTransport()
        return self._inner

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        """Route one request according to the current mode.

        Args:
            request: The outgoing request.

        Returns:
            The live or cassette-sourced response.
        """
        if not is_cf_workers_ai_url(request.url):
            return self._forward(request)
        step_key = cassette.hash_step_key(cassette.normalize_request(request))
        if self.mode == "replay":
            return self._replay(request, step_key)
        if self.mode == "passthrough":
            return self._forward(request)
        return self._record(request, step_key)

    def _forward(self, request: httpx.Request) -> httpx.Response:
        """Forward a request to the live transport, counting it as a live call."""
        self.live_call_count += 1
        return self.inner.handle_request(request)

    def _record(self, request: httpx.Request, step_key: str) -> httpx.Response:
        """Forward, store the response in the cassette, and write an audit record."""
        response = self._forward(request)
        response.read()
        stored = self._serialize_response(response)
        cassette.save_to_cassette(self.run_id, step_key, stored)
        self._prev_hash = write_audit_record(
            run_id=self.run_id,
            step_id=uuid.uuid4().hex,
            kind="llm_call",
            input_data=self._request_payload(request, step_key),
            output_data=stored,
            prev_hash=self._prev_hash,
            sequence=self._sequence,
        )
        self._sequence += 1
        return self._rebuild_response(stored, request)

    def _replay(self, request: httpx.Request, step_key: str) -> httpx.Response:
        """Return the recorded response for ``step_key`` without any live call."""
        steps = cassette.load_cassette(self.run_id)["steps"]
        if step_key not in steps:
            raise CassetteMissError(step_key)
        return self._rebuild_response(steps[step_key], request)

    @staticmethod
    def _serialize_response(response: httpx.Response) -> dict[str, Any]:
        """Capture a response as a JSON-serializable dict for the cassette."""
        try:
            body: Any = response.json()
            is_json = True
        except json.JSONDecodeError:
            body = response.text
            is_json = False
        return {
            "status_code": response.status_code,
            "headers": {"content-type": response.headers.get("content-type", "application/json")},
            "is_json": is_json,
            "body": body,
        }

    @staticmethod
    def _rebuild_response(stored: dict[str, Any], request: httpx.Request) -> httpx.Response:
        """Reconstruct an ``httpx.Response`` from a stored cassette entry."""
        headers = stored.get("headers", {})
        if stored.get("is_json", True):
            return httpx.Response(
                status_code=stored["status_code"],
                json=stored["body"],
                headers=headers,
                request=request,
            )
        return httpx.Response(
            status_code=stored["status_code"],
            text=stored["body"],
            headers=headers,
            request=request,
        )

    @staticmethod
    def _request_payload(request: httpx.Request, step_key: str) -> dict[str, Any]:
        """Build the audit ``input`` payload describing the intercepted request."""
        raw = request.content
        body: Any = None
        if raw:
            try:
                body = json.loads(raw)
            except json.JSONDecodeError:
                body = raw.decode("utf-8", errors="replace")
        return {"step_key": step_key, "path": request.url.path, "body": body}

    def close(self) -> None:
        """Close the live transport if one was created."""
        if self._inner is not None:
            self._inner.close()
