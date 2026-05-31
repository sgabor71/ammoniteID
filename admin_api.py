# admin_api.py - Admin analytics endpoints for AmmoniteID
# Add these endpoints to your main.py FastAPI app

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from datetime import datetime, timedelta
from typing import Optional, List
import sqlite3
from pathlib import Path

router = APIRouter()

# Database path (adjust based on your setup)
DB_PATH = Path(__file__).parent / 'ammonite.db'

# ============================================
# DATABASE SCHEMA UPDATES NEEDED
# ============================================
"""
Run these SQL commands to add tracking tables:

CREATE TABLE IF NOT EXISTS ad_impressions (
    impression_id INTEGER PRIMARY KEY AUTOINCREMENT,
    partner_id TEXT NOT NULL,
    partner_name TEXT NOT NULL,
    page TEXT NOT NULL,
    user_id TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    session_id TEXT
);

CREATE TABLE IF NOT EXISTS ad_clicks (
    click_id INTEGER PRIMARY KEY AUTOINCREMENT,
    partner_id TEXT NOT NULL,
    partner_name TEXT NOT NULL,
    page TEXT NOT NULL,
    user_id TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    session_id TEXT,
    seconds_viewed INTEGER
);

CREATE TABLE IF NOT EXISTS page_visits (
    visit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    page TEXT NOT NULL,
    user_id TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    time_spent INTEGER,
    session_id TEXT
);

CREATE TABLE IF NOT EXISTS partners (
    partner_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    email TEXT,
    bg_color TEXT NOT NULL,
    logo_path TEXT,
    billing_model TEXT DEFAULT 'none',
    rate_amount REAL DEFAULT 0,
    active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    anchor TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS subscriptions (
    subscription_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    status TEXT DEFAULT 'active',
    source TEXT DEFAULT 'website',
    amount REAL NOT NULL,
    start_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    end_date DATETIME,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- Add premium status to users table if not exists
ALTER TABLE users ADD COLUMN premium_status TEXT DEFAULT 'FREE';
ALTER TABLE users ADD COLUMN premium_expires DATETIME;

-- Create indexes for performance
CREATE INDEX idx_ad_impressions_partner ON ad_impressions(partner_id);
CREATE INDEX idx_ad_impressions_page ON ad_impressions(page);
CREATE INDEX idx_ad_impressions_timestamp ON ad_impressions(timestamp);
CREATE INDEX idx_ad_clicks_partner ON ad_clicks(partner_id);
CREATE INDEX idx_ad_clicks_timestamp ON ad_clicks(timestamp);
CREATE INDEX idx_page_visits_page ON page_visits(page);
"""

# ============================================
# PYDANTIC MODELS
# ============================================

class AdImpression(BaseModel):
    partner_id: str
    partner_name: str
    page: str
    user_id: Optional[str] = None
    session_id: str

class AdClick(BaseModel):
    partner_id: str
    partner_name: str
    page: str
    user_id: Optional[str] = None
    session_id: str
    seconds_viewed: Optional[int] = None

class PageVisit(BaseModel):
    page: str
    user_id: Optional[str] = None
    session_id: str
    time_spent: Optional[int] = None

class Partner(BaseModel):
    partner_id: str
    name: str
    url: str
    email: Optional[str] = None
    bg_color: str = '#FFB6C1'
    logo_path: Optional[str] = None
    billing_model: str = 'none'
    rate_amount: float = 0
    active: bool = True
    anchor: str = ''
    description: Optional[str] = ''
    address: Optional[str] = ''
    phone: Optional[str] = ''
    map_link: Optional[str] = ''
    offer: Optional[str] = ''
    category: Optional[str] = 'activities'
    tier: Optional[str] = 'standard'
    status: Optional[str] = 'active'
    logo_emoji: Optional[str] = '🏪'
    expires_at: Optional[str] = None
    display_duration: Optional[int] = 15
    rotation_weight: Optional[int] = 1

# ============================================
# TRACKING ENDPOINTS (Called from frontend)
# ============================================

