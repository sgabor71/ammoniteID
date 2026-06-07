# admin_content_api.py - Content management endpoints
# Add these to your existing admin_api.py or import this router

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import sqlite3
import json
from pathlib import Path

# Import shared database configuration
from database import DB_PATH

content_router = APIRouter()

# ============================================
# ADDITIONAL DATABASE SCHEMA
# ============================================
"""
Run these SQL commands to add content management tables:

CREATE TABLE IF NOT EXISTS site_content (
    content_id TEXT PRIMARY KEY,
    page TEXT NOT NULL,
    section TEXT NOT NULL,
    content_data TEXT NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS site_design (
    design_id INTEGER PRIMARY KEY AUTOINCREMENT,
    setting_name TEXT UNIQUE NOT NULL,
    setting_value TEXT NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Insert default content
INSERT OR IGNORE INTO site_content VALUES 
('home_hero', 'home', 'hero', '{"title": "Identify Your Ammonite in Seconds", "subtitle": "AI-powered fossil identification at your fingertips", "cta": "Start Identifying Now"}', CURRENT_TIMESTAMP),
('home_features', 'home', 'features', '{"feature1": {"title": "AI-Powered Recognition", "desc": "Advanced machine learning identifies your fossils instantly"}, "feature2": {"title": "Instant Results", "desc": "Get detailed information in seconds"}, "feature3": {"title": "Build Your Collection", "desc": "Save and organize all your discoveries"}}', CURRENT_TIMESTAMP),
('about_content', 'about', 'main', '{"mission": "Our mission is to make fossil identification accessible to everyone", "title": "About AmmoniteID", "text": "AmmoniteID uses cutting-edge AI technology to help identify ammonites and other fossils."}', CURRENT_TIMESTAMP),
('contact_info', 'contact', 'info', '{"email": "contact@ammoniteid.com", "phone": "", "intro": "Get in touch with us for questions or feedback"}', CURRENT_TIMESTAMP);

-- Insert default design settings
INSERT OR IGNORE INTO site_design (setting_name, setting_value) VALUES
('heading_font', '''Segoe UI'', sans-serif'),
('body_font', '''Segoe UI'', sans-serif'),
('heading_size', '36'),
('body_size', '16'),
('primary_color', '#2c5f2d'),
('secondary_color', '#3498db'),
('heading_color', '#2c5f2d'),
('body_color', '#333333'),
('button_bg', '#2c5f2d'),
('button_text', '#ffffff');
"""

# ============================================
# PYDANTIC MODELS
# ============================================

class HomeContent(BaseModel):
    heroTitle: str
    heroSubtitle: str
    ctaButton: str
    feature1Title: str
    feature1Desc: str
    feature2Title: str
    feature2Desc: str
    feature3Title: str
    feature3Desc: str

class AboutContent(BaseModel):
    missionStatement: str
    aboutTitle: str
    aboutText: str
    futurePlans: Optional[list] = []
    photoTipsIntro: Optional[str] = ""
    photoTips: Optional[list] = []
    trainingStats: Optional[list] = []
    faqs: Optional[list] = []

class ContactContent(BaseModel):
    contactEmail: str
    contactPhone: Optional[str] = ""
    contactIntro: str

class DesignSettings(BaseModel):
    headingFont: str
    bodyFont: str
    headingSize: str
    bodySize: str
    primaryColor: str
    secondaryColor: str
    headingColor: str
    bodyColor: str
    buttonBg: str
    buttonText: str

# ============================================
# CONTENT MANAGEMENT ENDPOINTS
# ============================================

