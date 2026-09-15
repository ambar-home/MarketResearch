"""Auth endpoints — login, status, logout. Never returns access_token."""

from fastapi import APIRouter, HTTPException

from app.schemas import AuthStatusResponse, LoginRequest, LoginResponse
from app.services.kite_session import kite_session

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest) -> LoginResponse:
    try:
        result = kite_session.login(
            api_key=body.api_key,
            api_secret=body.api_secret,
            request_token=body.request_token,
        )
    except Exception as exc:
        # Token errors, network errors, bad credentials, etc.
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return LoginResponse(
        ok=True,
        message="Login successful. Access token stored on the server only.",
        user_id=result["user_id"],
        user_name=result["user_name"],
    )


@router.get("/status", response_model=AuthStatusResponse)
def auth_status() -> AuthStatusResponse:
    status = kite_session.status()
    return AuthStatusResponse(**status)


@router.post("/logout", response_model=LoginResponse)
def logout() -> LoginResponse:
    kite_session.logout()
    return LoginResponse(ok=True, message="Logged out. Saved session cleared.")
