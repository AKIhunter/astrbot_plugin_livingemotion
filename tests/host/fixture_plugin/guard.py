"""Version-pinned, bearer-only guard for AstrBot 4.29.4 dashboard claims."""

import math

import jwt
from astrbot.api.web import request


def verified_dashboard_user(context):
    config = context.get_config().get("dashboard", {})
    secret = config.get("jwt_secret")
    authorization = request.headers.get("Authorization", "")
    if not isinstance(secret, str) or not secret or not authorization.startswith("Bearer "):
        return None
    token = authorization.removeprefix("Bearer ").strip()
    if not token or len(token) > 8192:
        return None
    try:
        claims = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options={
                "require": ["exp", "username"],
                "verify_signature": True,
                "verify_exp": True,
                "verify_nbf": True,
                "verify_iat": True,
                "verify_aud": True,
            },
        )
    except jwt.PyJWTError:
        return None
    # Dashboard password/desktop JWTs have only this shape in the pinned host.
    # Reject typed asset/OAuth tokens and unknown future claim shapes.
    if set(claims) - {"username", "exp", "auth_source"}:
        return None
    if claims.get("auth_source", "password") not in {"password", "desktop"}:
        return None
    expires = claims["exp"]
    if type(expires) not in {int, float} or not math.isfinite(expires):
        return None
    username = claims["username"]
    if not isinstance(username, str) or not username:
        return None
    if username != request.username or username != config.get("username"):
        return None
    return username
