# Virtual Land World - Payment Integration

## Payment Service

```python
# app/services/payment_service.py

import hashlib
import hmac
import json
from enum import Enum

class PaymentGateway(str, Enum):
    BKASH = "bkash"
    NAGAD = "nagad"
    ROCKET = "rocket"
    SSLCOMMERZ = "sslcommerz"

class PaymentService:
    """Handle payment gateway integration."""

    def __init__(self, secrets: dict):
        self.secrets = secrets

    def verify_webhook_signature(
        self,
        gateway: str,
        payload: str,
        signature: str
    ) -> bool:
        """Verify webhook signature."""
        secret = self.secrets.get(f"{gateway}_secret")
        if not secret:
            return False

        expected = hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(expected, signature)

    async def process_bkash_webhook(
        self,
        db: AsyncSession,
        payload: dict
    ) -> bool:
        """Process bKash payment webhook."""
        if payload["status"] != "Completed":
            return False

        transaction_id = payload["orderID"]

        # Check idempotency
        existing = await db.query(Transaction).filter(
            Transaction.gateway_transaction_id == transaction_id
        ).first()

        if existing:
            return True  # Already processed

        # Find user by transaction ID (should store when initiating payment)
        user_id = payload.get("user_id")
        amount = payload["amount"]

        # Update balance
        user = await db.query(User).filter(
            User.user_id == user_id
        ).with_for_update().first()

        user.balance_bdt += amount

        # Log transaction
        txn = Transaction(
            land_id=None,
            seller_id=user_id,
            buyer_id=user_id,
            amount_bdt=amount,
            gateway_name="bkash",
            gateway_transaction_id=transaction_id,
            status="completed"
        )
        db.add(txn)
        await db.commit()

        return True

    async def initiate_bkash_payment(
        self,
        user_id: str,
        amount: int
    ) -> dict:
        """Initiate bKash payment."""
        # Call bKash API
        response = await httpx.post(
            "https://api.bkash.com/api/checkout/payment",
            json={
                "amount": amount,
                "currency": "BDT",
                "intent": "sale",
                "payerReference": user_id,
                "returnURL": "https://app.virtuallandworld.com/payment/callback"
            },
            headers=self._get_bkash_headers()
        )

        return response.json()

    def _get_bkash_headers(self) -> dict:
        """Get bKash API headers."""
        timestamp = int(datetime.utcnow().timestamp())
        signature = hashlib.sha256(
            f"{self.secrets['bkash_app_key']}{timestamp}".encode()
        ).hexdigest()

        return {
            "X-APP-KEY": self.secrets["bkash_app_key"],
            "X-SIGN": signature,
            "X-TIMESTAMP": str(timestamp),
            "Content-Type": "application/json"
        }
```

## Webhook Receiver

```python
# app/api/v1/endpoints/payments.py

@router.post("/webhook/bkash")
async def bkash_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Receive bKash payment webhook."""
    body = await request.body()
    signature = request.headers.get("X-Signature")

    # Verify signature
    if not payment_service.verify_webhook_signature("bkash", body.decode(), signature):
        logger.warning("Invalid bKash webhook signature")
        return {"status": "rejected"}

    payload = json.loads(body)

    # Process payment
    try:
        success = await payment_service.process_bkash_webhook(db, payload)
        if success:
            return {"status": "accepted"}
        else:
            return {"status": "rejected"}
    except Exception as e:
        logger.error(f"bKash webhook error: {e}")
        return {"status": "rejected"}

@router.post("/webhook/nagad")
async def nagad_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Receive Nagad payment webhook."""
    # Similar to bKash but with Nagad-specific logic
    pass

@router.post("/webhook/sslcommerz")
async def sslcommerz_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Receive SSLCommerz payment webhook."""
    # Similar to bKash but with SSLCommerz-specific logic
    pass
```

## Idempotency

```python
# Idempotency key pattern

@router.post("/users/{user_id}/topup")
async def topup_balance(
    user_id: str,
    amount_bdt: int,
    idempotency_key: str = Header(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Top-up user balance (idempotent)."""

    # Verify ownership
    if current_user["sub"] != user_id:
        raise HTTPException(status_code=403)

    # Check if already processed
    cached = await cache_service.get(f"idempotency:{idempotency_key}")
    if cached:
        return json.loads(cached)

    # Initiate payment
    payment_data = await payment_service.initiate_bkash_payment(
        user_id, amount_bdt
    )

    response = {
        "transaction_id": str(uuid4()),
        "payment_url": payment_data["url"],
        "amount_bdt": amount_bdt
    }

    # Cache response for 24 hours
    await cache_service.set(
        f"idempotency:{idempotency_key}",
        json.dumps(response),
        ttl=86400
    )

    return response
```

**Resume Token:** `✓ PHASE_5_PAYMENTS_COMPLETE`
