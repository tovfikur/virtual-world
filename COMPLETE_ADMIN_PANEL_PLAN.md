# Complete Admin Panel Implementation Plan

## Overview
Build a comprehensive admin panel with ALL essential features for managing the Virtual Land World platform (excluding advanced monitoring/DevOps features).

---

## Features to Implement

### ✅ **Already Working**
1. Dashboard with basic stats
2. User list, search, and basic editing
3. System health check
4. Basic world config viewing
5. Audit logs

### 🔨 **To Be Implemented**

---

## **CATEGORY 1: Land Management**

### 1.1 Land Analytics
**Page:** `/admin/lands`
**Features:**
- Total lands: allocated vs unallocated
- Starter land distribution chart (sizes: 36×36, 63×63, 75×75, 100×100, etc.)
- Shape distribution (square, circle, triangle, rectangle)
- Lands per user statistics
- Search lands by coordinates
- View land details (owner, size, shape, biome, price)

### 1.2 Land Administration
**Features:**
- Transfer land ownership (manual)
- Reclaim/delete specific lands
- Bulk reclaim from inactive users
- Fix overlapping lands
- View land allocation history

### 1.3 Starter Land Configuration
**Features:**
- Enable/disable auto-allocation
- Edit size probability distribution
  - 36×36: slider (0-100%)
  - 63-75: slider (0-100%)
  - 76-1000: slider (0-100%)
- Edit shape probability
  - Square: slider (0-100%)
  - Other shapes: slider (0-100%)
- Min/max land size inputs
- Buffer spacing setting
- Preview allocation settings

---

## **CATEGORY 2: Marketplace & Economy**

### 2.1 Marketplace Moderation
**Page:** `/admin/marketplace`
**Features:**
- View all listings (active/sold/cancelled)
- Search by seller, price range, location
- Remove fraudulent listings
- View listing details and history
- Ban users from marketplace
- Price trend charts

### 2.2 Transaction Management
**Page:** `/admin/transactions`
**Features:**
- View all transactions (completed/pending/failed)
- Search by buyer/seller/amount/date range
- Transaction details popup
- Refund transaction (with confirmation)
- Export transactions as CSV
- Revenue summary (total, by period)

### 2.3 Economic Settings
**Features:**
- Transaction fee percentage (editable)
- Base land price by biome (editable)
- Biome pricing multipliers
  - Forest: input
  - Grassland: input
  - Water: input
  - Desert: input
  - Snow: input
- Min/max marketplace prices
- Enable/disable trading toggle
- Auction settings (bid increment, auto-extend minutes)

---

## **CATEGORY 3: User Management (Extended)**

### 3.1 Enhanced User Management
**Page:** `/admin/users` (enhanced)
**Features:**
- Suspend/ban users (with reason, duration)
- Unlock suspended accounts
- View login history (last 10 logins, IPs)
- View user's lands on map
- View user's transaction history
- Adjust user balance (with reason/audit)
- Change user role (user/moderator/admin)
- Delete user account (soft delete)
- Export user list as CSV

### 3.2 User Activity
**Features:**
- Last login timestamp
- Total time spent in-world
- Lands bought/sold count
- Messages sent count
- Account status (active/suspended/banned)

---

## **CATEGORY 4: Content Moderation**

### 4.1 Chat Moderation
**Page:** `/admin/moderation/chat`
**Features:**
- View recent chat messages (all users)
- Search messages by user, keyword, date
- Delete inappropriate messages
- Mute user from chat (duration)
- View user's chat history
- Export chat logs

### 4.2 Land Content
**Page:** `/admin/moderation/lands`
**Features:**
- View lands with public messages
- Search by content/owner
- Remove inappropriate land messages
- Clear fencing passwords (if reported)

### 4.3 User Reports
**Page:** `/admin/moderation/reports`
**Features:**
- View user reports (land, user, chat)
- Sort by date, type, status
- Assign to moderator
- Mark as resolved/dismissed
- Take action (ban, remove content, warn)
- Add notes to report

---

## **CATEGORY 5: Configuration & Settings**

### 5.1 World Generation (Full Edit)
**Page:** `/admin/config/world`
**Features:**
- World seed (editable, with warning)
- Noise parameters
  - Frequency: slider
  - Octaves: input
  - Persistence: slider
  - Lacunarity: slider
- Biome distribution (must sum to 100%)
  - Forest: %
  - Grassland: %
  - Water: %
  - Desert: %
  - Snow: %
- Regenerate world button (with confirmation)

### 5.2 Feature Toggles
**Page:** `/admin/config/features`
**Features:**
- Enable/disable land trading: toggle
- Enable/disable chat system: toggle
- Enable/disable user registration: toggle
- Enable/disable starter land allocation: toggle
- Enable/disable auctions: toggle
- Enable/disable WebRTC video: toggle
- Maintenance mode: toggle (blocks all users except admins)

### 5.3 System Limits
**Page:** `/admin/config/limits`
**Features:**
- Max lands per user: input
- Max active listings per user: input
- Max chat messages per minute: input
- Chunk cache TTL (seconds): input
- Max WebSocket connections: input
- API rate limit (requests/minute): input

