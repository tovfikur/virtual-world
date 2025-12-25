"""
Listing Schemas
Pydantic models for marketplace listing requests/responses
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict
from datetime import datetime
from enum import Enum


class ListingType(str, Enum):
    """Listing type enum."""
    AUCTION = "auction"
    FIXED_PRICE = "fixed_price"
    AUCTION_WITH_BUYNOW = "auction_with_buynow"


class ListingStatus(str, Enum):
    """Listing status enum."""
    ACTIVE = "active"
    SOLD = "sold"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class ListingCreate(BaseModel):
    """Schema for creating a new parcel listing."""
    land_ids: List[str] = Field(..., description="List of land UUIDs in parcel (must be connected)")
    listing_type: ListingType = Field(..., description="Type of listing")
    starting_price_bdt: Optional[int] = Field(
        None,
        ge=1,
        description="Starting price for auction (required for auctions, for entire parcel)"
    )
    reserve_price_bdt: Optional[int] = Field(
        None,
        ge=1,
        description="Minimum acceptable price for auction (for entire parcel)"
    )
    buy_now_price_bdt: Optional[int] = Field(
        None,
        ge=1,
        description="Buy now price (required for fixed_price and auction_with_buynow, for entire parcel)"
    )
    duration_hours: Optional[int] = Field(
        None,
        ge=1,
        le=168,  # Max 7 days
        description="Auction duration in hours (required for auctions)"
    )
    auto_extend_minutes: Optional[int] = Field(
        5,
        ge=0,
        le=60,
        description="Auto-extend auction by X minutes on late bids"
    )

    @validator("land_ids")
    def validate_land_ids(cls, v):
        """Validate land_ids list."""
        if not v or len(v) == 0:
            raise ValueError("At least one land required")
        if len(v) > 1000:  # Prevent abuse
            raise ValueError("Maximum 1000 lands per parcel")
        return v

    @validator("starting_price_bdt")
    def validate_starting_price(cls, v, values):
        """Validate starting price for auctions."""
        listing_type = values.get("listing_type")
        if listing_type in [ListingType.AUCTION, ListingType.AUCTION_WITH_BUYNOW]:
            if v is None:
                raise ValueError("starting_price_bdt required for auctions")
        return v

    @validator("buy_now_price_bdt")
    def validate_buy_now_price(cls, v, values):
        """Validate buy now price."""
        listing_type = values.get("listing_type")
        if listing_type in [ListingType.FIXED_PRICE, ListingType.AUCTION_WITH_BUYNOW]:
            if v is None:
                raise ValueError("buy_now_price_bdt required for this listing type")
        return v

    @validator("duration_hours")
    def validate_duration(cls, v, values):
        """Validate duration for auctions."""
        listing_type = values.get("listing_type")
        if listing_type in [ListingType.AUCTION, ListingType.AUCTION_WITH_BUYNOW]:
            if v is None:
                raise ValueError("duration_hours required for auctions")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "land_ids": [
                    "123e4567-e89b-12d3-a456-426614174000",
                    "223e4567-e89b-12d3-a456-426614174000"
                ],
                "listing_type": "auction",
                "starting_price_bdt": 100,
                "reserve_price_bdt": 150,
                "buy_now_price_bdt": 200,
                "duration_hours": 24,
                "auto_extend_minutes": 5
            }
        }


class ListingResponse(BaseModel):
    """Schema for listing response (parcel)."""
    listing_id: str
    land_count: int
    seller_id: str
    seller_username: Optional[str] = None
    listing_type: str
    status: str
    starting_price_bdt: Optional[int]
    current_price_bdt: int
    reserve_price_bdt: Optional[int]
    buy_now_price_bdt: Optional[int]
    bid_count: int
    highest_bidder_id: Optional[str]
    ends_at: Optional[str]
    created_at: str
    updated_at: str

    # Parcel information
    lands: Optional[List[Dict]] = None  # List of land details
    bounding_box: Optional[Dict] = None  # min_x, max_x, min_y, max_y
    biomes: Optional[List[str]] = None  # Unique biomes in parcel

    class Config:
        from_attributes = True


class BidCreate(BaseModel):
    """Schema for placing a bid."""
    amount_bdt: int = Field(..., ge=1, description="Bid amount in BDT")

    class Config:
        json_schema_extra = {
            "example": {
                "amount_bdt": 150
            }
        }


class BidResponse(BaseModel):
    """Schema for bid response."""
    bid_id: str
    listing_id: str
    bidder_id: str
    bidder_username: Optional[str] = None
    amount_bdt: int
    status: str
    created_at: str

    class Config:
        from_attributes = True


class BuyNowRequest(BaseModel):
    """Schema for instant buy now purchase."""
    payment_method: str = Field(
        ...,
        pattern="^(balance|bkash|nagad|rocket|sslcommerz)$",
        description="Payment method"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "payment_method": "balance"
            }
        }


class ListingSearch(BaseModel):
    """Schema for searching listings."""
    status: Optional[str] = None
    listing_type: Optional[str] = None
    min_price_bdt: Optional[int] = Field(None, ge=0)
    max_price_bdt: Optional[int] = Field(None, ge=0)
    biome: Optional[str] = None
    seller_id: Optional[str] = None
    sort_by: str = Field(
        "created_at_desc",
        pattern="^(price_asc|price_desc|created_at_asc|created_at_desc|ending_soon)$"
    )
    page: int = Field(1, ge=1)
    limit: int = Field(20, ge=1, le=100)

    class Config:
        json_schema_extra = {
            "example": {
                "status": "active",
                "listing_type": "auction",
                "min_price_bdt": 50,
                "max_price_bdt": 500,
                "biome": "plains",
                "sort_by": "ending_soon",
                "page": 1,
                "limit": 20
            }
        }
