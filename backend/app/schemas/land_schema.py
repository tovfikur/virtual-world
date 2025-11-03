"""
Land-related Pydantic schemas for request/response validation
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime


class LandResponse(BaseModel):
    """Schema for land response."""

    land_id: str
    owner_id: str
    coordinates: dict
    biome: str
    elevation: float
    color_hex: str
    fenced: bool
    passcode_required: bool
    public_message: Optional[str] = None
    price_base_bdt: int
    for_sale: bool
    created_at: datetime

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "land_id": "land-uuid-1234",
                "owner_id": "user-uuid-5678",
                "coordinates": {"x": 120, "y": 340, "z": 0},
                "biome": "forest",
                "elevation": 0.65,
                "color_hex": "#2d5016",
                "fenced": False,
                "passcode_required": False,
                "public_message": "Welcome to my forest!",
                "price_base_bdt": 1500,
                "for_sale": False,
                "created_at": "2025-01-15T10:20:30Z"
            }
        }


class LandUpdate(BaseModel):
    """Schema for updating land."""

    public_message: Optional[str] = Field(None, max_length=500)

    class Config:
        json_schema_extra = {
            "example": {
                "public_message": "Welcome to my land!"
            }
        }


class LandFence(BaseModel):
    """Schema for land fencing."""

    fenced: bool
    passcode: Optional[str] = Field(None, min_length=4, max_length=4)

    @field_validator('passcode')
    @classmethod
    def validate_passcode(cls, v: Optional[str], values) -> Optional[str]:
        """Validate passcode if fencing is enabled."""
        if v is not None and not v.isdigit():
            raise ValueError('Passcode must be 4 digits')
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "fenced": True,
                "passcode": "1234"
            }
        }


class LandTransfer(BaseModel):
    """Schema for land transfer."""

    new_owner_id: str
    message: Optional[str] = Field(None, max_length=200)

    class Config:
        json_schema_extra = {
            "example": {
                "new_owner_id": "user-uuid-9012",
                "message": "Gift for you!"
            }
        }


class LandSearch(BaseModel):
    """Schema for land search parameters."""

    biome: Optional[str] = None
    min_price_bdt: Optional[int] = Field(None, ge=0)
    max_price_bdt: Optional[int] = Field(None, ge=0)
    for_sale: Optional[bool] = None
    owner_id: Optional[str] = None
    x: Optional[int] = None
    y: Optional[int] = None
    radius: Optional[int] = Field(None, ge=1, le=100)
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)
    sort: str = Field(default="created_at_desc")

    @field_validator('sort')
    @classmethod
    def validate_sort(cls, v: str) -> str:
        """Validate sort parameter."""
        allowed = ["price_asc", "price_desc", "created_at_asc", "created_at_desc"]
        if v not in allowed:
            raise ValueError(f"Sort must be one of: {allowed}")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "biome": "forest",
                "min_price_bdt": 1000,
                "max_price_bdt": 5000,
                "for_sale": True,
                "page": 1,
                "limit": 20,
                "sort": "price_asc"
            }
        }
