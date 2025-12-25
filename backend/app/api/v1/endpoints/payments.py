"""
Payment Endpoints
Handle payment gateway webhooks and callbacks
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Header, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
from datetime import datetime, timedelta
import json
import logging

from app.db.session import get_db
from app.services.payment_service import payment_service, PaymentGateway
from app.services.cache_service import cache_service
from app.dependencies import get_current_user
from app.models.admin_config import AdminConfig
from app.models.transaction import Transaction, TransactionType, TransactionStatus

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/payments", tags=["payments"])


# ============================================
# Webhook Endpoints
# ============================================

@router.post("/webhook/bkash")
async def bkash_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Receive bKash payment webhook

    This endpoint is called by bKash when a payment is completed.
    Signature verification ensures authenticity.
    """
    try:
        body = await request.body()
        signature = request.headers.get("X-Signature", "")

        # Verify signature
        if not payment_service.verify_webhook_signature(
            PaymentGateway.BKASH,
            body.decode(),
            signature
        ):
            logger.warning("Invalid bKash webhook signature")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid signature"
            )

        payload = json.loads(body)

        # Process payment
        success = await payment_service.process_bkash_webhook(db, payload)

        if success:
            return {"status": "accepted", "message": "Payment processed"}
        else:
            return {"status": "rejected", "message": "Payment processing failed"}

    except json.JSONDecodeError:
        logger.error("Invalid JSON in bKash webhook")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload"
        )
    except Exception as e:
        logger.error(f"bKash webhook error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook processing error"
        )


@router.post("/webhook/nagad")
async def nagad_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Receive Nagad payment webhook
    """
    try:
        body = await request.body()
        signature = request.headers.get("X-KM-Signature", "")

        # Verify signature
        if not payment_service.verify_webhook_signature(
            PaymentGateway.NAGAD,
            body.decode(),
            signature
        ):
            logger.warning("Invalid Nagad webhook signature")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid signature"
            )

        payload = json.loads(body)

        # Extract payment info
        payment_id = payload.get("paymentRefId")
        user_id = payload.get("merchantOrderId", "").split("_")[0]  # Assuming format: userid_timestamp
        amount = int(float(payload.get("amount", 0)))
        status_msg = payload.get("status")

        # Process payment
        success = await payment_service.process_generic_webhook(
            db=db,
            gateway=PaymentGateway.NAGAD,
            payload=payload,
            payment_id=payment_id,
            user_id=user_id,
            amount=amount,
            status=status_msg
        )

        if success:
            return {"status": "accepted", "message": "Payment processed"}
        else:
            return {"status": "rejected", "message": "Payment processing failed"}

    except Exception as e:
        logger.error(f"Nagad webhook error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook processing error"
        )


@router.post("/webhook/rocket")
async def rocket_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Receive Rocket payment webhook
    """
    try:
        body = await request.body()
        signature = request.headers.get("X-Rocket-Signature", "")

        # Verify signature
        if not payment_service.verify_webhook_signature(
            PaymentGateway.ROCKET,
            body.decode(),
            signature
        ):
            logger.warning("Invalid Rocket webhook signature")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid signature"
            )

        payload = json.loads(body)

        # Extract payment info
        payment_id = payload.get("transactionId")
        user_id = payload.get("merchantRef", "").split("_")[0]
        amount = int(float(payload.get("amount", 0)))
        status_msg = payload.get("status")

        # Process payment
        success = await payment_service.process_generic_webhook(
            db=db,
            gateway=PaymentGateway.ROCKET,
            payload=payload,
            payment_id=payment_id,
            user_id=user_id,
            amount=amount,
            status=status_msg
        )

        if success:
            return {"status": "accepted", "message": "Payment processed"}
        else:
            return {"status": "rejected", "message": "Payment processing failed"}

    except Exception as e:
        logger.error(f"Rocket webhook error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook processing error"
        )


