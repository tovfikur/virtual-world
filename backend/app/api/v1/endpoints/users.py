"""
User endpoints
Profile management, balance operations, and user data
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import logging
from typing import Optional
import uuid

from app.db.session import get_db
from app.models.user import User
from app.models.land import Land
from app.schemas.user_schema import UserResponse, UserUpdate
from app.dependencies import get_current_user, require_role
from app.models.user import UserRole
from app.services.cache_service import cache_service
from app.config import CACHE_TTLS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/users", tags=["users"])


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    current_user: Optional[dict] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get user profile by ID.

    Returns public profile information.
    Some fields may be restricted based on privacy settings.
    """
    # Check cache first
    cache_key = f"user:{user_id}"
    cached_user = await cache_service.get(cache_key)

    if cached_user:
        logger.debug(f"Cache hit for user {user_id}")
        return UserResponse(**cached_user)

    # Fetch from database
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )

    result = await db.execute(
        select(User).where(User.user_id == user_uuid)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Cache the result
    user_dict = user.to_dict()
    await cache_service.set(cache_key, user_dict, ttl=CACHE_TTLS["user_profile"])

    return UserResponse.model_validate(user)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_data: UserUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update user profile.

    Users can only update their own profile unless they are admin.
    """
    # Check permission (user can only edit own profile, or admin can edit anyone)
    if current_user["sub"] != user_id and current_user.get("role") != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own profile"
        )

    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )

    result = await db.execute(
        select(User).where(User.user_id == user_uuid)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Update fields
    update_data = user_data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(user, field, value)

    await db.commit()
    await db.refresh(user)

    # Invalidate cache
    await cache_service.delete(f"user:{user_id}")

    logger.info(f"User profile updated: {user_id}")

    return UserResponse.model_validate(user)


@router.get("/{user_id}/balance")
async def get_balance(
    user_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get user's current BDT balance.

    Users can only view their own balance unless they are admin.
    """
    # Check permission
    if current_user["sub"] != user_id and current_user.get("role") != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own balance"
        )

    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )

    result = await db.execute(
        select(User).where(User.user_id == user_uuid)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return {
        "user_id": str(user.user_id),
        "balance_bdt": user.balance_bdt,
        "currency": "BDT"
    }


@router.post("/{user_id}/topup")
async def initiate_topup(
    user_id: str,
    amount_bdt: int = Query(..., ge=100, le=100000),
    gateway: str = Query(..., pattern="^(bkash|nagad|rocket|sslcommerz)$"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Initiate BDT top-up via payment gateway.

    - **amount_bdt**: Amount to add (100-100,000 BDT)
    - **gateway**: Payment gateway (bkash/nagad/rocket/sslcommerz)

    Returns payment URL for user to complete transaction.

    Note: This is a placeholder. Full payment integration requires
    actual gateway credentials and webhook setup.
    """
    # Check permission
    if current_user["sub"] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only top up your own account"
        )

    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )

    result = await db.execute(
        select(User).where(User.user_id == user_uuid)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # TODO: Implement actual payment gateway integration
    # For now, return placeholder response
    transaction_id = str(uuid.uuid4())

    logger.info(f"Payment initiated: {user_id} - {amount_bdt} BDT via {gateway}")

    return {
        "transaction_id": transaction_id,
        "amount_bdt": amount_bdt,
        "gateway": gateway,
        "status": "pending",
        "payment_url": f"https://sandbox.{gateway}.com/checkout?txn={transaction_id}",
        "message": "Complete payment at the provided URL. Balance will be updated after payment confirmation."
    }


@router.get("/{user_id}/lands")
async def get_user_lands(
    user_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all lands owned by a user.

    Returns paginated list of lands with coordinates and biome information.
    """
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )

    # Verify user exists
    result = await db.execute(
        select(User).where(User.user_id == user_uuid)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Get total count
    count_result = await db.execute(
        select(func.count(Land.land_id)).where(Land.owner_id == user_uuid)
    )
    total = count_result.scalar()

    # Get lands with pagination
    offset = (page - 1) * limit
    result = await db.execute(
        select(Land)
        .where(Land.owner_id == user_uuid)
        .order_by(Land.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    lands = result.scalars().all()

    return {
        "data": [land.to_dict() for land in lands],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit,
            "has_next": page * limit < total,
            "has_prev": page > 1
        }
    }


@router.get("/{user_id}/stats")
async def get_user_stats(
    user_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get user statistics.

    Returns:
    - Total lands owned
    - Total land value
    - Transaction counts
    - Listing counts
    """
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )

    # Verify user exists
    result = await db.execute(
        select(User).where(User.user_id == user_uuid)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Get lands count
    lands_count_result = await db.execute(
        select(func.count(Land.land_id)).where(Land.owner_id == user_uuid)
    )
    lands_count = lands_count_result.scalar()

    # Get total land value
    lands_value_result = await db.execute(
        select(func.sum(Land.price_base_bdt)).where(Land.owner_id == user_uuid)
    )
    lands_value = lands_value_result.scalar() or 0

    # Get transactions count (as buyer and seller)
    from app.models.transaction import Transaction

    transactions_as_buyer_result = await db.execute(
        select(func.count(Transaction.transaction_id))
        .where(Transaction.buyer_id == user_uuid)
    )
    transactions_as_buyer = transactions_as_buyer_result.scalar()

    transactions_as_seller_result = await db.execute(
        select(func.count(Transaction.transaction_id))
        .where(Transaction.seller_id == user_uuid)
    )
    transactions_as_seller = transactions_as_seller_result.scalar()

    return {
        "user_id": str(user_uuid),
        "username": user.username,
        "stats": {
            "lands_owned": lands_count,
            "total_land_value_bdt": int(lands_value),
            "transactions_as_buyer": transactions_as_buyer,
            "transactions_as_seller": transactions_as_seller,
            "total_transactions": transactions_as_buyer + transactions_as_seller
        }
    }


@router.put("/{user_id}/profile", response_model=UserResponse)
async def update_profile(
    user_id: str,
    update_data: dict,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update user profile (avatar, bio, etc).

    Users can only update their own profile unless they are admin.
    Accepts: avatar_url, bio
    """
    # Check permission
    if current_user["sub"] != user_id and current_user.get("role") != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own profile"
        )

    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )

    result = await db.execute(
        select(User).where(User.user_id == user_uuid)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Only allow updating specific fields
    allowed_fields = {"avatar_url", "bio"}
    update_fields = {k: v for k, v in update_data.items() if k in allowed_fields and v is not None}

    for field, value in update_fields.items():
        setattr(user, field, value)

    await db.commit()
    await db.refresh(user)

    # Invalidate cache
    await cache_service.delete(f"user:{user_id}")

    logger.info(f"User profile updated: {user_id}")

    return UserResponse.model_validate(user)


@router.post("/{user_id}/avatar")
async def upload_avatar(
    user_id: str,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload user avatar image.

    Accepts: PNG, JPEG (max 5MB)
    Returns: {avatar_url: string, user: UserResponse}
    """
    from app.services.file_upload_service import file_upload_service

    # Check permission
    if current_user["sub"] != user_id and current_user.get("role") != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own avatar"
        )

    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )

    result = await db.execute(
        select(User).where(User.user_id == user_uuid)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    try:
        # Upload avatar
        avatar_url = await file_upload_service.upload_avatar(file, user_id)

        # Delete old avatar if exists
        if user.avatar_url:
            file_upload_service.delete_avatar(user.avatar_url)

        # Update user
        user.avatar_url = avatar_url
        await db.commit()
        await db.refresh(user)

        # Invalidate cache
        await cache_service.delete(f"user:{user_id}")

        logger.info(f"Avatar uploaded for user {user_id}: {avatar_url}")

        return {"avatar_url": avatar_url, "user": UserResponse.model_validate(user)}

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Avatar upload failed for {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar"
        )


@router.get("/{user_id}/transactions")
async def get_user_transactions(
    user_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get transaction history for a user.

    Users can view their own transactions.
    Admins can view any user's transactions.

    Returns: Paginated list of transactions (as buyer and seller)
    """
    from app.models.transaction import Transaction

    # Check permission
    if current_user["sub"] != user_id and current_user.get("role") != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own transactions"
        )

    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )

    # Verify user exists
    result = await db.execute(
        select(User).where(User.user_id == user_uuid)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Get transactions where user is buyer OR seller
    # Combine both queries
    offset = (page - 1) * limit

    result = await db.execute(
        select(Transaction)
        .where(
            (Transaction.buyer_id == user_uuid) | (Transaction.seller_id == user_uuid)
        )
        .order_by(Transaction.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    transactions = result.scalars().all()

    # Get total count
    count_result = await db.execute(
        select(func.count(Transaction.transaction_id))
        .where(
            (Transaction.buyer_id == user_uuid) | (Transaction.seller_id == user_uuid)
        )
    )
    total = count_result.scalar()

    return {
        "user_id": str(user_uuid),
        "transactions": [t.to_dict() for t in transactions],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit,
            "has_next": page * limit < total,
            "has_prev": page > 1
        }
    }
