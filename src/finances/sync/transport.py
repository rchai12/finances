"""The one function in the project that sends an HTTP request."""

import urllib.error
import urllib.request

from finances.sync.simplefin import SyncError

TIMEOUT_SECONDS = 60


def urllib_transport(method: str, url: str, headers: dict[str, str]) -> tuple[int, bytes]:
    """Send one request and return its status and body. An error status has an empty body."""
    request = urllib.request.Request(
        url, data=b"" if method == "POST" else None, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        error.close()
        return error.code, b""
    except OSError:
        raise SyncError("could not reach the aggregator") from None