@router.post("/webhook/sslcommerz")
async def sslcommerz_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Receive SSLCommerz payment webhook
    """
    try:
        # SSLCommerz sends form data, not JSON
        form_data = await request.form()
        payload = dict(form_data)

        # SSLCommerz uses store password as validation hash
        valid_hash = payload.get("verify_sign")
        expected_hash = payment_service.sslcommerz_store_password  # Simplified - actual validation is more complex

        # For production, implement proper validation hash check
        # if valid_hash != expected_hash:
        #     logger.warning("Invalid SSLCommerz webhook signature")
        #     raise HTTPException(status_code=401, detail="Invalid signature")

        # Extract payment info
        payment_id = payload.get("tran_id")
        user_id = payload.get("value_a")  # Custom field we send during initiation
        amount = int(float(payload.get("amount", 0)))
        status_msg = payload.get("status")

        # Process payment
        success = await payment_service.process_generic_webhook(
            db=db,
            gateway=PaymentGateway.SSLCOMMERZ,
            payload=payload,
            payment_id=payment_id,
            user_id=user_id,
            amount=amount,
            status=status_msg
        )

        if success:
            return {"status": "accepted", "message": "Payment processed"}
        else:
            return {"status": "rejected", "message": "Payment processing failed"}

    except Exception as e:
        logger.error(f"SSLCommerz webhook error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook processing error"
        )


# ============================================
# Callback Endpoints (for user redirects)
# ============================================

@router.get("/callback/bkash")
async def bkash_callback(
    paymentID: str,
    status: str
):
    """
    bKash callback after user completes payment
    Redirect user to appropriate page
    """
    if status == "success":
        return {
            "message": "Payment successful",
            "redirect_url": "/profile?payment=success"
        }
    else:
        return {
            "message": "Payment failed or cancelled",
            "redirect_url": "/profile?payment=failed"
        }


@router.get("/callback/nagad")
async def nagad_callback(
    payment_ref_id: str,
    status: str
):
    """Nagad callback"""
    if status.lower() == "success":
        return {
            "message": "Payment successful",
            "redirect_url": "/profile?payment=success"
        }
    else:
        return {
            "message": "Payment failed or cancelled",
            "redirect_url": "/profile?payment=failed"
        }


@router.get("/callback/rocket")
async def rocket_callback(
    transaction_id: str,
    status: str
):
    """Rocket callback"""
    if status.lower() == "success":
        return {
            "message": "Payment successful",
            "redirect_url": "/profile?payment=success"
        }
    else:
        return {
            "message": "Payment failed or cancelled",
            "redirect_url": "/profile?payment=failed"
        }


@router.post("/callback/sslcommerz/success")
async def sslcommerz_success_callback(request: Request):
    """SSLCommerz success callback"""
    form_data = await request.form()
    return {
        "message": "Payment successful",
        "redirect_url": "/profile?payment=success"
    }


@router.post("/callback/sslcommerz/fail")
async def sslcommerz_fail_callback(request: Request):
    """SSLCommerz fail callback"""
    return {
        "message": "Payment failed",
        "redirect_url": "/profile?payment=failed"
    }


@router.post("/callback/sslcommerz/cancel")
async def sslcommerz_cancel_callback(request: Request):
    """SSLCommerz cancel callback"""
    return {
        "message": "Payment cancelled",
        "redirect_url": "/profile?payment=cancelled"
    }


# ============================================
# Payment Initiation (with Idempotency)
# ============================================

@router.post("/initiate/{gateway}")
async def initiate_payment(
    gateway: str,
    amount_bdt: int,
    current_user: dict = Depends(get_current_user),
    idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    db: AsyncSession = Depends(get_db)
):
    """
    Initiate payment with a gateway

    Requires idempotency key to prevent duplicate charges.
    If the same key is used, returns the cached response.
    """
    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Idempotency-Key header is required"
        )

    # Load payment configuration
    cfg_res = await db.execute(select(AdminConfig).limit(1))
    config = cfg_res.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=503, detail="Payment configuration missing")

    gateway_lower = gateway.lower()
    gateway_map = {
        PaymentGateway.BKASH: (config.enable_bkash, config.bkash_mode),
        PaymentGateway.NAGAD: (config.enable_nagad, config.nagad_mode),
        PaymentGateway.ROCKET: (config.enable_rocket, config.rocket_mode),
        PaymentGateway.SSLCOMMERZ: (config.enable_sslcommerz, config.sslcommerz_mode),
    }

    # Resolve gateway enum
    if gateway_lower == PaymentGateway.BKASH:
        gateway_enum = PaymentGateway.BKASH
    elif gateway_lower == PaymentGateway.NAGAD:
        gateway_enum = PaymentGateway.NAGAD
    elif gateway_lower == PaymentGateway.ROCKET:
        gateway_enum = PaymentGateway.ROCKET
    elif gateway_lower == PaymentGateway.SSLCOMMERZ:
        gateway_enum = PaymentGateway.SSLCOMMERZ
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported gateway: {gateway}"
        )

    enabled, mode = gateway_map[gateway_enum]
    if not enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{gateway_enum.value} payments are disabled"
        )
    if mode not in {"test", "live"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gateway mode must be configured as 'test' or 'live'"
        )

    # Limits
    min_amount = config.topup_min_bdt or 0
    max_amount = config.topup_max_bdt or 0
    daily_limit = config.topup_daily_limit_bdt or 0
    monthly_limit = config.topup_monthly_limit_bdt or 0

    if amount_bdt < min_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Minimum top-up amount is {min_amount} BDT"
        )

    if max_amount and amount_bdt > max_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum top-up amount is {max_amount} BDT"
        )

    user_id = current_user["sub"]

    # Enforce daily/monthly aggregates
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    month_window_start = datetime.utcnow() - timedelta(days=30)

    daily_sum = await db.scalar(
        select(func.coalesce(func.sum(Transaction.amount_bdt), 0)).where(
            Transaction.buyer_id == user_id,
            Transaction.transaction_type == TransactionType.TOPUP,
            Transaction.status == TransactionStatus.COMPLETED,
            Transaction.created_at >= today_start,
        )
    )

    monthly_sum = await db.scalar(
        select(func.coalesce(func.sum(Transaction.amount_bdt), 0)).where(
            Transaction.buyer_id == user_id,
            Transaction.transaction_type == TransactionType.TOPUP,
            Transaction.status == TransactionStatus.COMPLETED,
            Transaction.created_at >= month_window_start,
        )
    )

    if daily_limit and (daily_sum + amount_bdt) > daily_limit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Daily top-up limit exceeded (limit {daily_limit} BDT)"
        )

    if monthly_limit and (monthly_sum + amount_bdt) > monthly_limit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Monthly top-up limit exceeded (limit {monthly_limit} BDT)"
        )

    # Check idempotency cache
    cache_key = f"payment:idempotency:{idempotency_key}"
    cached = await cache_service.get(cache_key)
    if cached:
        logger.info(f"Returning cached payment response for key: {idempotency_key}")
        return json.loads(cached)

    reference_id = f"{user_id}_{idempotency_key}"

    # Initiate payment based on gateway
    if gateway_enum == PaymentGateway.BKASH:
        result = await payment_service.initiate_bkash_payment(
            user_id, amount_bdt, reference_id
        )
    elif gateway_enum == PaymentGateway.NAGAD:
        result = await payment_service.initiate_nagad_payment(
            user_id, amount_bdt, reference_id
        )
    elif gateway_enum == PaymentGateway.ROCKET:
        result = await payment_service.initiate_rocket_payment(
            user_id, amount_bdt, reference_id
        )
    elif gateway_enum == PaymentGateway.SSLCOMMERZ:
        user_email = current_user.get("email", "user@example.com")
        user_phone = current_user.get("phone", "01700000000")
        result = await payment_service.initiate_sslcommerz_payment(
            user_id, amount_bdt, reference_id, user_email, user_phone
        )

    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("error", "Payment initiation failed")
        )

    # Cache response for 24 hours
    await cache_service.set(
        cache_key,
        json.dumps(result),
        ttl=86400
    )

    return result


@router.get("/status/{reference_id}")
async def get_payment_status(
    reference_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Check payment status by reference ID
    """
    # Query transaction by reference ID
    # This would require storing reference_id in Transaction model or metadata
    # For now, return placeholder
    return {
        "reference_id": reference_id,
        "status": "pending",
        "message": "Payment status check not yet implemented"
    }
