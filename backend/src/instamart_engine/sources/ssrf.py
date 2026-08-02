"""URL validation for connectors that fetch arbitrary configured URLs.

edgecases.md SRC-012 (reject unsupported protocols) and SRC-013 (block URLs
that resolve to internal/private networks — SSRF). Used by the public-web
connector before any HTTP request is made.
"""

import ipaddress
import socket
from urllib.parse import urlparse

from instamart_engine.sources.exceptions import SourceConfigError, SSRFBlockedError

_ALLOWED_SCHEMES = {"https", "http"}


def validate_public_url(url: str, *, allow_http: bool = False) -> None:
    """Raise if `url` is unsafe to fetch. Does not perform the fetch itself."""
    parsed = urlparse(url)

    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise SourceConfigError(f"Unsupported URL scheme: {parsed.scheme!r}")
    if parsed.scheme == "http" and not allow_http:
        raise SourceConfigError(
            "Plain http is not permitted unless explicitly allowlisted for this source"
        )
    if not parsed.hostname:
        raise SourceConfigError(f"URL has no hostname: {url!r}")

    try:
        resolved = socket.getaddrinfo(parsed.hostname, None)
    except OSError as exc:
        raise SourceConfigError(f"Could not resolve hostname: {parsed.hostname!r}") from exc

    for _family, _type, _proto, _canonname, sockaddr in resolved:
        ip_str = sockaddr[0]
        ip = ipaddress.ip_address(ip_str)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise SSRFBlockedError(
                f"URL {url!r} resolves to a private/internal address ({ip_str}); refusing"
            )