@content_router.get("/api/content/home")
async def get_home_content():
    """Get home page content"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        cursor.execute("SELECT content_data FROM site_content WHERE content_id = 'home_hero'")
        hero = cursor.fetchone()
        
        cursor.execute("SELECT content_data FROM site_content WHERE content_id = 'home_features'")
        features = cursor.fetchone()
        
        conn.close()
        
        result = {}
        if hero:
            result.update(json.loads(hero[0]))
        if features:
            result.update(json.loads(features[0]))
            
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@content_router.post("/api/content/home")
async def save_home_content(content: HomeContent):
    """Save home page content"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        # Save hero content
        hero_data = json.dumps({
            "title": content.heroTitle,
            "subtitle": content.heroSubtitle,
            "cta": content.ctaButton
        })
        
        cursor.execute("""
            INSERT OR REPLACE INTO site_content (content_id, page, section, content_data, updated_at)
            VALUES ('home_hero', 'home', 'hero', ?, CURRENT_TIMESTAMP)
        """, (hero_data,))
        
        # Save features content
        features_data = json.dumps({
            "feature1": {
                "title": content.feature1Title,
                "desc": content.feature1Desc
            },
            "feature2": {
                "title": content.feature2Title,
                "desc": content.feature2Desc
            },
            "feature3": {
                "title": content.feature3Title,
                "desc": content.feature3Desc
            }
        })
        
        cursor.execute("""
            INSERT OR REPLACE INTO site_content (content_id, page, section, content_data, updated_at)
            VALUES ('home_features', 'home', 'features', ?, CURRENT_TIMESTAMP)
        """, (features_data,))
        
        conn.commit()
        conn.close()
        
        return {"status": "success", "message": "Home content saved"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@content_router.get("/api/content/about")
async def get_about_content():
    """Get about page content"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        cursor.execute("SELECT content_data FROM site_content WHERE content_id = 'about_content'")
        result = cursor.fetchone()
        
        conn.close()
        
        if result:
            return json.loads(result[0])
        return {}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@content_router.post("/api/content/about")
async def save_about_content(content: AboutContent):
    """Save about page content"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        content_data = json.dumps({
            "mission": content.missionStatement,
            "title": content.aboutTitle,
            "text": content.aboutText,
            "futurePlans": content.futurePlans,
            "photoTipsIntro": content.photoTipsIntro,
            "photoTips": content.photoTips,
            "trainingStats": content.trainingStats,
            "faqs": content.faqs
        })
        
        cursor.execute("""
            INSERT OR REPLACE INTO site_content (content_id, page, section, content_data, updated_at)
            VALUES ('about_content', 'about', 'main', ?, CURRENT_TIMESTAMP)
        """, (content_data,))
        
        conn.commit()
        conn.close()
        
        return {"status": "success", "message": "About content saved"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@content_router.get("/api/content/contact")
async def get_contact_content():
    """Get contact page content"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        cursor.execute("SELECT content_data FROM site_content WHERE content_id = 'contact_info'")
        result = cursor.fetchone()
        
        conn.close()
        
        if result:
            return json.loads(result[0])
        return {}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@content_router.post("/api/content/contact")
async def save_contact_content(content: ContactContent):
    """Save contact page content"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        content_data = json.dumps({
            "email": content.contactEmail,
            "phone": content.contactPhone,
            "intro": content.contactIntro
        })
        
        cursor.execute("""
            INSERT OR REPLACE INTO site_content (content_id, page, section, content_data, updated_at)
            VALUES ('contact_info', 'contact', 'info', ?, CURRENT_TIMESTAMP)
        """, (content_data,))
        
        conn.commit()
        conn.close()
        
        return {"status": "success", "message": "Contact content saved"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# DESIGN SETTINGS ENDPOINTS
# ============================================

@content_router.get("/api/design/settings")
async def get_design_settings():
    """Get all design settings"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        cursor.execute("SELECT setting_name, setting_value FROM site_design")
        rows = cursor.fetchall()
        
        conn.close()
        
        settings = {}
        for row in rows:
            settings[row[0]] = row[1]
            
        return settings
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@content_router.post("/api/design/settings")
async def save_design_settings(settings: DesignSettings):
    """Save design settings"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        settings_dict = {
            'heading_font': settings.headingFont,
            'body_font': settings.bodyFont,
            'heading_size': settings.headingSize,
            'body_size': settings.bodySize,
            'primary_color': settings.primaryColor,
            'secondary_color': settings.secondaryColor,
            'heading_color': settings.headingColor,
            'body_color': settings.bodyColor,
            'button_bg': settings.buttonBg,
            'button_text': settings.buttonText
        }
        
        for name, value in settings_dict.items():
            cursor.execute("""
                INSERT OR REPLACE INTO site_design (setting_name, setting_value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (name, value))
        
        conn.commit()
        conn.close()
        
        return {"status": "success", "message": "Design settings saved"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@content_router.post("/api/design/reset")
async def reset_design_settings():
    """Reset design settings to defaults"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        defaults = {
            'heading_font': "'Segoe UI', sans-serif",
            'body_font': "'Segoe UI', sans-serif",
            'heading_size': '36',
            'body_size': '16',
            'primary_color': '#2c5f2d',
            'secondary_color': '#3498db',
            'heading_color': '#2c5f2d',
            'body_color': '#333333',
            'button_bg': '#2c5f2d',
            'button_text': '#ffffff'
        }
        
        for name, value in defaults.items():
            cursor.execute("""
                UPDATE site_design SET setting_value = ?, updated_at = CURRENT_TIMESTAMP
                WHERE setting_name = ?
            """, (value, name))
        
        conn.commit()
        conn.close()
        
        return {"status": "success", "message": "Design settings reset to defaults"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# PARTNERS FOR PUBLIC PAGES ENDPOINT
# ============================================

@content_router.get("/api/content")
async def get_all_content():
    """Get all site content including partners - used by partners.html page"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get partners for public display - only active status
        cursor.execute("""
            SELECT partner_id, name, url, email, bg_color, logo_path, 
                   billing_model, rate_amount, active, anchor,
                   description, address, phone, map_link, offer, 
                   category, tier, status, logo_emoji
            FROM partners WHERE active = 1 AND status = 'active'
        """)
        
        partners = []
        for row in cursor.fetchall():
            partners.append({
                "id": row["partner_id"],
                "name": row["name"],
                "description": row["description"] or "",
                "website": row["url"],
                "email": row["email"] or "",
                "address": row["address"] or "",
                "phone": row["phone"] or "",
                "mapLink": row["map_link"] or "",
                "offer": row["offer"] or "",
                "category": row["category"] or "activities",
                "tier": row["tier"] or "standard",
                "status": row["status"] or "active",
                "logo": row["logo_emoji"] or "🏪",
                "logoData": row["logo_path"] or "",
                "bgColor": row["bg_color"] or "",
                "anchor": row["anchor"] or ""
            })
        
        # Get other content
        cursor.execute("SELECT content_data FROM site_content WHERE content_id = 'home_hero'")
        home_hero = cursor.fetchone()
        
        cursor.execute("SELECT content_data FROM site_content WHERE content_id = 'about_content'")
        about = cursor.fetchone()
        
        cursor.execute("SELECT content_data FROM site_content WHERE content_id = 'home_features'")
        features = cursor.fetchone()
        
        conn.close()
        
        home_data = json.loads(home_hero[0]) if home_hero else {}
        about_data = json.loads(about[0]) if about else {}
        
        return {
            "home": {
                "hero_title": home_data.get("title", "Identify Your Fossil"),
                "hero_subtitle": home_data.get("subtitle", "")
            },
            "about": {
                "mission": about_data.get("mission", "")
            },
            "faq": about_data.get("faqs", []),
            "partners": partners
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# ADD TO main.py:
# ============================================
"""
from admin_content_api import content_router

app.include_router(content_router)
"""

# ============================================================
# LEGAL DOCUMENTS (Terms, Privacy, Disclaimer)
# ============================================================

@content_router.get("/legal/{doc_type}")
async def get_legal_document(doc_type: str):
    """Fetch legal document content (terms, privacy, disclaimer)."""
    if doc_type not in ("terms", "privacy", "disclaimer"):
        raise HTTPException(status_code=400, detail="Invalid document type")
    
    try:
        conn = sqlite3.connect(str(DB_PATH))
        c = conn.cursor()
        c.execute("SELECT content FROM legal_documents WHERE doc_type = ?", (doc_type,))
        row = c.fetchone()
        conn.close()
        
        if not row:
            return {"doc_type": doc_type, "content": ""}
        return {"doc_type": doc_type, "content": row[0]}
    except Exception as e:
        return {"doc_type": doc_type, "content": "", "error": str(e)}


@content_router.post("/legal/{doc_type}")
async def save_legal_document(doc_type: str, body: dict):
    """Save legal document content."""
    if doc_type not in ("terms", "privacy", "disclaimer"):
        raise HTTPException(status_code=400, detail="Invalid document type")
    
    content = body.get("content", "")
    
    try:
        conn = sqlite3.connect(str(DB_PATH))
        c = conn.cursor()
        
        # Create table if it doesn't exist
        c.execute("""
            CREATE TABLE IF NOT EXISTS legal_documents (
                doc_type TEXT PRIMARY KEY,
                content TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Insert or update
        c.execute("SELECT 1 FROM legal_documents WHERE doc_type = ?", (doc_type,))
        exists = c.fetchone()
        
        if exists:
            c.execute("""
                UPDATE legal_documents 
                SET content = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE doc_type = ?
            """, (content, doc_type))
        else:
            c.execute("""
                INSERT INTO legal_documents (doc_type, content)
                VALUES (?, ?)
            """, (doc_type, content))
        
        conn.commit()
        conn.close()
        return {"status": "ok", "doc_type": doc_type, "saved": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
