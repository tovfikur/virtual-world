"""
Payment Service
Handles payment gateway integrations (bKash, Nagad, Rocket, SSLCommerz)
"""

import hashlib
import hmac
import json
import httpx
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from uuid import uuid4
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.models.transaction import Transaction
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class PaymentGateway(str, Enum):
    """Supported payment gateways"""
    BKASH = "bkash"
    NAGAD = "nagad"
    ROCKET = "rocket"
    SSLCOMMERZ = "sslcommerz"
    BALANCE = "balance"  # Internal balance-based payment


class PaymentStatus(str, Enum):
    """Payment status"""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class PaymentService:
    """Handle payment gateway integration"""

    def __init__(self):
        self.bkash_base_url = settings.bkash_api_url
        self.nagad_base_url = settings.nagad_api_url
        self.rocket_base_url = settings.rocket_api_url
        self.sslcommerz_base_url = settings.sslcommerz_api_url

        # API credentials (from environment)
        self.bkash_app_key = settings.bkash_app_key
        self.bkash_app_secret = settings.bkash_app_secret
        self.nagad_merchant_id = settings.nagad_merchant_id
        self.nagad_merchant_key = settings.nagad_merchant_key
        self.rocket_merchant_id = settings.rocket_merchant_id
        self.rocket_secret_key = settings.rocket_secret_key
        self.sslcommerz_store_id = settings.sslcommerz_store_id
        self.sslcommerz_store_password = settings.sslcommerz_store_password

    def verify_webhook_signature(
        self,
        gateway: PaymentGateway,
        payload: str,
        signature: str
    ) -> bool:
        """
        Verify webhook signature from payment gateway

        Args:
            gateway: Payment gateway name
            payload: Raw webhook payload
            signature: Signature from webhook header

        Returns:
            True if signature is valid
        """
        try:
            if gateway == PaymentGateway.BKASH:
                secret = self.bkash_app_secret
            elif gateway == PaymentGateway.NAGAD:
                secret = self.nagad_merchant_key
            elif gateway == PaymentGateway.ROCKET:
                secret = self.rocket_secret_key
            elif gateway == PaymentGateway.SSLCOMMERZ:
                secret = self.sslcommerz_store_password
            else:
                logger.warning(f"Unknown gateway for signature verification: {gateway}")
                return False

            if not secret:
                logger.error(f"No secret configured for gateway: {gateway}")
                return False

            # Compute HMAC-SHA256 signature
            expected = hmac.new(
                secret.encode(),
                payload.encode(),
                hashlib.sha256
            ).hexdigest()

            return hmac.compare_digest(expected, signature)

        except Exception as e:
            logger.error(f"Error verifying webhook signature: {e}")
            return False

    async def initiate_bkash_payment(
        self,
        user_id: str,
        amount: int,
        reference_id: str
    ) -> Dict[str, Any]:
        """
        Initiate bKash payment

        Args:
            user_id: User ID
            amount: Amount in BDT
            reference_id: Unique reference ID (idempotency key)

        Returns:
            Payment initiation response with payment URL
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Get auth token first
                auth_response = await client.post(
                    f"{self.bkash_base_url}/token/grant",
                    json={
                        "app_key": self.bkash_app_key,
                        "app_secret": self.bkash_app_secret
                    }
                )
                auth_data = auth_response.json()
                access_token = auth_data.get("id_token")

                # Create payment
                payment_response = await client.post(
                    f"{self.bkash_base_url}/checkout/payment/create",
                    json={
                        "mode": "0011",
                        "amount": str(amount),
                        "currency": "BDT",
                        "intent": "sale",
                        "merchantInvoiceNumber": reference_id,
                        "payerReference": user_id,
                        "callbackURL": f"{settings.backend_url}/api/v1/payments/callback/bkash",
                    },
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "X-APP-Key": self.bkash_app_key,
                    }
                )

                payment_data = payment_response.json()

                if payment_data.get("statusCode") == "0000":
                    return {
                        "success": True,
                        "payment_id": payment_data["paymentID"],
                        "payment_url": payment_data["bkashURL"],
                        "reference_id": reference_id,
                        "amount": amount,
                        "gateway": PaymentGateway.BKASH
                    }
                else:
                    return {
                        "success": False,
                        "error": payment_data.get("statusMessage", "Payment initiation failed")
                    }

        except Exception as e:
            logger.error(f"bKash payment initiation error: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def process_bkash_webhook(
        self,
        db: AsyncSession,
        payload: Dict[str, Any]
    ) -> bool:
        """
        Process bKash payment webhook

        Args:
            db: Database session
            payload: Webhook payload

        Returns:
            True if processed successfully
        """
        try:
            payment_id = payload.get("paymentID")
            status = payload.get("transactionStatus")

            if status != "Completed":
                logger.info(f"bKash payment {payment_id} not completed: {status}")
                return False

            # Check idempotency - avoid duplicate processing
            stmt = select(Transaction).where(
                Transaction.gateway_transaction_id == payment_id
            )
            result = await db.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                logger.info(f"bKash payment {payment_id} already processed")
                return True

            # Extract data
            user_id = payload.get("payerReference")
            amount = int(float(payload.get("amount", 0)))
            reference_id = payload.get("merchantInvoiceNumber")

            # Update user balance
            stmt = select(User).where(User.user_id == user_id).with_for_update()
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                logger.error(f"User not found for bKash payment: {user_id}")
                return False

            user.balance_bdt += amount

            # Log transaction
            transaction = Transaction(
                transaction_id=str(uuid4()),
                land_id=None,
                seller_id=user_id,
                buyer_id=user_id,
                amount_bdt=amount,
                transaction_type="topup",
                gateway_name=PaymentGateway.BKASH,
                gateway_transaction_id=payment_id,
                status=PaymentStatus.COMPLETED,
                metadata=json.dumps({
                    "reference_id": reference_id,
                    "webhook_received_at": datetime.utcnow().isoformat()
                })
            )
            db.add(transaction)

            await db.commit()
            logger.info(f"bKash payment processed: {payment_id}, amount: {amount} BDT")
            return True

        except Exception as e:
            logger.error(f"Error processing bKash webhook: {e}")
            await db.rollback()
            return False

    async def initiate_nagad_payment(
        self,
        user_id: str,
        amount: int,
        reference_id: str
    ) -> Dict[str, Any]:
        """Initiate Nagad payment"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Nagad-specific implementation
                timestamp = int(datetime.utcnow().timestamp() * 1000)

                # Create signature
                signature_data = f"{self.nagad_merchant_id}{reference_id}{amount}{timestamp}"
                signature = hmac.new(
                    self.nagad_merchant_key.encode(),
                    signature_data.encode(),
                    hashlib.sha256
                ).hexdigest()

                response = await client.post(
                    f"{self.nagad_base_url}/payment/create",
                    json={
                        "merchantId": self.nagad_merchant_id,
                        "orderId": reference_id,
                        "amount": amount,
                        "currency": "BDT",
                        "challenge": signature,
                        "callbackURL": f"{settings.backend_url}/api/v1/payments/callback/nagad",
                    },
                    headers={
                        "X-KM-Api-Version": "v-0.2.0",
                        "X-KM-IP-V4": "127.0.0.1",
                        "X-KM-Client-Type": "PC_WEB"
                    }
                )

                data = response.json()

                if data.get("status") == "Success":
                    return {
                        "success": True,
                        "payment_url": data["callBackUrl"],
                        "reference_id": reference_id,
                        "amount": amount,
                        "gateway": PaymentGateway.NAGAD
                    }
                else:
                    return {"success": False, "error": "Nagad payment initiation failed"}

        except Exception as e:
            logger.error(f"Nagad payment error: {e}")
            return {"success": False, "error": str(e)}

    async def initiate_rocket_payment(
        self,
        user_id: str,
        amount: int,
        reference_id: str
    ) -> Dict[str, Any]:
        """Initiate Rocket payment"""
        try:
            # Rocket payment initiation (placeholder - actual API may differ)
            return {
                "success": True,
                "payment_url": f"{self.rocket_base_url}/pay?ref={reference_id}&amount={amount}",
                "reference_id": reference_id,
                "amount": amount,
                "gateway": PaymentGateway.ROCKET
            }
        except Exception as e:
            logger.error(f"Rocket payment error: {e}")
            return {"success": False, "error": str(e)}

    async def initiate_sslcommerz_payment(
        self,
        user_id: str,
        amount: int,
        reference_id: str,
        user_email: str,
        user_phone: str
    ) -> Dict[str, Any]:
        """Initiate SSLCommerz payment"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.sslcommerz_base_url}/gwprocess/v4/api.php",
                    data={
                        "store_id": self.sslcommerz_store_id,
                        "store_passwd": self.sslcommerz_store_password,
                        "total_amount": amount,
                        "currency": "BDT",
                        "tran_id": reference_id,
                        "success_url": f"{settings.backend_url}/api/v1/payments/callback/sslcommerz/success",
                        "fail_url": f"{settings.backend_url}/api/v1/payments/callback/sslcommerz/fail",
                        "cancel_url": f"{settings.backend_url}/api/v1/payments/callback/sslcommerz/cancel",
                        "cus_email": user_email,
                        "cus_phone": user_phone,
                        "cus_name": user_id,
                        "product_name": "Virtual Land Credit",
                        "product_category": "Digital",
                        "product_profile": "general",
                        "shipping_method": "NO",
                    }
                )

                data = response.json()

                if data.get("status") == "SUCCESS":
                    return {
                        "success": True,
                        "payment_url": data["GatewayPageURL"],
                        "reference_id": reference_id,
                        "amount": amount,
                        "gateway": PaymentGateway.SSLCOMMERZ
                    }
                else:
                    return {"success": False, "error": "SSLCommerz payment initiation failed"}

        except Exception as e:
            logger.error(f"SSLCommerz payment error: {e}")
            return {"success": False, "error": str(e)}

    async def process_generic_webhook(
        self,
        db: AsyncSession,
        gateway: PaymentGateway,
        payload: Dict[str, Any],
        payment_id: str,
        user_id: str,
        amount: int,
        status: str
    ) -> bool:
        """
        Generic webhook processor for Nagad, Rocket, SSLCommerz
        """
        try:
            if status.lower() not in ["success", "completed", "valid"]:
                logger.info(f"{gateway} payment {payment_id} not successful: {status}")
                return False

            # Check idempotency
            stmt = select(Transaction).where(
                Transaction.gateway_transaction_id == payment_id
            )
            result = await db.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                logger.info(f"{gateway} payment {payment_id} already processed")
                return True

            # Update user balance
            stmt = select(User).where(User.user_id == user_id).with_for_update()
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                logger.error(f"User not found for {gateway} payment: {user_id}")
                return False

            user.balance_bdt += amount

            # Log transaction
            transaction = Transaction(
                transaction_id=str(uuid4()),
                land_id=None,
                seller_id=user_id,
                buyer_id=user_id,
                amount_bdt=amount,
                transaction_type="topup",
                gateway_name=gateway,
                gateway_transaction_id=payment_id,
                status=PaymentStatus.COMPLETED,
                metadata=json.dumps({
                    "webhook_received_at": datetime.utcnow().isoformat(),
                    "raw_payload": payload
                })
            )
            db.add(transaction)

            await db.commit()
            logger.info(f"{gateway} payment processed: {payment_id}, amount: {amount} BDT")
            return True

        except Exception as e:
            logger.error(f"Error processing {gateway} webhook: {e}")
            await db.rollback()
            return False


# Singleton instance
payment_service = PaymentService()