---

## **CATEGORY 6: Analytics & Reports**

### 6.1 Business Dashboard
**Page:** `/admin/analytics`
**Features:**
- User metrics
  - Total users, new users (7d, 30d)
  - Active users (DAU, MAU)
  - User retention chart
- Economic metrics
  - Total revenue (all time, 30d, 7d)
  - Average transaction value
  - Transaction volume chart
  - Top spenders list
- Land metrics
  - Total lands allocated
  - Lands for sale
  - Average land price
  - Most expensive land sold

### 6.2 World Heatmap
**Page:** `/admin/analytics/heatmap`
**Features:**
- 2D map visualization
- Color-coded regions by activity
  - Land sales density
  - User presence
  - Exploration hotspots
- Time range selector (24h, 7d, 30d)

### 6.3 Export & Reports
**Page:** `/admin/reports`
**Features:**
- Export users (CSV)
- Export transactions (CSV, date range)
- Export lands (CSV, with owner info)
- Export audit logs (CSV, filtered)
- Generate financial report (PDF)
- Schedule automated reports (email)

---

## **CATEGORY 7: Communication**

### 7.1 Announcements
**Page:** `/admin/announcements`
**Features:**
- Create announcement
  - Title
  - Message
  - Type (info/warning/urgent)
  - Target audience (all/role/specific users)
  - Start/end date
  - Display location (banner/popup/both)
- View active announcements
- Edit/delete announcements
- Schedule future announcements

### 7.2 Broadcast Messages
**Page:** `/admin/broadcast`
**Features:**
- Send instant message to:
  - All online users
  - All users (email)
  - Specific role (admin/moderator/user)
  - Specific users (comma-separated IDs)
- Message preview
- Send confirmation dialog

---

## **CATEGORY 8: Security**

### 8.1 User Bans & Suspensions
**Page:** `/admin/security/bans`
**Features:**
- Active bans list
- Ban user form
  - User ID/username
  - Reason (required)
  - Duration (permanent/temporary)
  - Ban type (full/marketplace/chat)
- Unban user
- View ban history
- IP ban (optional)

### 8.2 Security Logs
**Page:** `/admin/security/logs`
**Features:**
- Failed login attempts
- Rate limit violations
- Suspicious transactions (flagged)
- IP blacklist management
- Security alerts

---

## Implementation Structure

### **Backend API Endpoints**

```
/api/v1/admin/
├── dashboard/
│   ├── stats (existing)
│   └── analytics (enhanced)
├── users/
│   ├── list (existing)
│   ├── {id} (existing)
│   ├── {id}/suspend
│   ├── {id}/ban
│   ├── {id}/login-history
│   └── export
├── lands/
│   ├── analytics
│   ├── search
│   ├── {id}/transfer
│   ├── {id}/reclaim
│   └── bulk-reclaim
├── marketplace/
│   ├── listings
│   ├── {id}/remove
│   └── ban-user
├── transactions/
│   ├── list
│   ├── {id}/refund
│   └── export
├── moderation/
│   ├── chat-messages
│   ├── {id}/delete-message
│   ├── {user_id}/mute
│   ├── land-content
│   └── reports
├── config/
│   ├── world (enhanced)
│   ├── features
│   ├── economy
│   └── limits
├── announcements/
│   ├── list
│   ├── create
│   ├── {id}/update
│   └── {id}/delete
├── security/
│   ├── bans
│   ├── ban-user
│   ├── unban-user
│   └── security-logs
└── reports/
    ├── export-users
    ├── export-transactions
    └── generate-financial
```

### **Frontend Pages**

```
/admin/
├── dashboard (existing, enhanced)
├── users (existing, enhanced)
├── lands (NEW)
│   ├── analytics
│   └── administration
├── marketplace (NEW)
│   ├── listings
│   └── transactions
├── moderation (NEW)
│   ├── chat
│   ├── lands
│   └── reports
├── config (existing, enhanced)
│   ├── world
│   ├── features
│   ├── economy
│   └── limits
├── analytics (NEW)
│   ├── dashboard
│   ├── heatmap
│   └── reports
├── announcements (NEW)
├── broadcast (NEW)
├── security (NEW)
│   ├── bans
│   └── logs
└── logs (existing)
```

---

## Database Schema Additions

### New Tables Needed

