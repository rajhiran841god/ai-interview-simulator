"""
Auth endpoints. Thin wrapper over Supabase Auth — no custom password
handling, no credentials touch our own code beyond passthrough to
Supabase's SDK over TLS.

Pilot notice (per Decision Log): consent copy for the pilot notice shown
at signup lives in the frontend signup form, not here. See
/docs/PILOT_NOTICE.md for the approved text.
"""
from fastapi import APIRouter, HTTPException

from app.core.supabase_client import get_supabase
from app.schemas.auth import SignUpRequest, SignInRequest, AuthResponse

router = APIRouter()


@router.post("/signup", response_model=AuthResponse)
def sign_up(payload: SignUpRequest):
    supabase = get_supabase()
    try:
        result = supabase.auth.sign_up(
            {
                "email": payload.email,
                "password": payload.password,
                "options": {"data": {"full_name": payload.full_name}},
            }
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not result.session:
        raise HTTPException(
            status_code=400,
            detail="Sign up succeeded but no session was returned — check if email confirmation is required.",
        )
    if not result.user or not result.user.email:
        raise HTTPException(
            status_code=400,
            detail="Sign up succeeded but no user record was returned.",
        )

    return AuthResponse(
        access_token=result.session.access_token,
        refresh_token=result.session.refresh_token,
        user_id=result.user.id,
        email=result.user.email,
    )


@router.post("/signin", response_model=AuthResponse)
def sign_in(payload: SignInRequest):
    supabase = get_supabase()
    try:
        result = supabase.auth.sign_in_with_password(
            {"email": payload.email, "password": payload.password}
        )
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not result.session or not result.user or not result.user.email:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    return AuthResponse(
        access_token=result.session.access_token,
        refresh_token=result.session.refresh_token,
        user_id=result.user.id,
        email=result.user.email,
    )
