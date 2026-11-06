"""Strict Dashboard authentication for the verified AstrBot v4.29.4 shape."""

import math
from collections.abc import Mapping

from .errors import ConsoleError
from .protocols import HostContext


def require_dashboard_user(host_context: HostContext, request) -> str:
    import jwt

    try:
        dashboard = host_context.get_config().get("dashboard", {})
        if not isinstance(dashboard, Mapping):
            raise ConsoleError("unauthorized")
        secret = dashboard.get("jwt_secret")
        administrator = dashboard.get("username")
        headers = request.headers.getlist("Authorization")
        if len(headers) != 1 or not headers[0].startswith("Bearer "):
            raise ConsoleError("unauthorized")
        token = headers[0].removeprefix("Bearer ").strip()
        if not isinstance(secret, str) or not secret or not token or len(token) > 8192:
            raise ConsoleError("unauthorized")
        claims = jwt.decode(
            token, secret, algorithms=["HS256"],
            options={
                "require": ["exp", "username"],
                "verify_signature": True,
                "verify_exp": True,
                "verify_nbf": True,
                "verify_iat": True,
                "verify_aud": True,
            },
        )
        expires = claims["exp"]
        if type(expires) not in (int, float) or not math.isfinite(expires):
            raise ConsoleError("unauthorized")
        username = claims["username"]
        if not isinstance(username, str) or not username.strip():
            raise ConsoleError("unauthorized")
        # The host's v1 scope dependency accepts asset JWTs as users. Signature
        # verification alone is therefore insufficient for private reads too.
        if set(claims) - {"username", "exp", "auth_source"}:
            raise ConsoleError("forbidden")
        if claims.get("auth_source", "password") not in ("password", "desktop"):
            raise ConsoleError("forbidden")
        if username != request.username or username != administrator:
            raise ConsoleError("forbidden")
        return username
    except ConsoleError:
        raise
    except (jwt.PyJWTError, TypeError, ValueError, OverflowError, KeyError):
        raise ConsoleError("unauthorized") from None
    except Exception:
        # Missing host request context/config is never an authorization fallback.
        raise ConsoleError("unauthorized") from None