```sql
-- User bans/suspensions
CREATE TABLE bans (
  ban_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(user_id),
  banned_by UUID REFERENCES users(user_id),
  reason TEXT NOT NULL,
  ban_type VARCHAR(20) NOT NULL, -- 'full', 'marketplace', 'chat'
  expires_at TIMESTAMP WITH TIME ZONE,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Announcements
CREATE TABLE announcements (
  announcement_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title VARCHAR(255) NOT NULL,
  message TEXT NOT NULL,
  type VARCHAR(20) NOT NULL, -- 'info', 'warning', 'urgent'
  target_audience VARCHAR(50), -- 'all', 'admins', 'users'
  display_location VARCHAR(20), -- 'banner', 'popup', 'both'
  start_date TIMESTAMP WITH TIME ZONE,
  end_date TIMESTAMP WITH TIME ZONE,
  created_by UUID REFERENCES users(user_id),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- User reports
CREATE TABLE reports (
  report_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  reporter_id UUID REFERENCES users(user_id),
  reported_user_id UUID REFERENCES users(user_id),
  resource_type VARCHAR(50), -- 'user', 'land', 'chat_message'
  resource_id UUID,
  reason TEXT NOT NULL,
  status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'resolved', 'dismissed'
  assigned_to UUID REFERENCES users(user_id),
  resolution_notes TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  resolved_at TIMESTAMP WITH TIME ZONE
);

-- Feature flags (alternative: use admin_config)
CREATE TABLE feature_flags (
  flag_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  flag_name VARCHAR(100) UNIQUE NOT NULL,
  enabled BOOLEAN DEFAULT false,
  description TEXT,
  updated_by UUID REFERENCES users(user_id),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### Modify Existing Tables

```sql
-- Add to users table
ALTER TABLE users ADD COLUMN is_suspended BOOLEAN DEFAULT false;
ALTER TABLE users ADD COLUMN suspension_reason TEXT;
ALTER TABLE users ADD COLUMN suspended_until TIMESTAMP WITH TIME ZONE;
ALTER TABLE users ADD COLUMN last_login TIMESTAMP WITH TIME ZONE;

-- Add to admin_config table
ALTER TABLE admin_config ADD COLUMN maintenance_mode BOOLEAN DEFAULT false;
ALTER TABLE admin_config ADD COLUMN enable_land_trading BOOLEAN DEFAULT true;
ALTER TABLE admin_config ADD COLUMN enable_chat BOOLEAN DEFAULT true;
ALTER TABLE admin_config ADD COLUMN enable_registration BOOLEAN DEFAULT true;
ALTER TABLE admin_config ADD COLUMN max_lands_per_user INTEGER DEFAULT NULL;
ALTER TABLE admin_config ADD COLUMN max_listings_per_user INTEGER DEFAULT 10;
ALTER TABLE admin_config ADD COLUMN auction_bid_increment INTEGER DEFAULT 100;
ALTER TABLE admin_config ADD COLUMN auction_extend_minutes INTEGER DEFAULT 5;
```

---

## UI/UX Design Guidelines

### **Sidebar Navigation**
```
Admin Panel
├── 🏠 Dashboard
├── 👥 Users
├── 🏘️ Lands
│   ├── Analytics
│   └── Administration
├── 🛒 Marketplace
│   ├── Listings
│   └── Transactions
├── 🛡️ Moderation
│   ├── Chat
│   ├── Land Content
│   └── Reports
├── ⚙️ Configuration
│   ├── World Generation
│   ├── Features
│   ├── Economy
│   └── System Limits
├── 📊 Analytics
│   ├── Business Dashboard
│   ├── World Heatmap
│   └── Reports & Exports
├── 📢 Communication
│   ├── Announcements
│   └── Broadcast
├── 🔒 Security
│   ├── Bans & Suspensions
│   └── Security Logs
└── 📋 Audit Logs
```

### **Color Coding**
- **Green**: Safe actions (view, enable)
- **Blue**: Neutral actions (edit, configure)
- **Yellow**: Caution actions (suspend, remove)
- **Red**: Dangerous actions (ban, delete, refund)

### **Confirmation Dialogs**
Required for:
- Ban/suspend user
- Refund transaction
- Delete content
- Change world seed
- Bulk operations
- Disable critical features

### **Audit Trail**
Every admin action must log:
- Admin user ID
- Action type
- Resource affected
- Timestamp
- Details/reason

---

## Development Timeline

### **Week 1: Land Management**
- Land analytics page
- Land administration tools
- Starter land configuration UI

### **Week 2: Marketplace & Economy**
- Marketplace moderation page
- Transaction management
- Economic settings UI

### **Week 3: User Management & Moderation**
- Enhanced user management
- Chat moderation
- Reports system

### **Week 4: Configuration**
- World generation settings (editable)
- Feature toggles
- System limits

### **Week 5: Analytics & Communication**
- Business analytics dashboard
- World heatmap
- Announcements system
- Broadcast tools

### **Week 6: Security & Polish**
- Bans/suspensions
- Security logs
- Export/reports
- Bug fixes and polish

---

## Success Metrics

### **Admin Panel Should Enable:**
1. ✅ Manage 10,000+ users efficiently
2. ✅ Moderate content within 5 minutes of report
3. ✅ Respond to security incidents immediately
4. ✅ Generate business reports in < 10 seconds
5. ✅ Configure all system settings without code changes
6. ✅ Track all admin actions with audit trail
7. ✅ Export data for compliance/accounting

---

## Next Steps

1. **Create database migrations** for new tables
2. **Implement backend API endpoints** (category by category)
3. **Build frontend pages** (parallel with backend)
4. **Add comprehensive testing**
5. **Document all admin features**
6. **Train admin/moderator users**

---

Ready to start implementation?