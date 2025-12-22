"""Livekit token generation endpoint"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from livekit import AccessToken
import os

from app.database import get_db

router = APIRouter(prefix="/livekit", tags=["livekit"])

# Livekit credentials from environment
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "devkey")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "secret")
LIVEKIT_URL = os.getenv("LIVEKIT_URL", "ws://localhost:7880")


@router.get("/token")
async def get_livekit_token(
    room: str,
    identity: str,
    username: str = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Generate a Livekit access token for a user to join a room.
    
    Room name is based on land coordinates:
    - land_265_86 = Room at coordinates (265, 86)
    - Same coordinates = same room = can hear/see each other
    """
    if not room or not identity:
        raise HTTPException(status_code=400, detail="room and identity required")

    try:
        # Create token
        token = AccessToken(
            api_key=LIVEKIT_API_KEY,
            api_secret=LIVEKIT_API_SECRET,
            identity=identity,
            name=username or identity,
            grants={
                "roomJoin": True,
                "room": room,
                "canPublish": True,
                "canPublishData": True,
                "canSubscribe": True,
            },
        )

        print(f"[livekit] Generated token for user={identity} room={room}")

        return {
            "token": token.toJwt(),
            "url": LIVEKIT_URL,
            "room": room,
        }

    except Exception as e:
        print(f"[livekit] Error generating token: {e}")
        raise HTTPException(status_code=500, detail=str(e))
