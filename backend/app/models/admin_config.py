"""
Admin Config model
World generation and platform configuration
"""

from sqlalchemy import Column, Integer, Float, ForeignKey, CheckConstraint, Boolean, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.db.base import BaseModel


class AdminConfig(BaseModel):
    """
    Admin configuration for world generation and pricing.

    Only one record should exist (singleton pattern).
    Updated by admins to control world generation and economics.

    Attributes:
        config_id: Unique UUID identifier
        world_seed: Seed for deterministic world generation
        noise_frequency: OpenSimplex noise frequency
        noise_octaves: Number of noise layers
        noise_persistence: Amplitude falloff per octave
        noise_lacunarity: Frequency multiplier per octave
        biome_*_percent: Distribution percentages (must sum to 1.0)
        base_land_price_bdt: Base price per land triangle
        *_multiplier: Price multipliers per biome
        transaction_fee_percent: Platform commission percentage
        updated_by_id: Admin who last updated config
    """

    __tablename__ = "admin_config"

    __table_args__ = (
        CheckConstraint(
            "noise_octaves >= 1 AND noise_octaves <= 8",
            name="check_octaves_range"
        ),
        CheckConstraint(
            "noise_persistence > 0 AND noise_persistence < 1",
            name="check_persistence_range"
        ),
        CheckConstraint(
            "noise_lacunarity > 1",
            name="check_lacunarity_range"
        ),
        CheckConstraint(
            "biome_forest_percent + biome_grassland_percent + biome_water_percent + "
            "biome_desert_percent + biome_snow_percent = 1.0",
            name="check_biome_distribution_sum"
        ),
        CheckConstraint(
            "transaction_fee_percent >= 0 AND transaction_fee_percent <= 100",
            name="check_fee_percentage"
        ),
    )

    # Primary Key
    config_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False
    )

    # World Generation Parameters
    world_seed = Column(
        Integer,
        nullable=False,
        default=12345
    )

    # Noise Parameters (OpenSimplex)
    noise_frequency = Column(
        Float,
        default=0.05,
        nullable=False
    )
    noise_octaves = Column(
        Integer,
        default=6,
        nullable=False
    )
    noise_persistence = Column(
        Float,
        default=0.6,
        nullable=False
    )
    noise_lacunarity = Column(
        Float,
        default=2.0,
        nullable=False
    )

    # Biome Distribution (percentages, must sum to 1.0)
    biome_forest_percent = Column(
        Float,
        default=0.35,
        nullable=False
    )
    biome_grassland_percent = Column(
        Float,
        default=0.30,
        nullable=False
    )
    biome_water_percent = Column(
        Float,
        default=0.20,
        nullable=False
    )
    biome_desert_percent = Column(
        Float,
        default=0.10,
        nullable=False
    )
    biome_snow_percent = Column(
        Float,
        default=0.05,
        nullable=False
    )

    # Auth & Session
    login_max_attempts = Column(
        Integer,
        default=5,
        nullable=False,
        comment="Maximum failed login attempts before lockout"
    )
    lockout_duration_minutes = Column(
        Integer,
        default=15,
        nullable=False,
        comment="Account lockout duration in minutes after max failed attempts"
    )
    max_sessions_per_user = Column(
        Integer,
        default=1,
        nullable=False,
        comment="Maximum concurrent sessions allowed per user"
    )

    # Pricing Configuration
    base_land_price_bdt = Column(
        Integer,
        default=1000,
        nullable=False
    )
    elevation_price_min_factor = Column(
        Float,
        default=0.8,
        nullable=False,
        comment="Minimum elevation price factor (elevation=0)"
    )
    elevation_price_max_factor = Column(
        Float,
        default=1.2,
        nullable=False,
        comment="Maximum elevation price factor (elevation=1)"
    )
    forest_multiplier = Column(
        Float,
        default=1.0,
        nullable=False
    )
    grassland_multiplier = Column(
        Float,
        default=0.8,
        nullable=False
    )
    water_multiplier = Column(
        Float,
        default=1.2,
        nullable=False
    )
    desert_multiplier = Column(
        Float,
        default=0.7,
        nullable=False
    )
    snow_multiplier = Column(
        Float,
        default=1.5,
        nullable=False
    )

    # Price Formula Controls
    land_pricing_formula = Column(
        String(32),
        default="dynamic",
        nullable=False,
        comment="Pricing formula type: dynamic (algorithmic) or fixed (flat rate)"
    )
    fixed_land_price_bdt = Column(
        Integer,
        default=1000,
        nullable=False,
        comment="Fixed price per land when formula=fixed"
    )
    dynamic_pricing_biome_influence = Column(
        Float,
        default=1.0,
        nullable=False,
        comment="Multiplier for biome influence on dynamic pricing (0=ignore biomes)"
    )
    dynamic_pricing_elevation_influence = Column(
        Float,
        default=1.0,
        nullable=False,
        comment="Multiplier for elevation influence on dynamic pricing (0=flat elevation)"
    )

    # Fencing Cost Controls
    fencing_enabled = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="Enable/disable land fencing feature"
    )
    fencing_cost_per_unit = Column(
        Integer,
        default=100,
        nullable=False,
        comment="Cost in BDT per unit perimeter for fencing"
    )
    fencing_maintenance_cost_percent = Column(
        Float,
        default=5.0,
        nullable=False,
        comment="Annual maintenance cost as % of fencing installation cost"
    )
    fencing_durability_years = Column(
        Integer,
        default=10,
        nullable=False,
        comment="Expected lifetime of fence before replacement needed"
    )

    # Parcel Rules
    parcel_connectivity_required = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="Require purchased lands to be connected/adjacent"
    )
    parcel_diagonal_allowed = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Allow diagonal adjacency for connectivity"
    )
    parcel_min_size = Column(
        Integer,
        default=1,
        nullable=False,
        comment="Minimum parcel size (number of lands)"
    )
    parcel_max_size = Column(
        Integer,
        default=1000,
        nullable=False,
        comment="Maximum parcel size (number of lands)"
    )

    # Ownership Limits
    max_lands_per_user = Column(
        Integer,
        default=10000,
        nullable=False,
        comment="Maximum total lands one user can own"
    )
    max_lands_per_biome_per_user = Column(
        Integer,
        default=2000,
        nullable=False,
        comment="Maximum lands per biome type per user"
    )
    max_contiguous_lands = Column(
        Integer,
        default=500,
        nullable=False,
        comment="Maximum size of single contiguous land parcel"
    )
    ownership_cooldown_minutes = Column(
        Integer,
        default=0,
        nullable=False,
        comment="Cooldown between land purchases (0=disabled)"
    )

    # Exploration Incentives
    exploration_first_discover_enabled = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="Enable bonus rewards for first discovery of new chunks"
    )
    exploration_first_discover_bonus_bdt = Column(
        Integer,
        default=50,
        nullable=False,
        comment="BDT reward for first chunk discovery"
    )
    exploration_rare_land_spawn_rate = Column(
        Float,
        default=0.01,
        nullable=False,
        comment="Chance (0-1) for rare/special land to spawn in unexplored chunks"
    )
    exploration_rare_land_bonus_multiplier = Column(
        Float,
        default=2.0,
        nullable=False,
        comment="Price multiplier for rare lands (2.0 = 2x base price)"
    )

    # Fraud Enforcement Controls
    wash_trading_enforcement_enabled = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="If true, enforce wash trading detection by blocking flagged transactions"
    )
    related_account_enforcement_enabled = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="If true, enforce related account linkage detection by blocking suspicious transfers"
    )
    price_deviation_auto_reject_enabled = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="If true, auto-reject listings/transactions exceeding price deviation threshold"
    )
    fraud_temp_suspend_minutes = Column(
        Integer,
        default=0,
        nullable=False,
        comment="If >0, temporarily suspend users involved in enforced fraud events for N minutes"
    )

    # Platform Fees
    transaction_fee_percent = Column(
        Float,
        default=5.0,
        nullable=False
    )
    # Marketplace Fee Tiers
    fee_tier_1_threshold = Column(
        Integer,
        default=10000,
        nullable=False,
        comment="Amount threshold (BDT) for tier 1"
    )
    fee_tier_1_percent = Column(
        Float,
        default=5.0,
        nullable=False,
        comment="Platform fee percent for amounts below tier 1 threshold"
    )
    fee_tier_2_threshold = Column(
        Integer,
        default=50000,
        nullable=False,
        comment="Amount threshold (BDT) for tier 2"
    )
    fee_tier_2_percent = Column(
        Float,
        default=3.5,
        nullable=False,
        comment="Platform fee percent for amounts between tier 1 and tier 2"
    )
    fee_tier_3_threshold = Column(
        Integer,
        default=100000,
        nullable=False,
        comment="Amount threshold (BDT) for tier 3"
    )
    fee_tier_3_percent = Column(
        Float,
        default=2.0,
        nullable=False,
        comment="Platform fee percent for amounts above tier 2"
    )
    listing_creation_fee_bdt = Column(
        Integer,
        default=0,
        nullable=False,
        comment="Fee charged when creating a listing"
    )
    premium_listing_fee_bdt = Column(
        Integer,
        default=0,
        nullable=False,
        comment="Fee for premium/promoted listing placement"
    )
    success_fee_mode = Column(
        String(16),
        default="percent",
        nullable=False,
        comment="Success fee mode: percent or flat"
    )
    success_fee_percent = Column(
        Float,
        default=2.0,
        nullable=False,
        comment="Success fee percent when mode=percent"
    )
    success_fee_flat_bdt = Column(
        Integer,
        default=0,
        nullable=False,
        comment="Success fee flat amount when mode=flat"
    )
    max_price_deviation_percent = Column(
        Float,
        default=25.0,
        nullable=False,
        comment="Max allowed price deviation vs reference before flag"
    )
    parcel_size_limit = Column(
        Integer,
        default=0,
        nullable=False,
        comment="Maximum parcel size allowed (0=unlimited)"
    )
    biome_trade_fee_percent = Column(
        Float,
        default=2.0,
        nullable=False,
        comment="Platform fee for biome share trading (separate from marketplace)"
    )

    # Biome Market Controls
    max_price_move_percent = Column(
        Float,
        default=5.0,
        nullable=False,
        comment="Maximum price movement per redistribution cycle"
    )
    max_transaction_percent = Column(
        Float,
        default=10.0,
        nullable=False,
        comment="Maximum single transaction as % of market cap"
    )
    redistribution_pool_percent = Column(
        Float,
        default=25.0,
        nullable=False,
        comment="Percentage of total market cash to redistribute"
    )
    biome_trading_paused = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Emergency pause for all biome trading"
    )
    biome_prices_frozen = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Freeze biome prices (no redistribution)"
    )

    # Biome Market Initialization (per-biome starting state)
    biome_initial_cash_bdt = Column(
        Integer,
        default=10000,
        nullable=False,
        comment="Initial market cash (BDT) per biome market initialization"
    )
    biome_initial_shares_outstanding = Column(
        Integer,
        default=1000,
        nullable=False,
        comment="Initial shares outstanding per biome on market init"
    )
    biome_initial_share_price_bdt = Column(
        Float,
        default=10.0,
        nullable=False,
        comment="Initial share price (BDT) at market initialization"
    )
    biome_price_update_frequency_seconds = Column(
        Integer,
        default=300,
        nullable=False,
        comment="Frequency of price updates via redistribution (seconds)"
    )
    attention_weight_algorithm_version = Column(
        String(32),
        default="v1_uniform",
        nullable=False,
        comment="Attention-weight algorithm version (v1_uniform, v1_volume_weighted, etc)"
    )

    # Attention-Weight Algorithm Parameters
    attention_weight_recency_decay = Column(
        Float,
        default=0.95,
        nullable=False,
        comment="Decay factor for recency in attention weight (0-1, higher=less decay)"
    )
    attention_weight_volume_factor = Column(
        Float,
        default=0.5,
        nullable=False,
        comment="Weight factor for transaction volume in attention calculation (0-1)"
    )
    attention_weight_momentum_threshold = Column(
        Float,
        default=1.05,
        nullable=False,
        comment="Price momentum threshold for attention boost (> 1.0 = upward momentum)"
    )
    attention_weight_volatility_window_minutes = Column(
        Integer,
        default=60,
        nullable=False,
        comment="Time window for calculating volatility (minutes)"
    )
    attention_weight_update_interval_seconds = Column(
        Integer,
        default=30,
        nullable=False,
        comment="Frequency of attention weight recalculation (seconds)"
    )

    # Biome Land Base Prices (BDT per land)
    plains_base_price = Column(
        Float,
        default=125.0,
        nullable=False,
        comment="Base price for plains biome land"
    )
    forest_base_price = Column(
        Float,
        default=100.0,
        nullable=False,
        comment="Base price for forest biome land"
    )
    beach_base_price = Column(
        Float,
        default=90.0,
        nullable=False,
        comment="Base price for beach biome land"
    )
    mountain_base_price = Column(
        Float,
        default=80.0,
        nullable=False,
        comment="Base price for mountain biome land"
    )
    desert_base_price = Column(
        Float,
        default=55.0,
        nullable=False,
        comment="Base price for desert biome land"
    )
    snow_base_price = Column(
        Float,
        default=45.0,
        nullable=False,
        comment="Base price for snow biome land"
    )
    ocean_base_price = Column(
        Float,
        default=30.0,
        nullable=False,
        comment="Base price for ocean biome land"
    )

    # Feature Toggles
    enable_land_trading = Column(
        Boolean,
        default=True,
        nullable=False
    )
    enable_chat = Column(
        Boolean,
        default=True,
        nullable=False
    )
    enable_registration = Column(
        Boolean,
        default=True,
        nullable=False
    )
    maintenance_mode = Column(
        Boolean,
        default=False,
        nullable=False
    )

    # System Limits
    max_lands_per_user = Column(
        Integer,
        nullable=True
    )
    max_listings_per_user = Column(
        Integer,
        default=10,
        nullable=False
    )
    max_lands_per_listing = Column(
        Integer,
        default=50,
        nullable=False,
        comment="Maximum number of land tiles allowed per listing"
    )
    max_listing_duration_days = Column(
        Integer,
        default=30,
        nullable=False,
        comment="Maximum listing duration for auctions in days"
    )
    listing_cooldown_minutes = Column(
        Integer,
        default=5,
        nullable=False,
        comment="Cooldown between listings per seller"
    )
    min_reserve_price_percent = Column(
        Integer,
        default=50,
        nullable=False,
        comment="Minimum reserve price as percent of starting price"
    )
    # Auction Anti-Sniping
    anti_sniping_enabled = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="Enable anti-sniping auto-extend near auction end"
    )
    anti_sniping_extend_minutes = Column(
        Integer,
        default=5,
        nullable=False,
        comment="Minutes to extend when anti-sniping triggers"
    )
    anti_sniping_threshold_minutes = Column(
        Integer,
        default=3,
        nullable=False,
        comment="If time remaining is below this threshold, extend"
    )
    # Payment Gateway Toggles & Limits
    enable_bkash = Column(
        Boolean,
        default=True,
        nullable=False
    )
    enable_nagad = Column(
        Boolean,
        default=True,
        nullable=False
    )
    enable_rocket = Column(
        Boolean,
        default=False,
        nullable=False
    )
    enable_sslcommerz = Column(
        Boolean,
        default=True,
        nullable=False
    )
    bkash_mode = Column(
        String(10),
        default="test",
        nullable=False
    )
    nagad_mode = Column(
        String(10),
        default="test",
        nullable=False
    )
    rocket_mode = Column(
        String(10),
        default="test",
        nullable=False
    )
    sslcommerz_mode = Column(
        String(10),
        default="test",
        nullable=False
    )
    topup_min_bdt = Column(
        Integer,
        default=100,
        nullable=False
    )
    topup_max_bdt = Column(
        Integer,
        default=100000,
        nullable=False
    )
    topup_daily_limit_bdt = Column(
        Integer,
        default=200000,
        nullable=False
    )
    topup_monthly_limit_bdt = Column(
        Integer,
        default=1000000,
        nullable=False
    )
    enable_email = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Enable outbound email system"
    )
    smtp_host = Column(
        String(255),
        nullable=True,
        comment="SMTP server host"
    )
    smtp_port = Column(
        Integer,
        default=587,
        nullable=False,
        comment="SMTP server port"
    )
    smtp_username = Column(
        String(255),
        nullable=True,
        comment="SMTP username"
    )
    smtp_password = Column(
        String(255),
        nullable=True,
        comment="SMTP password (stored hashed or encrypted externally)"
    )
    smtp_use_tls = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="Use STARTTLS"
    )
    smtp_use_ssl = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Use SSL/TLS socket"
    )
    default_from_email = Column(
        String(255),
        nullable=True,
        comment="Default From email address"
    )
    email_rate_limit_per_hour = Column(
        Integer,
        default=200,
        nullable=False,
        comment="Max emails per user per hour"
    )
    email_template_theme = Column(
        String(64),
        default="default",
        nullable=False,
        comment="Email template theme identifier"
    )
    enable_push_notifications = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Enable push notifications"
    )
    push_system_enabled = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="Enable system/transactional push notifications"
    )
    push_marketing_enabled = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Enable marketing/promotional push notifications"
    )
    push_daily_limit = Column(
        Integer,
        default=50,
        nullable=False,
        comment="Max push notifications per user per day"
    )
    push_quiet_hours_start = Column(
        Integer,
        default=0,
        nullable=False,
        comment="Quiet hours start (0-23)"
    )
    push_quiet_hours_end = Column(
        Integer,
        default=0,
        nullable=False,
        comment="Quiet hours end (0-23)"
    )
    push_webhook_url = Column(
        String(512),
        nullable=True,
        comment="Webhook/endpoint for push notification provider"
    )
    chat_max_length = Column(
        Integer,
        default=500,
        nullable=False,
        comment="Maximum chat message length"
    )
    chat_profanity_filter_enabled = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Enable profanity filtering"
    )
    chat_block_keywords = Column(
        String(1024),
        nullable=True,
        comment="Comma-separated keywords to block"
    )
    chat_retention_days = Column(
        Integer,
        default=30,
        nullable=False,
        comment="Retention period for chat messages"
    )
    chat_pm_enabled = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="Allow private messages"
    )
    chat_group_max_members = Column(
        Integer,
        default=50,
        nullable=False,
        comment="Maximum members in a chat group"
    )
    announcement_allow_high_priority = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Allow high-priority announcements"
    )
    announcement_max_priority = Column(
        Integer,
        default=3,
        nullable=False,
        comment="Max priority level allowed (numeric)"
    )
    announcement_rate_limit_per_hour = Column(
        Integer,
        default=20,
        nullable=False,
        comment="Max announcements per hour per admin"
    )
    log_level = Column(
        String(20),
        default="INFO",
        nullable=False,
        comment="Global application log level"
    )
    log_retention_days = Column(
        Integer,
        default=30,
        nullable=False,
        comment="Desired log retention in days (policy indicator)"
    )
    chunk_cache_ttl_seconds = Column(
        Integer,
        default=3600,
        nullable=False,
        comment="TTL for chunk cache entries"
    )
    payment_alert_window_minutes = Column(
        Integer,
        default=60,
        nullable=False,
        comment="Time window (minutes) for evaluating payment alerts"
    )
    payment_alert_failure_threshold = Column(
        Integer,
        default=3,
        nullable=False,
        comment="Number of failed/errored webhooks in window to trigger alert"
    )
    payment_reconcile_tolerance = Column(
        Integer,
        default=0,
        nullable=False,
        comment="Allowed delta between success events and recorded top-ups in window"
    )
    # Rate Limiting Controls
    api_requests_per_minute = Column(
        Integer,
        default=120,
        nullable=False,
        comment="General API requests per minute per user"
    )
    marketplace_actions_per_hour = Column(
        Integer,
        default=200,
        nullable=False,
        comment="Marketplace actions (create listing/bid/buy) per hour per user"
    )
    chat_messages_per_minute = Column(
        Integer,
        default=60,
        nullable=False,
        comment="Chat messages per minute per user"
    )
    biome_trades_per_minute = Column(
        Integer,
        default=120,
        nullable=False,
        comment="Biome trade operations per minute per user"
    )

    # Fraud Detection Thresholds
    wash_trading_min_trades_window = Column(
        Integer,
        default=10,
        nullable=False,
        comment="Minimum trades in 24h window to trigger wash trading flag"
    )
    wash_trading_min_volume_percent = Column(
        Float,
        default=30.0,
        nullable=False,
        comment="Min percent of trades back-and-forth (sell then buy same biome within 1h)"
    )
    related_account_min_transactions = Column(
        Integer,
        default=5,
        nullable=False,
        comment="Min transactions between accounts to flag as related"
    )
    related_account_max_price_variance_percent = Column(
        Float,
        default=2.0,
        nullable=False,
        comment="Max price variance in related account transactions to trigger flag"
    )
    price_deviation_auto_reject_percent = Column(
        Float,
        default=50.0,
        nullable=False,
        comment="Price deviation % threshold for auto-reject transaction (0 to disable)"
    )

    # Market Manipulation Detection Thresholds
    market_spike_threshold_percent = Column(
        Float,
        default=30.0,
        nullable=False,
        comment="Price spike % threshold to trigger manipulation alert"
    )
    market_spike_window_seconds = Column(
        Integer,
        default=300,
        nullable=False,
        comment="Time window for detecting sudden price spikes (seconds)"
    )
    order_clustering_threshold = Column(
        Integer,
        default=5,
        nullable=False,
        comment="Number of orders within clustering time window to trigger alert"
    )
    order_clustering_window_seconds = Column(
        Integer,
        default=60,
        nullable=False,
        comment="Time window for order clustering detection (seconds)"
    )
    pump_and_dump_price_increase_percent = Column(
        Float,
        default=50.0,
        nullable=False,
        comment="Price increase % threshold for pump-and-dump pattern detection"
    )
    pump_and_dump_volume_window_minutes = Column(
        Integer,
        default=30,
        nullable=False,
        comment="Time window for analyzing volume in pump-and-dump patterns (minutes)"
    )
    manipulation_alert_auto_freeze = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Auto-freeze market when manipulation detected (requires manual review)"
    )
    manipulation_alert_severity_threshold = Column(
        String(16),
        default="high",
        nullable=False,
        comment="Alert severity level to trigger action (low, medium, high, critical)"
    )

    # Emergency Market Reset Controls
    market_emergency_reset_enabled = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="Enable emergency market reset functionality"
    )
    market_reset_clear_all_orders = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="Clear all pending orders during emergency reset"
    )
    market_reset_reset_prices = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="Reset all prices to initialization values during reset"
    )
    market_reset_clear_volatility_history = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="Clear price volatility history to reset momentum tracking"
    )
    market_reset_redistribute_wealth = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Redistribute wealth to Gini coefficient target (advanced, rarely used)"
    )
    market_reset_redistribution_gini_target = Column(
        Float,
        default=0.3,
        nullable=False,
        comment="Target Gini coefficient for wealth redistribution (0=perfect equality, 1=max inequality)"
    )
    market_reset_require_confirmation = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="Require two-factor confirmation from multiple admins"
    )
    market_reset_cooldown_minutes = Column(
        Integer,
        default=120,
        nullable=False,
        comment="Minimum cooldown between emergency resets (minutes)"
    )

    access_token_expire_minutes = Column(
        Integer,
        default=60,
        nullable=False,
        comment="Access token expiry in minutes"
    )
    refresh_token_expire_days = Column(
        Integer,
        default=7,
        nullable=False,
        comment="Refresh token expiry in days"
    )
    password_min_length = Column(
        Integer,
        default=12,
        nullable=False,
        comment="Minimum password length"
    )
    password_require_uppercase = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="Password must include an uppercase letter"
    )
    password_require_lowercase = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="Password must include a lowercase letter"
    )
    password_require_number = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="Password must include a number"
    )
    password_require_special = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="Password must include a special character"
    )
    gateway_fee_mode = Column(
        String(16),
        default="absorb",
        nullable=False,
        comment="How gateway fees are handled: absorb or pass_through"
    )
    gateway_fee_percent = Column(
        Float,
        default=1.5,
        nullable=False,
        comment="Percent fee applied by gateway"
    )
    gateway_fee_flat_bdt = Column(
        Integer,
        default=0,
        nullable=False,
        comment="Flat fee in BDT applied by gateway"
    )
    # Auction Duration Limits
    auction_min_duration_hours = Column(
        Integer,
        default=1,
        nullable=False,
        comment="Minimum allowed auction duration in hours"
    )
    auction_max_duration_hours = Column(
        Integer,
        default=168,
        nullable=False,
        comment="Maximum allowed auction duration in hours (7 days)"
    )
    auction_bid_increment = Column(
        Integer,
        default=100,
        nullable=False
    )
    auction_extend_minutes = Column(
        Integer,
        default=5,
        nullable=False
    )
    max_land_price_bdt = Column(
        Integer,
        nullable=True
    )
    min_land_price_bdt = Column(
        Integer,
        nullable=True
    )

    # Land Allocation Settings (for new users)
    starter_land_enabled = Column(
        Boolean,
        default=True,
        nullable=False
    )
    starter_land_min_size = Column(
        Integer,
        default=36,
        nullable=False
    )
    starter_land_max_size = Column(
        Integer,
        default=1000,
        nullable=False
    )
    starter_land_buffer_units = Column(
        Integer,
        default=1,
        nullable=False
    )
    starter_shape_variation_enabled = Column(
        Boolean,
        default=True,
        nullable=False
    )

    # Meta
    updated_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=False
    )

    # Relationship
    updated_by = relationship(
        "User",
        foreign_keys=[updated_by_id]
    )

    def get_biome_multiplier(self, biome: str) -> float:
        """
            "chat": {
                "max_length": self.chat_max_length,
                "profanity_filter_enabled": self.chat_profanity_filter_enabled,
                "block_keywords": self.chat_block_keywords,
                "retention_days": self.chat_retention_days,
                "pm_enabled": self.chat_pm_enabled,
                "group_max_members": self.chat_group_max_members,
            },
            "announcements": {
                "allow_high_priority": self.announcement_allow_high_priority,
                "max_priority": self.announcement_max_priority,
                "rate_limit_per_hour": self.announcement_rate_limit_per_hour,
            },
        Get price multiplier for a biome.

        Args:
            biome: Biome name (forest/desert/grassland/water/snow)

        Returns:
            float: Price multiplier

        Example:
            ```python
            multiplier = config.get_biome_multiplier("forest")
            price = base_price * multiplier
            ```
        """
        multipliers = {
            "forest": self.forest_multiplier,
            "desert": self.desert_multiplier,
            "grassland": self.grassland_multiplier,
            "water": self.water_multiplier,
            "snow": self.snow_multiplier
        }
        return multipliers.get(biome, 1.0)

    def calculate_land_price(self, biome: str) -> int:
        """
        Calculate land price based on biome.

        Args:
            biome: Biome name

        Returns:
            int: Calculated price in BDT
        """
        multiplier = self.get_biome_multiplier(biome)
        return int(self.base_land_price_bdt * multiplier)

    def __repr__(self) -> str:
        """String representation of AdminConfig."""
        return f"<AdminConfig {self.config_id} - Seed {self.world_seed}>"

    def to_dict(self) -> dict:
        """
        Convert config to dictionary for API responses.

        Returns:
            dict: Config data dictionary
        """
        return {
            "config_id": str(self.config_id),
            "world_seed": self.world_seed,
            "noise_frequency": self.noise_frequency,
            "noise_octaves": self.noise_octaves,
            "noise_persistence": self.noise_persistence,
            "noise_lacunarity": self.noise_lacunarity,
            "biome_distribution": {
                "forest": self.biome_forest_percent,
                "grassland": self.biome_grassland_percent,
                "water": self.biome_water_percent,
                "desert": self.biome_desert_percent,
                "snow": self.biome_snow_percent
            },
            "base_land_price_bdt": self.base_land_price_bdt,
            "elevation_price_factor": {
                "min": self.elevation_price_min_factor,
                "max": self.elevation_price_max_factor
            },
            "biome_multipliers": {
                "forest": self.forest_multiplier,
                "grassland": self.grassland_multiplier,
                "water": self.water_multiplier,
                "desert": self.desert_multiplier,
                "snow": self.snow_multiplier
            },
            "transaction_fee_percent": self.transaction_fee_percent,
            "marketplace_fee_tiers": {
                "tier_1": {
                    "threshold_bdt": self.fee_tier_1_threshold,
                    "percent": self.fee_tier_1_percent
                },
                "tier_2": {
                    "threshold_bdt": self.fee_tier_2_threshold,
                    "percent": self.fee_tier_2_percent
                },
            "listing_fees": {
                "creation_bdt": self.listing_creation_fee_bdt,
                "premium_bdt": self.premium_listing_fee_bdt,
                "success_fee_mode": self.success_fee_mode,
                "success_fee_percent": self.success_fee_percent,
                "success_fee_flat_bdt": self.success_fee_flat_bdt,
            },
            "price_controls": {
                "max_price_deviation_percent": self.max_price_deviation_percent,
                "parcel_size_limit": self.parcel_size_limit,
            },
                "tier_3": {
                    "threshold_bdt": self.fee_tier_3_threshold,
                    "percent": self.fee_tier_3_percent
                }
            },
            "biome_trade_fee_percent": self.biome_trade_fee_percent,
            "biome_market_controls": {
                "max_price_move_percent": self.max_price_move_percent,
                "max_transaction_percent": self.max_transaction_percent,
                "redistribution_pool_percent": self.redistribution_pool_percent,
                "biome_trading_paused": self.biome_trading_paused,
                "biome_prices_frozen": self.biome_prices_frozen
            },
            "biome_market_initialization": {
                "initial_cash_bdt": self.biome_initial_cash_bdt,
                "initial_shares_outstanding": self.biome_initial_shares_outstanding,
                "initial_share_price_bdt": self.biome_initial_share_price_bdt,
                "price_update_frequency_seconds": self.biome_price_update_frequency_seconds,
                "attention_weight_algorithm_version": self.attention_weight_algorithm_version,
            },
            "attention_weight_algorithm": {
                "version": self.attention_weight_algorithm_version,
                "recency_decay": self.attention_weight_recency_decay,
                "volume_factor": self.attention_weight_volume_factor,
                "momentum_threshold": self.attention_weight_momentum_threshold,
                "volatility_window_minutes": self.attention_weight_volatility_window_minutes,
                "update_interval_seconds": self.attention_weight_update_interval_seconds,
            },
            "biome_land_base_prices": {
                "plains": self.plains_base_price,
                "forest": self.forest_base_price,
                "beach": self.beach_base_price,
                "mountain": self.mountain_base_price,
                "desert": self.desert_base_price,
                "snow": self.snow_base_price,
                "ocean": self.ocean_base_price
            },
            "auction_limits": {
                "min_duration_hours": self.auction_min_duration_hours,
                "max_duration_hours": self.auction_max_duration_hours
            },
            "rate_limits": {
                "api_requests_per_minute": self.api_requests_per_minute,
                "marketplace_actions_per_hour": self.marketplace_actions_per_hour,
                "chat_messages_per_minute": self.chat_messages_per_minute,
                "biome_trades_per_minute": self.biome_trades_per_minute
            },
            "fraud_detection": {
                "wash_trading_min_trades_window": self.wash_trading_min_trades_window,
                "wash_trading_min_volume_percent": self.wash_trading_min_volume_percent,
                "related_account_min_transactions": self.related_account_min_transactions,
                "related_account_max_price_variance_percent": self.related_account_max_price_variance_percent,
                "price_deviation_auto_reject_percent": self.price_deviation_auto_reject_percent,
            },
            "market_manipulation_detection": {
                "spike_threshold_percent": self.market_spike_threshold_percent,
                "spike_window_seconds": self.market_spike_window_seconds,
                "order_clustering_threshold": self.order_clustering_threshold,
                "order_clustering_window_seconds": self.order_clustering_window_seconds,
                "pump_and_dump_price_increase_percent": self.pump_and_dump_price_increase_percent,
                "pump_and_dump_volume_window_minutes": self.pump_and_dump_volume_window_minutes,
                "alert_auto_freeze": self.manipulation_alert_auto_freeze,
                "alert_severity_threshold": self.manipulation_alert_severity_threshold,
            },
            "market_emergency_reset": {
                "enabled": self.market_emergency_reset_enabled,
                "clear_all_orders": self.market_reset_clear_all_orders,
                "reset_prices": self.market_reset_reset_prices,
                "clear_volatility_history": self.market_reset_clear_volatility_history,
                "redistribute_wealth": self.market_reset_redistribute_wealth,
                "redistribution_gini_target": self.market_reset_redistribution_gini_target,
                "require_confirmation": self.market_reset_require_confirmation,
                "cooldown_minutes": self.market_reset_cooldown_minutes,
            },
            "fraud_enforcement": {
                "wash_trading_enforcement_enabled": self.wash_trading_enforcement_enabled,
                "related_account_enforcement_enabled": self.related_account_enforcement_enabled,
                "price_deviation_auto_reject_enabled": self.price_deviation_auto_reject_enabled,
                "fraud_temp_suspend_minutes": self.fraud_temp_suspend_minutes,
            },
            "land_pricing_formula": {
                "formula": self.land_pricing_formula,
                "fixed_price_bdt": self.fixed_land_price_bdt,
                "dynamic_biome_influence": self.dynamic_pricing_biome_influence,
                "dynamic_elevation_influence": self.dynamic_pricing_elevation_influence,
            },
            "fencing": {
                "enabled": self.fencing_enabled,
                "cost_per_unit_bdt": self.fencing_cost_per_unit,
                "maintenance_cost_percent": self.fencing_maintenance_cost_percent,
                "durability_years": self.fencing_durability_years,
            },
            "parcel_rules": {
                "connectivity_required": self.parcel_connectivity_required,
                "diagonal_allowed": self.parcel_diagonal_allowed,
                "min_size": self.parcel_min_size,
                "max_size": self.parcel_max_size,
            },
            "ownership_limits": {
                "max_lands_per_user": self.max_lands_per_user,
                "max_lands_per_biome_per_user": self.max_lands_per_biome_per_user,
                "max_contiguous_lands": self.max_contiguous_lands,
                "cooldown_minutes": self.ownership_cooldown_minutes,
            },
            "exploration_incentives": {
                "first_discover_enabled": self.exploration_first_discover_enabled,
                "first_discover_bonus_bdt": self.exploration_first_discover_bonus_bdt,
                "rare_land_spawn_rate": self.exploration_rare_land_spawn_rate,
                "rare_land_bonus_multiplier": self.exploration_rare_land_bonus_multiplier,
            },
            "auth": {
                "access_token_expire_minutes": self.access_token_expire_minutes,
                "refresh_token_expire_days": self.refresh_token_expire_days,
                "login_max_attempts": self.login_max_attempts,
                "lockout_duration_minutes": self.lockout_duration_minutes,
                "max_sessions_per_user": self.max_sessions_per_user,
            },
            "password_policy": {
                "min_length": self.password_min_length,
                "require_uppercase": self.password_require_uppercase,
                "require_lowercase": self.password_require_lowercase,
                "require_number": self.password_require_number,
                "require_special": self.password_require_special,
            },
            "listing_limits": {
                "max_lands_per_listing": self.max_lands_per_listing,
                "max_listing_duration_days": self.max_listing_duration_days,
                "listing_cooldown_minutes": self.listing_cooldown_minutes,
                "min_reserve_price_percent": self.min_reserve_price_percent,
            },
            "auction_antisinping": {
                "enabled": self.anti_sniping_enabled,
                "extend_minutes": self.anti_sniping_extend_minutes,
                "threshold_minutes": self.anti_sniping_threshold_minutes,
            },
            "payments": {
                "gateways": {
                    "bkash": {"enabled": self.enable_bkash, "mode": self.bkash_mode},
                    "nagad": {"enabled": self.enable_nagad, "mode": self.nagad_mode},
                    "rocket": {"enabled": self.enable_rocket, "mode": self.rocket_mode},
                    "sslcommerz": {"enabled": self.enable_sslcommerz, "mode": self.sslcommerz_mode},
                },
                "fees": {
                    "mode": self.gateway_fee_mode,
                    "percent": self.gateway_fee_percent,
                    "flat_bdt": self.gateway_fee_flat_bdt,
                },
                "limits": {
                    "min_bdt": self.topup_min_bdt,
                    "max_bdt": self.topup_max_bdt,
                    "daily_limit_bdt": self.topup_daily_limit_bdt,
                    "monthly_limit_bdt": self.topup_monthly_limit_bdt,
                },
                "monitoring": {
                    "alert_window_minutes": self.payment_alert_window_minutes,
                    "failure_threshold": self.payment_alert_failure_threshold,
                    "reconcile_tolerance": self.payment_reconcile_tolerance,
                },
            },
            "email": {
                "enabled": self.enable_email,
                "smtp": {
                    "host": self.smtp_host,
                    "port": self.smtp_port,
                    "username": self.smtp_username,
                    "use_tls": self.smtp_use_tls,
                    "use_ssl": self.smtp_use_ssl,
                },
                "defaults": {
                    "from_email": self.default_from_email,
                    "template_theme": self.email_template_theme,
                },
                "rate_limit_per_hour": self.email_rate_limit_per_hour,
                "password_set": bool(self.smtp_password),
            },
            "notifications": {
                "push": {
                    "enabled": self.enable_push_notifications,
                    "system_enabled": self.push_system_enabled,
                    "marketing_enabled": self.push_marketing_enabled,
                    "daily_limit": self.push_daily_limit,
                    "quiet_hours": {
                        "start_hour": self.push_quiet_hours_start,
                        "end_hour": self.push_quiet_hours_end,
                    },
                    "webhook_url_set": bool(self.push_webhook_url),
                },
            },
            "logging": {
                "level": self.log_level,
                "retention_days": self.log_retention_days,
            },
            "cache": {
                "chunk_ttl_seconds": self.chunk_cache_ttl_seconds,
            },
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
