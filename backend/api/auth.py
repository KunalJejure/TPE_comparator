"""
backend/api/auth.py
Microsoft Entra ID (Azure AD) Single Sign-On via OAuth2 / OpenID Connect.
Only users from the configured tenant (company domain) can log in.
"""

import logging
import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from authlib.integrations.starlette_client import OAuth
from starlette.config import Config as StarletteConfig

from backend.config import (
    AZURE_CLIENT_ID,
    AZURE_CLIENT_SECRET,
    AZURE_TENANT_ID,
    AZURE_METADATA_URL,
    SECRET_KEY,
    BASE_URL,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["auth"])

# ------------------------------------------------------------------ #
#  OAuth2 / OpenID Connect setup via Authlib
# ------------------------------------------------------------------ #

oauth = OAuth()

# Only register if credentials are configured
_SSO_ENABLED = all([AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID]) and \
               AZURE_CLIENT_ID != "your-client-id-here"

if _SSO_ENABLED:
    oauth.register(
        name="azure",
        client_id=AZURE_CLIENT_ID,
        client_secret=AZURE_CLIENT_SECRET,
        server_metadata_url=AZURE_METADATA_URL,
        client_kwargs={
            "scope": "openid email profile",
        },
    )
    logger.info("Microsoft Entra ID SSO is enabled (Tenant: %s)", AZURE_TENANT_ID)
else:
    logger.warning(
        "SSO is NOT configured. Set AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, "
        "and AZURE_TENANT_ID in .env to enable it."
    )


# ------------------------------------------------------------------ #
#  Helpers
# ------------------------------------------------------------------ #

# You can add ALLOWED_DOMAIN=yourcompany.com to .env to restrict by email domain
ALLOWED_DOMAIN: Optional[str] = os.getenv("ALLOWED_DOMAIN", None)


def _validate_user(user_info: dict):
    """
    Validate user belongs to the company domain.
    Checks both tenant ID (primary) and email domain (secondary).
    """
    email = user_info.get("email", "") or user_info.get("preferred_username", "")
    tid = user_info.get("tid", "")

    # Primary check: Tenant ID must match
    if AZURE_TENANT_ID and tid and tid != AZURE_TENANT_ID:
        logger.warning("User from wrong tenant: %s (expected %s)", tid, AZURE_TENANT_ID)
        raise HTTPException(
            status_code=403,
            detail="Access denied. Your organization is not authorized to use this application."
        )

    # Secondary check: Email domain restriction (if configured)
    if ALLOWED_DOMAIN and email:
        domain = email.split("@")[-1].lower()
        if domain != ALLOWED_DOMAIN.lower():
            logger.warning("User email domain not allowed: %s", email)
            raise HTTPException(
                status_code=403,
                detail=f"Access denied. Only @{ALLOWED_DOMAIN} accounts can sign in."
            )

    return email


# ------------------------------------------------------------------ #
#  Routes
# ------------------------------------------------------------------ #

@router.get("/auth/status")
async def auth_status(request: Request):
    """Check if the current user is authenticated."""
    user = request.session.get("user")
    if user:
        return {
            "authenticated": True,
            "sso_enabled": _SSO_ENABLED,
            "user": {
                "name": user.get("name", ""),
                "email": user.get("email", ""),
                "picture": user.get("picture", ""),
            },
        }
    return {"authenticated": False, "sso_enabled": _SSO_ENABLED}


@router.get("/auth/login")
async def login(request: Request):
    """
    Initiate the Microsoft SSO login flow.
    Redirects the user to Microsoft's login page.
    """
    if not _SSO_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="SSO is not configured. Please set Azure AD credentials in .env file."
        )

    if BASE_URL:
        redirect_uri = f"{BASE_URL.rstrip('/')}/auth/callback"
    else:
        redirect_uri = str(request.url_for("auth_callback"))
        redirect_uri = redirect_uri.replace("://0.0.0.0:", "://localhost:")

    logger.info("OAuth redirect URI: %s", redirect_uri)
    return await oauth.azure.authorize_redirect(request, redirect_uri)


@router.get("/auth/callback")
async def auth_callback(request: Request):
    """
    Handle the OAuth2 callback from Microsoft.
    Exchanges the auth code for tokens, validates the user, and creates a session.
    """
    if not _SSO_ENABLED:
        raise HTTPException(status_code=503, detail="SSO is not configured.")

    try:
        token = await oauth.azure.authorize_access_token(request)
    except Exception as e:
        logger.error("OAuth token exchange failed: %s", e)
        raise HTTPException(
            status_code=401,
            detail="Authentication failed. Please try again."
        )

    # Extract user info from the ID token
    user_info = token.get("userinfo", {})
    if not user_info:
        # Fallback: parse the id_token manually
        user_info = dict(token.get("id_token_claims", {}))

    # Validate user belongs to the company
    email = _validate_user(user_info)

    # Store user info in session
    request.session["user"] = {
        "name": user_info.get("name", email.split("@")[0] if email else "User"),
        "email": email,
        "picture": user_info.get("picture", ""),
        "tid": user_info.get("tid", ""),
        "login_time": datetime.utcnow().isoformat(),
    }

    logger.info("✅ User logged in via SSO: %s", email)

    # Redirect back to the main app
    return RedirectResponse(url="/")


@router.get("/auth/logout")
async def logout(request: Request):
    """Clear the session and optionally redirect to Microsoft logout."""
    user = request.session.get("user", {})
    email = user.get("email", "unknown")
    request.session.clear()
    logger.info("🔒 User logged out: %s", email)

    if _SSO_ENABLED and AZURE_TENANT_ID:
        if BASE_URL:
            post_logout_url = BASE_URL.rstrip("/") + "/"
        else:
            post_logout_url = str(request.url_for("home"))
            post_logout_url = post_logout_url.replace("://0.0.0.0:", "://localhost:")
        ms_logout_url = (
            f"https://login.microsoftonline.com/{AZURE_TENANT_ID}/oauth2/v2.0/logout"
            f"?post_logout_redirect_uri={post_logout_url}"
        )
        return RedirectResponse(url=ms_logout_url)

    return RedirectResponse(url="/")
