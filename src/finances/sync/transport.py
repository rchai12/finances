"""The one function in the project that sends an HTTP request."""

import urllib.error
import urllib.request

from finances import __version__
from finances.sync.simplefin import SyncError

TIMEOUT_SECONDS = 60
USER_AGENT = f"finances/{__version__}"


class _RefuseRedirects(urllib.request.HTTPRedirectHandler):
    """Answer every redirect with its own status, so credentials never reach another address."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: object,
        code: int,
        msg: str,
        headers: object,
        newurl: str,
    ) -> None:
        return None


_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}), _RefuseRedirects)


def urllib_transport(method: str, url: str, headers: dict[str, str]) -> tuple[int, bytes]:
    """Send one request and return its status and body. An error status has an empty body.

    The app is named in User-Agent unless the caller names another agent: the host in front of
    SimpleFIN refuses urllib's default agent.
    """
    request = urllib.request.Request(
        url,
        data=b"" if method == "POST" else None,
        headers={"User-Agent": USER_AGENT, **headers},
        method=method,
    )
    try:
        with _OPENER.open(request, timeout=TIMEOUT_SECONDS) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        error.close()
        return error.code, b""
    except OSError:
        raise SyncError("could not reach the aggregator") from None
