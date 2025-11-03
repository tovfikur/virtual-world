"""
Land model
Represents individual land parcels in the virtual world
"""

from sqlalchemy import Column, String, Integer, Float, Boolean, ForeignKey, DateTime, Index, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property
import uuid
import bcrypt
from enum import Enum as PyEnum
from datetime import datetime

from app.db.base import BaseModel


class Biome(str, PyEnum):
    """Biome type enumeration for land terrain."""
    OCEAN = "ocean"
    BEACH = "beach"
    PLAINS = "plains"
    FOREST = "forest"
    DESERT = "desert"
    MOUNTAIN = "mountain"
    SNOW = "snow"


class Land(BaseModel):
    """
    Land model representing purchasable virtual land parcels.

    Each land triangle has unique coordinates and belongs to one owner.
    Land can be fenced with passcode protection for privacy.

    Attributes:
        land_id: Unique UUID identifier
        owner_id: Reference to owning user
        x, y, z: 3D coordinates (z=0 for 2D world)
        biome: Terrain type (forest/desert/grassland/water/snow)
        elevation: Height value (0-1 normalized)
        color_hex: Hex color for rendering (#RRGGBB)
        fenced: Whether land has restricted access
        passcode_hash: Hashed 4-digit passcode for entry
        public_message: Message displayed to visitors
        price_base_bdt: Base price in Bangladeshi Taka
        for_sale: Whether land is currently listed
    """

    __tablename__ = "lands"

    __table_args__ = (
        Index("idx_lands_coordinates", "x", "y", "z", unique=True),
        Index("idx_lands_spatial", "x", "y", postgresql_using="brin"),
    )

    # Primary Key
    land_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False
    )

    # Ownership
    owner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=False,
        index=True
    )

    # Coordinates (unique per triangle)
    x = Column(Integer, nullable=False)
    y = Column(Integer, nullable=False)
    z = Column(Integer, default=0, nullable=False)

    # World Generation Data
    biome = Column(
        SQLEnum(Biome),
        nullable=False,
        index=True
    )
    elevation = Column(
        Float,
        default=0.5,
        nullable=False
    )
    color_hex = Column(
        String(7),
        nullable=False
    )

    # Access Control
    fenced = Column(
        Boolean,
        default=False,
        nullable=False
    )
    passcode_hash = Column(
        String(255),
        nullable=True
    )
    passcode_updated_at = Column(
        DateTime(timezone=True),
        nullable=True
    )

    # Content
    public_message = Column(
        String(500),
        nullable=True
    )

    # Pricing
    price_base_bdt = Column(
        Integer,
        default=1000,
        nullable=False
    )

    # Marketplace Status
    for_sale = Column(
        Boolean,
        default=False,
        nullable=False,
        index=True
    )

    # Relationships
    owner = relationship(
        "User",
        back_populates="lands",
        foreign_keys=[owner_id]
    )
    transactions = relationship(
        "Transaction",
        back_populates="land"
    )
    listings = relationship(
        "Listing",
        back_populates="land"
    )
    chat_sessions = relationship(
        "ChatSession",
        back_populates="land"
    )

    @validates("x", "y")
    def validate_coordinates(self, key: str, value: int) -> int:
        """Validate coordinates are non-negative."""
        if value < 0:
            raise ValueError(f"{key} must be non-negative")
        return value

    @validates("biome")
    def validate_biome(self, key: str, value: Biome) -> Biome:
        """Validate biome is valid enum value."""
        if not isinstance(value, Biome):
            raise ValueError(f"Invalid biome: {value}")
        return value

    @validates("elevation")
    def validate_elevation(self, key: str, value: float) -> float:
        """Validate elevation is between 0 and 1."""
        if not (0 <= value <= 1):
            raise ValueError("Elevation must be between 0 and 1")
        return value

    @validates("color_hex")
    def validate_color_hex(self, key: str, value: str) -> str:
        """Validate color is valid hex format."""
        if not value.startswith("#") or len(value) != 7:
            raise ValueError("Color must be in #RRGGBB format")
        return value

    def set_passcode(self, passcode: str) -> None:
        """
        Hash and set 4-digit access passcode.

        Args:
            passcode: 4-digit numeric string

        Raises:
            ValueError: If passcode is not exactly 4 digits

        Example:
            ```python
            land.set_passcode("1234")
            ```
        """
        if len(passcode) != 4 or not passcode.isdigit():
            raise ValueError("Passcode must be exactly 4 digits")

        salt = bcrypt.gensalt(rounds=8)  # Lower rounds for passcode
        self.passcode_hash = bcrypt.hashpw(
            passcode.encode('utf-8'),
            salt
        ).decode('utf-8')
        self.passcode_updated_at = datetime.utcnow()

    def verify_passcode(self, passcode: str) -> bool:
        """
        Verify passcode against stored hash.

        Args:
            passcode: 4-digit passcode to verify

        Returns:
            bool: True if passcode matches, False otherwise

        Example:
            ```python
            if land.verify_passcode("1234"):
                # Access granted
                pass
            ```
        """
        if not self.passcode_hash:
            return False

        try:
            return bcrypt.checkpw(
                passcode.encode('utf-8'),
                self.passcode_hash.encode('utf-8')
            )
        except Exception:
            return False

    @hybrid_property
    def is_accessible(self) -> bool:
        """
        Check if land is accessible without passcode.

        Returns:
            bool: True if not fenced, False if fenced
        """
        return not self.fenced

    def enable_fence(self, passcode: str) -> None:
        """
        Enable fence with passcode protection.

        Args:
            passcode: 4-digit passcode
        """
        self.fenced = True
        self.set_passcode(passcode)

    def disable_fence(self) -> None:
        """Remove fence and clear passcode."""
        self.fenced = False
        self.passcode_hash = None
        self.passcode_updated_at = None

    def __repr__(self) -> str:
        """String representation of Land."""
        return f"<Land ({self.x}, {self.y}) - {self.biome.value}>"

    def to_dict(self) -> dict:
        """
        Convert land to dictionary for API responses.

        Returns:
            dict: Land data dictionary
        """
        return {
            "land_id": str(self.land_id),
            "owner_id": str(self.owner_id),
            "coordinates": {"x": self.x, "y": self.y, "z": self.z},
            "biome": self.biome.value,
            "elevation": self.elevation,
            "color_hex": self.color_hex,
            "fenced": self.fenced,
            "passcode_required": self.passcode_hash is not None,
            "public_message": self.public_message,
            "price_base_bdt": self.price_base_bdt,
            "for_sale": self.for_sale,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
