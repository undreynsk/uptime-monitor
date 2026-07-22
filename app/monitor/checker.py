"""Single-site availability check.

Pure network logic: given an HTTP client and a URL, return the outcome.
Knows nothing about the database — easy to test and to reuse.
"""

import time
from dataclasses import dataclass

import httpx


# AM 21/Jul/26 - a plain data container for one check result.
# @dataclass auto-generates __init__ etc. These four fields map 1:1 to the
# check_results table columns. This is NOT a Pydantic schema and NOT a DB model —
# it is an internal result type of the checker layer.
@dataclass
class CheckOutcome:
    is_up: bool                       # AM 21/Jul/26 - True = site considered alive
    status_code: int | None           # AM 21/Jul/26 - HTTP code, or None if no response arrived
    response_time_ms: float | None     # AM 21/Jul/26 - round-trip time, or None on failure
    error: str | None                  # AM 21/Jul/26 - short error tag, or None on success


async def check_site(client: httpx.AsyncClient, url: str) -> CheckOutcome:
    # AM 21/Jul/26 - the client is passed IN (dependency injection), not created here.
    # In tests we inject a client with a fake transport and this code does not notice.

    # AM 21/Jul/26 - monotonic clock: immune to system time changes, meant for durations
    start = time.monotonic()

    # AM 21/Jul/26 - the only network call. Any failure below becomes a result, not a crash,
    # so that one bad site never breaks the whole checking round.
    try:
        response = await client.get(url)
    except httpx.TimeoutException:
        # AM 21/Jul/26 - server did not answer in time (timeout is set on the client)
        return CheckOutcome(is_up=False, status_code=None, response_time_ms=None, error="timeout")
    except httpx.ConnectError:
        # AM 21/Jul/26 - could not even connect: DNS failure or connection refused
        return CheckOutcome(is_up=False, status_code=None, response_time_ms=None, error="connect_error")
    except httpx.HTTPError:
        # AM 21/Jul/26 - catch-all for the httpx error family. MUST come last, because
        # TimeoutException and ConnectError are subclasses of HTTPError.
        return CheckOutcome(is_up=False, status_code=None, response_time_ms=None, error="request_error")

    # AM 21/Jul/26 - we got a response; measure how long it took
    elapsed_ms = round((time.monotonic() - start) * 1000, 1)

    # AM 21/Jul/26 - "up" = server answered and is not failing itself (5xx = server error).
    # 4xx (e.g. 404, 403) means "client's fault", the server is healthy -> still counts as up.
    is_up = response.status_code < 500
    error = None if is_up else f"http_{response.status_code}"

    return CheckOutcome(
        is_up=is_up,
        status_code=response.status_code,
        response_time_ms=elapsed_ms,
        error=error,
    )