@router.post("/api/track/ad-impression")
async def track_ad_impression(impression: AdImpression):
    """Track when an ad is shown to a user"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO ad_impressions (partner_id, partner_name, page, user_id, session_id)
            VALUES (?, ?, ?, ?, ?)
        """, (impression.partner_id, impression.partner_name, impression.page, 
              impression.user_id, impression.session_id))
        
        conn.commit()
        conn.close()
        
        return {"status": "success", "message": "Impression tracked"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/track/ad-click")
async def track_ad_click(click: AdClick):
    """Track when a user clicks an ad"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO ad_clicks (partner_id, partner_name, page, user_id, session_id, seconds_viewed)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (click.partner_id, click.partner_name, click.page, 
              click.user_id, click.session_id, click.seconds_viewed))
        
        conn.commit()
        conn.close()
        
        return {"status": "success", "message": "Click tracked"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/track/page-visit")
async def track_page_visit(visit: PageVisit):
    """Track page visits"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO page_visits (page, user_id, session_id, time_spent)
            VALUES (?, ?, ?, ?)
        """, (visit.page, visit.user_id, visit.session_id, visit.time_spent))
        
        conn.commit()
        conn.close()
        
        return {"status": "success", "message": "Visit tracked"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# ADMIN DASHBOARD ENDPOINTS
# ============================================

@router.get("/api/admin/dashboard")
async def get_dashboard_stats():
    """Get overview statistics for admin dashboard"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Total users
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        # Active users (last 30 days)
        thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()
        cursor.execute("SELECT COUNT(DISTINCT user_id) FROM identifications WHERE timestamp > ?", (thirty_days_ago,))
        active_users = cursor.fetchone()[0]
        
        # Total identifications
        cursor.execute("SELECT COUNT(*) FROM identifications")
        total_identifications = cursor.fetchone()[0]
        
        # IDs today
        today = datetime.now().date().isoformat()
        cursor.execute("SELECT COUNT(*) FROM identifications WHERE DATE(timestamp) = ?", (today,))
        ids_today = cursor.fetchone()[0]
        
        # FREE vs PREMIUM
        cursor.execute("SELECT COUNT(*) FROM users WHERE premium_status = 'FREE'")
        free_users = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM users WHERE premium_status = 'PREMIUM'")
        premium_users = cursor.fetchone()[0]
        
        # Ad impressions and clicks
        cursor.execute("SELECT COUNT(*) FROM ad_impressions")
        total_impressions = cursor.fetchone()[0] if cursor.fetchone() else 0
        
        cursor.execute("SELECT COUNT(*) FROM ad_clicks")
        total_clicks = cursor.fetchone()[0] if cursor.fetchone() else 0
        
        # New users this week
        week_ago = (datetime.now() - timedelta(days=7)).isoformat()
        cursor.execute("SELECT COUNT(*) FROM users WHERE created_at > ?", (week_ago,))
        new_users_week = cursor.fetchone()[0]
        
        # Overall CTR
        overall_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
        
        # Conversion rate
        conversion_rate = (premium_users / total_users * 100) if total_users > 0 else 0
        
        # MRR (placeholder - will need subscription data)
        cursor.execute("SELECT SUM(amount) FROM subscriptions WHERE status = 'active'")
        mrr_result = cursor.fetchone()
        mrr = mrr_result[0] if mrr_result and mrr_result[0] else 0
        
        conn.close()
        
        return {
            "total_users": total_users,
            "active_users": active_users,
            "total_identifications": total_identifications,
            "ids_today": ids_today,
            "free_users": free_users,
            "premium_users": premium_users,
            "total_impressions": total_impressions,
            "total_clicks": total_clicks,
            "new_users_week": new_users_week,
            "overall_ctr": round(overall_ctr, 2),
            "conversion_rate": round(conversion_rate, 1),
            "mrr": round(mrr, 2)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/admin/ad-performance")
async def get_ad_performance():
    """Get detailed ad performance by partner and page"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Performance by partner
        cursor.execute("""
            SELECT 
                p.partner_name,
                COUNT(DISTINCT i.impression_id) as impressions,
                COUNT(DISTINCT c.click_id) as clicks,
                ROUND(CAST(COUNT(DISTINCT c.click_id) AS FLOAT) / 
                      NULLIF(COUNT(DISTINCT i.impression_id), 0) * 100, 2) as ctr
            FROM partners p
            LEFT JOIN ad_impressions i ON p.partner_id = i.partner_id
            LEFT JOIN ad_clicks c ON p.partner_id = c.partner_id
            GROUP BY p.partner_name
        """)
        
        partners_data = []
        for row in cursor.fetchall():
            partners_data.append({
                "partner": row[0],
                "impressions": row[1],
                "clicks": row[2],
                "ctr": row[3] or 0
            })
        
        # Performance by page
        cursor.execute("""
            SELECT 
                page,
                COUNT(*) as impressions,
                (SELECT COUNT(*) FROM ad_clicks WHERE ad_clicks.page = ad_impressions.page) as clicks
            FROM ad_impressions
            GROUP BY page
        """)
        
        pages_data = []
        for row in cursor.fetchall():
            impressions = row[1]
            clicks = row[2]
            ctr = (clicks / impressions * 100) if impressions > 0 else 0
            pages_data.append({
                "page": row[0],
                "impressions": impressions,
                "clicks": clicks,
                "ctr": round(ctr, 2)
            })
        
        conn.close()
        
        return {
            "by_partner": partners_data,
            "by_page": pages_data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/admin/partner-report/{partner_id}")
async def get_partner_report(partner_id: str, date_from: Optional[str] = None, date_to: Optional[str] = None):
    """Generate detailed report for a specific partner"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Build date filter
        date_filter = ""
        params = [partner_id]
        
        if date_from and date_to:
            date_filter = " AND timestamp BETWEEN ? AND ?"
            params.extend([date_from, date_to])
        
        # Get partner details
        cursor.execute("SELECT * FROM partners WHERE partner_id = ?", (partner_id,))
        partner = cursor.fetchone()
        
        if not partner:
            raise HTTPException(status_code=404, detail="Partner not found")
        
        # Total impressions
        cursor.execute(f"SELECT COUNT(*) FROM ad_impressions WHERE partner_id = ?{date_filter}", params)
        total_impressions = cursor.fetchone()[0]
        
        # Total clicks
        cursor.execute(f"SELECT COUNT(*) FROM ad_clicks WHERE partner_id = ?{date_filter}", params)
        total_clicks = cursor.fetchone()[0]
        
        # CTR
        ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
        
        # Breakdown by page
        cursor.execute(f"""
            SELECT page, COUNT(*) as impressions
            FROM ad_impressions 
            WHERE partner_id = ?{date_filter}
            GROUP BY page
        """, params)
        
        page_breakdown = {}
        for row in cursor.fetchall():
            page = row[0]
            impressions = row[1]
            
            # Get clicks for this page
            click_params = [partner_id, page]
            if date_from and date_to:
                click_params.extend([date_from, date_to])
                
            cursor.execute(f"""
                SELECT COUNT(*) FROM ad_clicks 
                WHERE partner_id = ? AND page = ?{date_filter.replace('timestamp', 'timestamp')}
            """, click_params)
            clicks = cursor.fetchone()[0]
            
            page_breakdown[page] = {
                "impressions": impressions,
                "clicks": clicks,
                "ctr": round((clicks / impressions * 100), 2) if impressions > 0 else 0
            }
        
        # Calculate billing
        billing_amount = 0
        billing_model = partner[7]  # billing_model column
        rate = partner[8]  # rate_amount column
        
        if billing_model == 'cpm':
            billing_amount = (total_impressions / 1000) * rate
        elif billing_model == 'cpc':
            billing_amount = total_clicks * rate
        elif billing_model == 'flat':
            billing_amount = rate
        
        conn.close()
        
        return {
            "partner_name": partner[1],
            "partner_url": partner[2],
            "date_from": date_from,
            "date_to": date_to,
            "total_impressions": total_impressions,
            "total_clicks": total_clicks,
            "ctr": round(ctr, 2),
            "page_breakdown": page_breakdown,
            "billing_model": billing_model,
            "rate": rate,
            "billing_amount": round(billing_amount, 2)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# PARTNER MANAGEMENT ENDPOINTS
# ============================================

@router.get("/api/admin/partners")
async def get_all_partners():
    """Get all partners"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT partner_id, name, url, email, bg_color, logo_path, billing_model, 
                   rate_amount, active, created_at, anchor,
                   description, address, phone, map_link, offer, category, tier, status, logo_emoji, expires_at,
                   display_duration, rotation_weight
            FROM partners
        """)
        partners = []
        
        for row in cursor.fetchall():
            partners.append({
                "partner_id": row["partner_id"],
                "name": row["name"],
                "url": row["url"],
                "email": row["email"],
                "bg_color": row["bg_color"],
                "logo_path": row["logo_path"],
                "billing_model": row["billing_model"],
                "rate_amount": row["rate_amount"],
                "active": row["active"],
                "created_at": row["created_at"],
                "anchor": row["anchor"],
                "description": row["description"] or "",
                "address": row["address"] or "",
                "phone": row["phone"] or "",
                "map_link": row["map_link"] or "",
                "offer": row["offer"] or "",
                "category": row["category"] or "activities",
                "tier": row["tier"] or "standard",
                "status": row["status"] or "active",
                "logo_emoji": row["logo_emoji"] or "🏪",
                "expires_at": row["expires_at"] or None,
                "display_duration": row["display_duration"] or 15,
                "rotation_weight": row["rotation_weight"] or 1
            })
        
        conn.close()
        return {"partners": partners}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/admin/partners")
async def create_partner(partner: Partner):
    """Add a new partner"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO partners 
            (partner_id, name, url, email, bg_color, logo_path, billing_model, rate_amount, active, anchor,
             description, address, phone, map_link, offer, category, tier, status, logo_emoji, expires_at,
             display_duration, rotation_weight)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (partner.partner_id, partner.name, partner.url, partner.email, 
              partner.bg_color, partner.logo_path, partner.billing_model, 
              partner.rate_amount, 1 if partner.active else 0, partner.anchor,
              partner.description, partner.address, partner.phone, partner.map_link,
              partner.offer, partner.category, partner.tier, partner.status, partner.logo_emoji,
              partner.expires_at, partner.display_duration, partner.rotation_weight))
        
        conn.commit()
        conn.close()
        
        return {"status": "success", "message": "Partner added successfully"}
        
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Partner with this ID already exists. Try a different name.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/api/admin/partners/{partner_id}")
async def update_partner(partner_id: str, partner: Partner):
    """Update partner details"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE partners 
            SET name = ?, url = ?, email = ?, bg_color = ?, logo_path = ?,
                billing_model = ?, rate_amount = ?, active = ?, anchor = ?,
                description = ?, address = ?, phone = ?, map_link = ?, 
                offer = ?, category = ?, tier = ?, status = ?, logo_emoji = ?, expires_at = ?,
                display_duration = ?, rotation_weight = ?
            WHERE partner_id = ?
        """, (partner.name, partner.url, partner.email, partner.bg_color,
              partner.logo_path, partner.billing_model, partner.rate_amount,
              1 if partner.active else 0, partner.anchor,
              partner.description, partner.address, partner.phone, partner.map_link,
              partner.offer, partner.category, partner.tier, partner.status, partner.logo_emoji,
              partner.expires_at, partner.display_duration, partner.rotation_weight, partner_id))
        
        conn.commit()
        conn.close()
        
        return {"status": "success", "message": "Partner updated successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/api/admin/partners/{partner_id}")
async def delete_partner(partner_id: str):
    """Deactivate a partner"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("UPDATE partners SET active = 0, status = 'expired' WHERE partner_id = ?", (partner_id,))
        
        conn.commit()
        conn.close()
        
        return {"status": "success", "message": "Partner deleted"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/admin/partners/{partner_id}/pause")
async def pause_partner(partner_id: str):
    """Pause a partner - hides from public pages but keeps data"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("UPDATE partners SET status = 'paused' WHERE partner_id = ?", (partner_id,))
        
        conn.commit()
        conn.close()
        
        return {"status": "success", "message": "Partner paused"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/admin/partners/{partner_id}/resume")
async def resume_partner(partner_id: str):
    """Resume a paused partner"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("UPDATE partners SET status = 'active' WHERE partner_id = ?", (partner_id,))
        
        conn.commit()
        conn.close()
        
        return {"status": "success", "message": "Partner resumed"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# ADD TO main.py:
# ============================================
"""
from admin_api import router as admin_router

app.include_router(admin_router)
"""
