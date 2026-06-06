<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Identify Your Ammonite - AmmoniteID</title>
    <script src="/static/tier-gates.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/@tensorflow/tfjs@4.20.0/dist/tf.min.js"></script>
    <script src="/static/offline-engine.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        :root {
            --cream: #F5F1E8; --dark-brown: #5D4E3A; --stone: #8B7355;
            --deep-green: #2c5f2d; --light-green: #4a7c59; --accent-blue: #4A90A4;
            --dark-text: #1a1a1a; --light-text: #666; --success: #6FA876; --error: #C85555;
            --shadow: 0 8px 32px rgba(0,0,0,0.12); --shadow-sm: 0 2px 8px rgba(0,0,0,0.08);
        }
        html, body { height: 100%; font-family: 'Georgia','Merriweather',serif; color: var(--dark-text); background-image: url('background.jpg'); background-size: cover; background-attachment: fixed; background-position: center; }

        nav {
            position: sticky; top: 0;
            background: rgba(255,255,255,0.97); backdrop-filter: blur(10px);
            padding: 1.2rem 2rem; box-shadow: var(--shadow-sm); z-index: 1000;
        }
        .nav-container { max-width: 1200px; margin: 0 auto; display: flex; justify-content: space-between; align-items: center; }
        .logo { font-size: 1.8rem; font-weight: bold; color: #2c5f2d; text-decoration: none; flex-shrink: 0; }
        .nav-links { display: flex; gap: 2rem; list-style: none; }
        .nav-links a { color: #5D4E3A; text-decoration: none; font-size: 1.2rem; transition: all 0.3s; font-weight: bold; font-family: 'Arial',sans-serif; padding-bottom: 3px; border-bottom: 3px solid transparent; }
        .nav-links a:hover, .nav-links a.active { color: #2c5f2d; border-bottom: 3px solid #2c5f2d; }
        .auth-buttons { display: flex; gap: 1rem; align-items: center; }
        .btn-outline { padding: 0.6rem 1.5rem; border: 2px solid #2c5f2d; background: linear-gradient(135deg, #2c5f2d 0%, #1e4620 100%); color: white; border-radius: 8px; text-decoration: none; font-family: 'Arial',sans-serif; font-size: 1.1rem; font-weight: bold; transition: all 0.3s; cursor: pointer; box-shadow: 0 2px 8px rgba(44,95,45,0.3); }
        .btn-outline:hover { transform: translateY(-2px); }
        .hamburger-btn { display: none; }
        .mobile-menu { display: none; }
        @media (max-width: 768px) {
            nav { padding: 0.6rem 1rem; position: relative; }
            .nav-container { flex-wrap: nowrap; gap: 0.5rem; }
            .logo { font-size: 1.2rem; }
            .nav-links { display: none !important; }
            .auth-buttons .btn-outline { padding: 0.35rem 0.7rem; font-size: 0.8rem; }
            .auth-buttons { gap: 0.4rem; }
            .hamburger-btn { display: flex !important; flex-direction: column; justify-content: center; gap: 5px; background: none; border: none; cursor: pointer; padding: 6px; margin-left: 6px; flex-shrink: 0; }
            .hamburger-btn span { display: block; width: 22px; height: 2.5px; background: #2c5f2d; border-radius: 2px; transition: all 0.3s ease; }
            .hamburger-btn.open span:nth-child(1) { transform: rotate(45deg) translate(5px, 8px); }
            .hamburger-btn.open span:nth-child(2) { opacity: 0; }
            .hamburger-btn.open span:nth-child(3) { transform: rotate(-45deg) translate(5px, -8px); }
            .mobile-menu { display: none; flex-direction: column; position: absolute; top: 100%; left: 0; right: 0; background: rgba(255,255,255,0.99); box-shadow: 0 6px 16px rgba(0,0,0,0.12); z-index: 1050; padding: 0.3rem 0; }
            .mobile-menu.open { display: flex !important; }
            .mobile-menu a, .mobile-menu button { padding: 0.85rem 1.5rem; color: #5D4E3A; text-decoration: none; font-family: 'Arial',sans-serif; font-weight: bold; font-size: 0.95rem; border: none; background: none; text-align: left; cursor: pointer; border-bottom: 1px solid #f0ece4; display: block; width: 100%; }
            .mobile-menu a:hover, .mobile-menu button:hover { background: #f5f1e8; color: #2c5f2d; }
        }
        .container { max-width: 900px; margin: 0 auto; padding: 2rem; }
        .upload-section { background: linear-gradient(135deg, rgba(255,255,255,0.98) 0%, rgba(248,250,252,0.95) 100%); border-radius: 20px; padding: 3rem; box-shadow: var(--shadow); margin-bottom: 2rem; border: 2px solid rgba(44,95,45,0.1); animation: fadeInUp 0.6s ease-out 0.1s both; }
        .upload-area { border: 3px dashed #2c5f2d; border-radius: 16px; padding: 3rem 2rem; text-align: center; background: linear-gradient(135deg, rgba(44,95,45,0.03) 0%, rgba(255,255,255,0.95) 100%); }
        .upload-icon { font-size: 3rem; margin-bottom: 1rem; }
        .upload-area h3 { font-size: 1.5rem; color: #2c5f2d; margin-bottom: 0.5rem; font-weight: bold; }
        .upload-area p { color: #1a1a1a; font-family: 'Arial',sans-serif; font-size: 1.1rem; margin-bottom: 1.5rem; font-weight: bold; }
        .upload-buttons { display: flex; gap: 1rem; justify-content: center; flex-wrap: wrap; }
        .btn { padding: 1.2rem 2.5rem; border: none; border-radius: 25px; font-family: 'Arial',sans-serif; font-size: 1.15rem; font-weight: bold; cursor: pointer; transition: all 0.3s ease; display: inline-flex; align-items: center; gap: 0.5rem; }
        .btn-primary { background: #2c5f2d; color: white; }
        .btn-primary:hover:not(:disabled) { background: #1e4620; transform: translateY(-2px); }
        .btn-secondary { background: var(--accent-blue); color: white; }
        .btn-secondary:hover:not(:disabled) { background: #3a7a8f; transform: translateY(-2px); }
        .btn:disabled { opacity: 0.45; cursor: not-allowed; transform: none !important; }
        .file-input { display: none; }
        .preview-section { margin-top: 2rem; }
        .preview-section h3 { font-size: 1.2rem; color: var(--dark-brown); margin-bottom: 1.5rem; display: flex; align-items: center; gap: 0.5rem; }
        .preview-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 1.5rem; margin-bottom: 1.5rem; }
        .preview-item { position: relative; border-radius: 12px; overflow: hidden; box-shadow: var(--shadow-sm); animation: scaleIn 0.3s ease-out; }
        .preview-item img { width: 100%; height: 150px; object-fit: cover; display: block; }
        .preview-remove { position: absolute; top: 8px; right: 8px; background: rgba(200,85,85,0.9); color: white; border: none; border-radius: 50%; width: 32px; height: 32px; cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 1.2rem; transition: all 0.3s; opacity: 0; }
        .preview-item:hover .preview-remove, .preview-item .preview-remove { opacity: 1; }
        .action-buttons { display: flex; justify-content: space-between; gap: 1rem; flex-wrap: wrap; margin-bottom: 2rem; }
        .action-buttons .btn { padding: 1.4rem 3rem; font-size: 1.25rem; font-weight: bold; }
        .btn-reset { background: #dc3545; color: white; border: none; margin-left: auto; }
        .btn-reset:hover:not(:disabled) { background: #c82333; }
        .progress-indicator { text-align: center; padding: 2rem; margin: 2rem 0; }
        .spinner { width: 40px; height: 40px; margin: 0 auto 1rem; border: 3px solid rgba(139,115,85,0.2); border-top: 3px solid var(--stone); border-radius: 50%; animation: spin 1s linear infinite; }
        .results-section { display: none; background: white; border-radius: 16px; padding: 2.5rem; box-shadow: var(--shadow); animation: fadeInUp 0.6s ease-out; }
        .results-section.show { display: block; }
        .results-header { text-align: center; margin-bottom: 2rem; padding-bottom: 1.5rem; border-bottom: 2px solid #e8dcc8; }
        .results-header h2 { font-size: 2rem; color: var(--dark-brown); margin-bottom: 0.5rem; }
        .family-result { background: linear-gradient(135deg, rgba(44,95,45,0.05) 0%, rgba(139,115,85,0.05) 100%); padding: 1.5rem; border-radius: 12px; margin-bottom: 2rem; border-left: 4px solid var(--deep-green); }
        .confidence-badge { display: inline-block; background: var(--success); color: white; padding: 0.8rem 1.8rem; border-radius: 25px; font-size: 1.2rem; font-weight: bold; font-family: 'Arial',sans-serif; margin-bottom: 1rem; }
        .genus-breakdown { margin-top: 1.5rem; }
        .genus-item { margin-bottom: 1.2rem; }
        .genus-label { display: flex; justify-content: space-between; margin-bottom: 0.5rem; font-family: 'Arial',sans-serif; font-size: 0.95rem; }
        .genus-item.best-match { background: linear-gradient(135deg, rgba(44,95,45,0.08) 0%, rgba(255,255,255,0.5) 100%); border-left: 4px solid #2c5f2d; padding-left: 1rem; margin-left: -1rem; }
        .progress-bar { height: 8px; background: #e8dcc8; border-radius: 4px; overflow: hidden; }
        .progress-fill { height: 100%; background: linear-gradient(90deg, var(--stone) 0%, var(--deep-green) 100%); transition: width 0.4s ease; border-radius: 4px; }
        .camera-modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.97); z-index: 10000; flex-direction: column; justify-content: center; align-items: center; gap: 0; }
        .camera-modal.active { display: flex; }
        .camera-header { width: 100%; max-width: 640px; background: rgba(255,255,255,0.08); padding: 10px 16px; border-radius: 12px 12px 0 0; display: flex; align-items: center; justify-content: space-between; }
        .camera-header-title { color: white; font-family: 'Arial',sans-serif; font-size: 0.9rem; font-weight: bold; }
        .camera-tip { color: #aaa; font-family: 'Arial',sans-serif; font-size: 0.78rem; }
        .camera-video-wrap { position: relative; width: 100%; max-width: 640px; background: #000; }
        #cameraVideo { width: 100%; display: block; max-height: 55vh; object-fit: cover; }
        .zoom-badge { position: absolute; top: 10px; left: 10px; background: rgba(0,0,0,0.55); color: white; font-family: 'Arial',sans-serif; font-size: 0.85rem; font-weight: bold; padding: 4px 10px; border-radius: 20px; pointer-events: none; }
        .zoom-panel { width: 100%; max-width: 640px; background: rgba(255,255,255,0.06); padding: 12px 20px; display: flex; align-items: center; gap: 12px; }
        .zoom-icon { font-size: 1rem; color: #aaa; flex-shrink: 0; }
        .zoom-slider { flex: 1; -webkit-appearance: none; appearance: none; height: 4px; border-radius: 4px; background: linear-gradient(90deg, #2c5f2d 0%, #4a7c59 100%); outline: none; cursor: pointer; }
        .zoom-slider::-webkit-slider-thumb { -webkit-appearance: none; appearance: none; width: 22px; height: 22px; border-radius: 50%; background: white; cursor: pointer; box-shadow: 0 2px 6px rgba(0,0,0,0.4); }
        .zoom-value { color: white; font-family: 'Arial',sans-serif; font-size: 0.9rem; font-weight: bold; min-width: 30px; text-align: right; flex-shrink: 0; }
        .camera-controls { width: 100%; max-width: 640px; background: rgba(255,255,255,0.06); padding: 14px 20px; border-radius: 0 0 12px 12px; display: flex; gap: 12px; justify-content: center; }
        .camera-controls .btn { padding: 1rem 1.8rem; font-size: 1rem; border-radius: 20px; }
        .login-modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); z-index: 9999; justify-content: center; align-items: center; }
        .login-modal.show { display: flex; }
        .login-modal-content { background: white; border-radius: 20px; padding: 40px; max-width: 450px; width: 90%; text-align: center; box-shadow: var(--shadow); }
        .login-modal-icon { font-size: 60px; margin-bottom: 20px; }
        .login-modal-title { color: #2c5f2d; font-size: 24px; font-weight: 700; margin-bottom: 10px; }
        .login-modal-message { color: #666; font-size: 16px; margin-bottom: 30px; line-height: 1.5; font-family: 'Arial',sans-serif; }
        .login-modal-buttons { display: flex; gap: 10px; justify-content: center; flex-wrap: wrap; }
        .modal-btn { padding: 12px 24px; border-radius: 10px; font-family: 'Arial',sans-serif; font-weight: bold; cursor: pointer; text-decoration: none; border: none; font-size: 15px; transition: all 0.3s; flex: 1; min-width: 100px; text-align: center; }
        .modal-btn-green { background: linear-gradient(135deg, #2c5f2d 0%, #1e4620 100%); color: white; }
        .modal-btn-grey { background: #f0f0f0; color: #333; }
        .modal-btn-outline { background: white; color: #2c5f2d; border: 2px solid #2c5f2d; }
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes fadeInUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes scaleIn { from { opacity: 0; transform: scale(0.9); } to { opacity: 1; transform: scale(1); } }
        @media (max-width: 768px) {
            .container { padding: 1rem; }
            .upload-section { padding: 1.5rem; }
            .upload-area { padding: 2rem 1rem; }
            .upload-area h3 { font-size: 1.2rem; }
            .upload-area p { font-size: 0.95rem; }
            .upload-buttons { flex-direction: column; align-items: stretch; gap: 0.8rem; }
            .btn { padding: 1rem 1.5rem; font-size: 1rem; border-radius: 14px; width: 100%; justify-content: center; }
            .preview-grid { grid-template-columns: repeat(auto-fill, minmax(100px, 1fr)); gap: 0.8rem; }
            .preview-item img { height: 110px; }
            .action-buttons { flex-direction: column; gap: 0.8rem; }
            .action-buttons .btn { padding: 1rem; font-size: 1.1rem; width: 100%; margin-left: 0; }
            .results-section { padding: 1.5rem; }
            .results-header h2 { font-size: 1.4rem; }
            .confidence-badge { font-size: 1rem; padding: 0.6rem 1.2rem; }
            .genus-label { font-size: 0.85rem; }
            #cameraVideo { max-height: 45vh; }
        }
    </style>
</head>
<body>

<div id="loginModal" class="login-modal">
    <div class="login-modal-content">
        <div class="login-modal-icon">🔐</div>
        <div class="login-modal-title">Login Required</div>
        <div class="login-modal-message">Please log in or sign up to identify fossils.</div>
        <div class="login-modal-buttons">
            <a href="/static/home.html" class="modal-btn modal-btn-outline">🏠 Home</a>
            <a href="/static/login.html" class="modal-btn modal-btn-green">Log In</a>
            <a href="/static/login.html" class="modal-btn modal-btn-grey">Sign Up</a>
        </div>
    </div>
</div>

<nav>
    <div class="nav-container">
        <a href="/static/home.html" class="logo">AmmoniteID</a>
        <ul class="nav-links">
            <li><a href="/static/home.html">Home</a></li>
            <li><a href="/static/test.html" class="active">Identify</a></li>
            <li><a href="/static/mylog.html">My Fossil Collection</a></li>
            <li><a href="/static/about.html">About</a></li>
            <li><a href="/static/contact.html">Contact</a></li>
            <li><a href="/static/partners.html">Partners</a></li>
        </ul>
        <div class="auth-buttons" id="authButtons">
            <a href="/static/login.html" class="btn-outline">Log In</a>
            <a href="/static/login.html" class="btn-outline">Sign Up</a>
        </div>
        <button class="hamburger-btn" id="hamburgerBtn" aria-label="Menu">
            <span></span><span></span><span></span>
        </button>
    </div>
    <div class="mobile-menu" id="mobileMenu">
        <a href="/static/home.html">🏠 Home</a>
        <a href="/static/test.html">🔍 Identify</a>
        <a href="/static/mylog.html">📚 My Fossil Collection</a>
        <a href="/static/about.html">ℹ️ About</a>
        <a href="/static/contact.html">📬 Contact</a>
        <a href="/static/partners.html">🤝 Partners</a>
        <div id="mobileAuthLinks">
            <a href="/static/login.html">🔑 Log In</a>
            <a href="/static/login.html">✏️ Sign Up</a>
        </div>
    </div>
</nav>

<div id="partner-ad-banner"></div>

<div class="container">
    <div id="premiumWarning" style="display:none;margin-bottom:1.5rem;padding:16px 20px;border-radius:12px;background:linear-gradient(135deg,#fff3cd,#ffe8b6);border-left:5px solid #ff9800;font-family:Arial;">
        <div style="font-size:1rem;font-weight:bold;color:#333;margin-bottom:8px;">⚠️ Premium Feature Not Activated</div>
        <p style="color:#555;margin:0 0 12px 0;font-size:0.95rem;">You have Premium access but haven't downloaded the offline model yet.</p>
        <button onclick="document.getElementById('offlineDownloadSection').scrollIntoView({behavior:'smooth'})" style="padding:8px 16px;background:#ff9800;color:white;border:none;border-radius:6px;font-weight:bold;cursor:pointer;">⬇️ Activate Now</button>
    </div>
    <div id="offlineBar" style="display:none;margin-bottom:1.5rem;padding:14px 18px;border-radius:12px;font-family:Arial;font-size:0.95rem;"></div>
    <div id="offlineDownloadSection" style="display:none;margin-bottom:1.5rem;text-align:center;background:white;border-radius:12px;padding:20px;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
        <button id="downloadModelBtn" onclick="startOfflineDownload()" style="padding:12px 24px;background:linear-gradient(135deg,#f39c12,#e67e22);color:#fff;border:none;border-radius:10px;font-size:1rem;font-weight:bold;cursor:pointer;">⬇️ Enable Offline Mode</button>
        <p style="font-size:0.85rem;color:#999;margin-top:8px;">One-time download (8.5MB)</p>
        <div id="downloadProgress" style="display:none;margin-top:10px;">
            <div style="background:#e0e0e0;border-radius:8px;height:8px;overflow:hidden;"><div id="downloadBar" style="background:#e67e22;height:100%;width:0%;transition:width 0.3s;"></div></div>
            <p id="downloadStatus" style="font-size:0.85rem;color:#666;margin-top:5px;">Downloading...</p>
        </div>
    </div>
    <div class="upload-section">
        <div class="upload-area" id="uploadArea">
            <div class="upload-icon">📸</div>
            <h3>Upload or Capture Photos</h3>
            <p>Use up to 3 photos for best results</p>
            <div class="upload-buttons">
                <button class="btn btn-primary" id="captureBtn">📷 Take a Photo</button>
                <button class="btn btn-secondary" id="uploadBtn">📤 Upload Photo</button>
            </div>
            <input type="file" id="fileInput" class="file-input" accept="image/*" multiple>
        </div>
        <div class="preview-section" id="previewSection" style="display:none;">
            <h3>📷 Selected Photos (<span id="photoCount">0</span>/3)</h3>
            <div class="preview-grid" id="previewGrid"></div>
        </div>
    </div>
    <div class="action-buttons">
        <button class="btn btn-primary" id="submitBtn" disabled>🔍 Identify Fossil</button>
        <button class="btn btn-reset" id="resetBtn" disabled>🔄 Clear Photos</button>
    </div>
    <div class="progress-indicator" id="progressIndicator" style="display:none;">
        <div class="spinner"></div>
        <p class="progress-text">Analysing your photos...</p>
    </div>
    <div class="results-section" id="resultsSection">
        <div class="results-header"><h2>✓ Identification Complete</h2></div>
        <div class="family-result">
            <h3 id="topFamily"></h3>
            <div class="confidence-badge">Confidence: <span id="familyConfidence"></span></div>
            <p id="familyDescription" style="color:var(--light-text);font-family:Arial;margin-top:0.5rem;"></p>
            <div class="genus-breakdown"><div id="genusBreakdown"></div></div>
        </div>
    </div>
</div>

<div id="cameraModal" class="camera-modal">
    <div class="camera-header">
        <span class="camera-header-title">📷 Camera</span>
        <span class="camera-tip">💡 Tap screen to focus</span>
    </div>
    <div class="camera-video-wrap">
        <video id="cameraVideo" autoplay playsinline></video>
        <div class="zoom-badge" id="zoomBadge">1.0x</div>
    </div>
    <div class="zoom-panel">
        <span class="zoom-icon">🔍</span>
        <input type="range" class="zoom-slider" id="zoomSlider" min="1" max="5" step="0.1" value="1">
        <span class="zoom-value" id="zoomValue">1x</span>
    </div>
    <div class="camera-controls">
        <button class="btn btn-primary" onclick="capturePhoto()">📸 Capture</button>
        <button class="btn btn-reset" onclick="closeCamera()">✕ Cancel</button>
    </div>
</div>
<canvas id="canvas" style="display:none;"></canvas>

<style>
    #partner-ad-banner { position:sticky;top:70px;z-index:99;overflow:hidden;height:160px;box-shadow:0 4px 8px rgba(0,0,0,0.1);transform:translateY(-110%);opacity:0; }
    .banner-in  { animation: bannerSlideIn  0.6s cubic-bezier(0.22,1,0.36,1) forwards; }
    .banner-out { animation: bannerSlideOut 0.4s ease forwards; }
    @keyframes bannerSlideIn  { from{transform:translateY(-110%);opacity:0;} to{transform:translateY(0);opacity:1;} }
    @keyframes bannerSlideOut { from{transform:translateY(0);opacity:1;} to{transform:translateY(-110%);opacity:0;} }
    .ad-content { position:relative;display:flex;justify-content:space-between;align-items:center;padding:0 2rem;height:160px;white-space:nowrap;overflow:hidden; }
    .ad-left { display:flex;align-items:center;gap:0;flex:1;min-width:0;overflow:hidden; }
    .ad-partner-name { font-size:1.1rem;font-weight:bold;color:#1a1a1a;text-decoration:none;cursor:pointer;flex-shrink:0;transition:all 0.2s; }
    .ad-partner-name:hover { text-decoration:underline;color:#2c5f2d; }
    .ad-bar { color:#ccc;padding:0 10px;flex-shrink:0; }
    .ad-detail { font-size:0.9rem;color:#444;font-family:Arial,sans-serif;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex-shrink:1; }
    .ad-detail a { color:#2c5f2d;text-decoration:none; }
    .ad-offer { font-size:0.85rem;color:#2c5f2d;font-weight:bold;background:rgba(255,255,255,0.85);padding:2px 8px;border-radius:4px;white-space:nowrap;flex-shrink:0;margin-left:10px; }
    .ad-more-info { padding:0.5rem 1.2rem;background:#2c5f2d;color:white;text-decoration:none;border-radius:6px;font-family:Arial,sans-serif;font-size:0.9rem;font-weight:bold;transition:all 0.3s;white-space:nowrap;flex-shrink:0;margin-left:1rem; }
    .ad-more-info:hover { background:#1e4620; }
    @media (max-width:768px) {
        #partner-ad-banner { height:100px; top:52px; }
        .ad-content { padding:0.6rem 1rem;height:100px; }
        .ad-detail { display:none; }
        .ad-more-info { font-size:0.8rem;padding:0.4rem 0.8rem; }
    }
</style>

<script>
    const hamburgerBtn = document.getElementById('hamburgerBtn');
    const mobileMenu = document.getElementById('mobileMenu');
    if (hamburgerBtn) {
        hamburgerBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            hamburgerBtn.classList.toggle('open');
            mobileMenu.classList.toggle('open');
        });
        mobileMenu.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', () => {
                hamburgerBtn.classList.remove('open');
                mobileMenu.classList.remove('open');
            });
        });
        document.addEventListener('click', function(e) {
            if (!mobileMenu.contains(e.target) && !hamburgerBtn.contains(e.target)) {
                hamburgerBtn.classList.remove('open');
                mobileMenu.classList.remove('open');
            }
        });
    }
</script>

<script type="module">
    import { initializeApp } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-app.js";
    import { getAuth, onAuthStateChanged, signOut } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-auth.js";
    const firebaseConfig = { apiKey:"AIzaSyChXqOpXgpkLrn44mfIcPoTVPBk6neicBQ", authDomain:"ammoniteid-f9d8e.firebaseapp.com", projectId:"ammoniteid-f9d8e", storageBucket:"ammoniteid-f9d8e.firebasestorage.app", messagingSenderId:"828376677091", appId:"1:828376677091:web:e302f3ff538b78bc83e3d6" };
    const app = initializeApp(firebaseConfig);
    const auth = getAuth(app);
    onAuthStateChanged(auth, async (user) => {
        const authButtons = document.getElementById('authButtons');
        const mobileAuthLinks = document.getElementById('mobileAuthLinks');
        const loginModal = document.getElementById('loginModal');
        const uploadArea = document.getElementById('uploadArea');
        if (user) {
            localStorage.setItem('ammonite_user_id', user.uid);
            authButtons.innerHTML = `<a href="/static/my-account.html" class="btn-outline" style="font-size:0.95rem;padding:0.5rem 1rem;">👤 My Account</a><button class="btn-outline" style="font-size:0.9rem;padding:0.5rem 1rem;" onclick="handleLogout()">🚪 Log Out</button>`;
            mobileAuthLinks.innerHTML = `<a href="/static/my-account.html">👤 My Account</a><button onclick="handleLogout()">🚪 Log Out</button>`;
            loginModal.classList.remove('show');
            uploadArea.style.pointerEvents = 'auto';
            uploadArea.style.opacity = '1';
            await refreshTierAndApplyNav(user.uid);
        } else {
            localStorage.removeItem('ammonite_user_id');
            authButtons.innerHTML = `<a href="/static/login.html" class="btn-outline">Log In</a><a href="/static/login.html" class="btn-outline">Sign Up</a>`;
            mobileAuthLinks.innerHTML = `<a href="/static/login.html">🔑 Log In</a><a href="/static/login.html">✏️ Sign Up</a>`;
            loginModal.classList.add('show');
            uploadArea.style.pointerEvents = 'none';
            uploadArea.style.opacity = '0.5';
            applyNavForTier('FREE');
        }
    });
    window.handleLogout = async function() { try { await signOut(auth); window.location.href='/static/home.html'; } catch(e) { alert('Error logging out.'); } };
</script>

<script>
    const fileInput = document.getElementById('fileInput');
    const captureBtn = document.getElementById('captureBtn');
    const uploadBtn = document.getElementById('uploadBtn');
    const previewSection = document.getElementById('previewSection');
    const previewGrid = document.getElementById('previewGrid');
    const photoCount = document.getElementById('photoCount');
    const submitBtn = document.getElementById('submitBtn');
    const resetBtn = document.getElementById('resetBtn');
    const zoomSlider = document.getElementById('zoomSlider');
    const zoomValue = document.getElementById('zoomValue');
    const zoomBadge = document.getElementById('zoomBadge');

    let selectedFiles = [];
    const MAX_PHOTOS = 3;
    let cameraStream = null;
    let photosFromCamera = false;
    let currentZoom = 1;

    captureBtn.addEventListener('click', openCamera);
    uploadBtn.addEventListener('click', () => fileInput.click());

    async function openCamera() {
        if (selectedFiles.length >= MAX_PHOTOS) return;
        try {
            const constraints = { video: { facingMode:'environment', width:{ideal:1920}, height:{ideal:1080} } };
            cameraStream = await navigator.mediaDevices.getUserMedia(constraints);
            document.getElementById('cameraVideo').srcObject = cameraStream;
            const track = cameraStream.getVideoTracks()[0];
            const caps = track.getCapabilities ? track.getCapabilities() : {};
            if (caps.zoom) {
                zoomSlider.min = caps.zoom.min;
                zoomSlider.max = caps.zoom.max;
                zoomSlider.step = caps.zoom.step || 0.1;
            } else {
                zoomSlider.min = 1; zoomSlider.max = 5; zoomSlider.step = 0.1;
            }
            zoomSlider.value = currentZoom;
            applyZoom(currentZoom);
            document.getElementById('cameraModal').classList.add('active');
        } catch(error) {
            alert('Camera access denied: ' + error.message);
        }
    }

    function closeCamera() {
        if (cameraStream) { cameraStream.getTracks().forEach(t => t.stop()); cameraStream = null; }
        document.getElementById('cameraVideo').srcObject = null;
        document.getElementById('cameraModal').classList.remove('active');
    }

    zoomSlider.addEventListener('input', () => {
        currentZoom = parseFloat(zoomSlider.value);
        applyZoom(currentZoom);
    });

    function applyZoom(zoom) {
        const label = zoom.toFixed(1) + 'x';
        zoomValue.textContent = label;
        zoomBadge.textContent = label;
        const track = cameraStream && cameraStream.getVideoTracks()[0];
        const caps = track && track.getCapabilities ? track.getCapabilities() : {};
        if (caps.zoom) {
            track.applyConstraints({ advanced: [{ zoom }] }).catch(() => {});
        } else {
            document.getElementById('cameraVideo').style.transform = `scale(${zoom})`;
            document.getElementById('cameraVideo').style.transformOrigin = 'center center';
        }
    }

    document.getElementById('cameraVideo').addEventListener('click', function(e) {
        const track = cameraStream && cameraStream.getVideoTracks()[0];
        const caps = track && track.getCapabilities ? track.getCapabilities() : {};
        if (caps.focusMode && caps.focusMode.includes('manual')) {
            const rect = this.getBoundingClientRect();
            const x = (e.clientX - rect.left) / rect.width;
            const y = (e.clientY - rect.top) / rect.height;
            track.applyConstraints({ advanced:[{ focusMode:'manual', pointsOfInterest:[{x,y}] }] }).catch(()=>{});
        }
    });

    function capturePhoto() {
        const video = document.getElementById('cameraVideo');
        const canvas = document.getElementById('canvas');
        const ctx = canvas.getContext('2d');
        const vw = video.videoWidth;
        const vh = video.videoHeight;
        const track = cameraStream && cameraStream.getVideoTracks()[0];
        const caps = track && track.getCapabilities ? track.getCapabilities() : {};
        const useHardwareZoom = !!caps.zoom;
        if (!useHardwareZoom && currentZoom > 1) {
            const cropW = vw / currentZoom;
            const cropH = vh / currentZoom;
            const cropX = (vw - cropW) / 2;
            const cropY = (vh - cropH) / 2;
            canvas.width = cropW;
            canvas.height = cropH;
            ctx.drawImage(video, cropX, cropY, cropW, cropH, 0, 0, cropW, cropH);
        } else {
            canvas.width = vw;
            canvas.height = vh;
            ctx.drawImage(video, 0, 0);
        }
        canvas.toBlob((blob) => {
            const file = new File([blob], `camera_${Date.now()}.jpg`, {type:'image/jpeg'});
            selectedFiles.push(file);
            photosFromCamera = true;
            updatePreview();
            closeCamera();
        }, 'image/jpeg', 0.95);
    }

    window.capturePhoto = capturePhoto;
    window.closeCamera = closeCamera;

    fileInput.addEventListener('change', (e) => {
        const newFiles = Array.from(e.target.files);
        selectedFiles = [...selectedFiles, ...newFiles].slice(0, MAX_PHOTOS);
        if (newFiles.length + selectedFiles.length > MAX_PHOTOS) alert(`Maximum ${MAX_PHOTOS} photos. Extras removed.`);
        photosFromCamera = false;
        updatePreview();
        fileInput.value = '';
    });

    const uploadArea = document.getElementById('uploadArea');
    uploadArea.addEventListener('dragover', e => { e.preventDefault(); uploadArea.style.borderColor='#1e4620'; });
    uploadArea.addEventListener('dragleave', () => { uploadArea.style.borderColor='#2c5f2d'; });
    uploadArea.addEventListener('drop', e => {
        e.preventDefault(); uploadArea.style.borderColor='#2c5f2d';
        const newFiles = Array.from(e.dataTransfer.files).filter(f => f.type.startsWith('image/'));
        selectedFiles = [...selectedFiles, ...newFiles].slice(0, MAX_PHOTOS);
        updatePreview();
    });

    function updatePreview() {
        photoCount.textContent = selectedFiles.length;
        if (selectedFiles.length === 0) {
            previewSection.style.display = 'none';
            submitBtn.disabled = true; resetBtn.disabled = true;
            captureBtn.textContent = '📷 Take a Photo';
            uploadBtn.textContent = '📤 Upload Photo';
            captureBtn.disabled = false; uploadBtn.disabled = false;
            return;
        }
        previewSection.style.display = 'block';
        submitBtn.disabled = false; resetBtn.disabled = false;
        if (selectedFiles.length >= MAX_PHOTOS) {
            captureBtn.textContent = '📷 Max 3 Reached'; captureBtn.disabled = true;
            uploadBtn.textContent = '📤 Max 3 Reached'; uploadBtn.disabled = true;
        } else {
            captureBtn.textContent = '📷 Take Another Photo'; captureBtn.disabled = false;
            uploadBtn.textContent = '📤 Upload Another Photo'; uploadBtn.disabled = false;
        }
        previewGrid.innerHTML = '';
        selectedFiles.forEach((file, idx) => {
            const reader = new FileReader();
            reader.onload = e => {
                const div = document.createElement('div');
                div.className = 'preview-item';
                div.innerHTML = `<img src="${e.target.result}" alt="Photo ${idx+1}"><button class="preview-remove" onclick="removeFile(${idx})">✕</button>`;
                previewGrid.appendChild(div);
            };
            reader.readAsDataURL(file);
        });
    }

    window.removeFile = idx => {
        selectedFiles.splice(idx, 1);
        if (!selectedFiles.length) photosFromCamera = false;
        updatePreview();
    };

    resetBtn.addEventListener('click', () => {
        selectedFiles = []; photosFromCamera = false; fileInput.value = '';
        updatePreview();
        document.getElementById('resultsSection').classList.remove('show');
        document.getElementById('progressIndicator').style.display = 'none';
        window.scrollTo({top:0, behavior:'smooth'});
    });
</script>

<script>
    document.getElementById('submitBtn').addEventListener('click', async () => {
        if (!selectedFiles.length) return;
        const userId = localStorage.getItem('ammonite_user_id');
        if (!userId) { document.getElementById('loginModal').classList.add('show'); return; }

        const progressIndicator = document.getElementById('progressIndicator');
        const resultsSection = document.getElementById('resultsSection');
        const submitBtn = document.getElementById('submitBtn');
        progressIndicator.style.display = 'block';
        resultsSection.classList.remove('show');
        submitBtn.disabled = true;

        try {
            let result;
            const isOffline = !navigator.onLine;
            if (isOffline && window.offlineReady && window.offlineReady()) {
                progressIndicator.querySelector('p').textContent = '🔍 Identifying offline...';
                result = await window.identifyOffline(selectedFiles);
                result.family_confidence = result.top_family_score;
            } else if (isOffline) {
                throw new Error('NO_SIGNAL');
            } else {
                const formData = new FormData();
                selectedFiles.forEach(f => formData.append('photos', f));
                formData.append('user_id', userId);
                const response = await fetch('/identify', {method:'POST', body:formData});
                if (!response.ok) throw new Error(`API error: ${response.status}`);
                result = await response.json();
            }

            const identification_id = result.identification_id || String(Date.now());
            const familyConf = result.family_confidence || 0;
            const feedbackMsg = photosFromCamera ? (result.feedback_message || '') : '';

            // Display results based on scenario
            if (result.scenario === 'non_ammonite') {
                const c = result.non_am_total || 0;
                let lbl, prefix;
                if (c >= 80) { lbl = 'HIGH ✅'; prefix = 'Appears to be:'; }
                else if (c >= 60) { lbl = 'MODERATE ⚠️'; prefix = 'Possibly:'; }
                else if (c >= 30) { lbl = 'LOW ⚠️'; prefix = 'Best guess:'; }
                else { lbl = 'VERY LOW ❌'; prefix = 'Uncertain:'; }
                
                document.getElementById('topFamily').innerHTML = '<span style="font-size:1.8rem;font-weight:bold;">' + prefix + ' ' + (result.non_am_display || 'Not an ammonite') + '</span><br><span style="font-size:1.1rem;">[Confidence: ' + c + '% — ' + lbl + ']</span>';
                document.getElementById('familyConfidence').textContent = c + '%';
                if (feedbackMsg) {
                    document.getElementById('familyDescription').innerHTML = '<div style="margin-top:15px;padding:12px;background:#e3f2fd;border-left:4px solid #2196f3;border-radius:5px;font-family:Arial;">' + feedbackMsg + '</div>';
                } else {
                    document.getElementById('familyDescription').innerHTML = '';
                }
                document.getElementById('genusBreakdown').innerHTML = '<p style="color:var(--light-text);font-family:Arial;">No genus breakdown for non-ammonite specimens.</p>';

            } else if (result.scenario === 'uncertain') {
                document.getElementById('topFamily').innerHTML = '<span style="font-size:1.8rem;font-weight:bold;">Uncertain</span><br><span style="font-size:1.1rem;">[VERY LOW ❌ — ≤29%]</span>';
                document.getElementById('familyConfidence').textContent = '—';
                document.getElementById('familyDescription').innerHTML = '<div style="margin-top:15px;padding:12px;background:#fff3cd;border-left:4px solid #ff9800;border-radius:5px;font-family:Arial;">⚠️ Image too unclear for reliable identification. Please retake with fossil filling 80%+ of frame and even lighting.</div>';
                document.getElementById('genusBreakdown').innerHTML = '<p style="color:var(--light-text);font-family:Arial;">Cannot determine genus from this image.</p>';

            } else if (result.scenario === 'low') {
                const familyConfVal = result.top_family_score || 0;
                let lbl;
                if (familyConfVal >= 60) lbl = 'MODERATE ⚠️';
                else if (familyConfVal >= 30) lbl = 'LOW ⚠️';
                else lbl = 'VERY LOW ❌';
                
                document.getElementById('topFamily').innerHTML = '<span style="font-size:1.8rem;font-weight:bold;">Family: ' + (result.top_family || 'Unknown') + ' (Best Guess)</span><br><span style="font-size:1.1rem;">[' + familyConfVal + '% — ' + lbl + ']</span>';
                document.getElementById('familyConfidence').textContent = familyConfVal + '%';
                document.getElementById('familyDescription').innerHTML = '<div style="margin-top:15px;padding:12px;background:#fff3cd;border-left:4px solid #ff9800;border-radius:5px;font-family:Arial;">⚠️ Low confidence (' + familyConfVal + '%) - this is our best estimate<br><br>💡 For better results: fill 80%+ of frame with fossil, use even lighting, and ensure sharp focus</div>';
                
                const gb = document.getElementById('genusBreakdown');
                gb.innerHTML = '<h3 style="margin-bottom:1rem;color:var(--dark-brown);">Likely Genera (Best Guess)</h3>';
                if (result.genus_breakdown && result.genus_breakdown.length > 0) {
                    for (let i = 0; i < result.genus_breakdown.length; i++) {
                        const g = result.genus_breakdown[i];
                        const s = g.percentage || 0;
                        let cl;
                        if (s >= 80) cl = '<span style="color:#28a745;font-weight:bold;">HIGH ✅</span>';
                        else if (s >= 60) cl = '<span style="color:#ff9800;font-weight:bold;">MODERATE ⚠️</span>';
                        else if (s >= 30) cl = '<span style="color:#dc3545;font-weight:bold;">LOW ⚠️</span>';
                        else cl = '<span style="color:#999;font-weight:bold;">VERY LOW ❌</span>';
                        
                        gb.innerHTML += '<div class="genus-item ' + (i === 0 ? 'best-match' : '') + '"><div class="genus-label"><span style="' + (i === 0 ? 'font-weight:bold;font-size:1.1rem;' : '') + '">' + g.genus + '</span><span style="' + (i === 0 ? 'font-weight:bold;' : '') + '">' + s + '% — ' + (i === 0 ? 'Best Match' : 'Possible') + ' [' + cl + ']</span></div><div class="progress-bar"><div class="progress-fill" style="width:' + s + '%"></div></div></div>';
                    }
                }

            } else { // 'likely' or 'possible'
                const familyConfVal = result.top_family_score || 0;
                let lbl, wording;
                if (result.scenario === 'likely') {
                    lbl = familyConfVal >= 80 ? 'HIGH ✅' : 'MODERATE ⚠️';
                    wording = 'Likely';
                } else {
                    lbl = familyConfVal >= 60 ? 'MODERATE ⚠️' : 'LOW ⚠️';
                    wording = 'Possible';
                }
                
                document.getElementById('topFamily').innerHTML = '<span style="font-size:1.8rem;font-weight:bold;">Family: ' + (result.top_family || 'Unknown') + '</span><br><span style="font-size:1.1rem;">[' + wording + ' — ' + familyConfVal + '% — ' + lbl + ']</span>';
                document.getElementById('familyConfidence').textContent = familyConfVal + '%';
                if (feedbackMsg) {
                    document.getElementById('familyDescription').innerHTML = '<div style="margin-top:15px;padding:12px;background:#e3f2fd;border-left:4px solid #2196f3;border-radius:5px;font-family:Arial;">' + feedbackMsg + '</div>';
                } else {
                    document.getElementById('familyDescription').innerHTML = '';
                }
                
                const gb = document.getElementById('genusBreakdown');
                gb.innerHTML = '<h3 style="margin-bottom:1rem;color:var(--dark-brown);">Likely Genera</h3>';
                if (result.genus_breakdown && result.genus_breakdown.length > 0) {
                    for (let i = 0; i < result.genus_breakdown.length; i++) {
                        const g = result.genus_breakdown[i];
                        const s = g.percentage || 0;
                        let cl;
                        if (s >= 80) cl = '<span style="color:#28a745;font-weight:bold;">HIGH ✅</span>';
                        else if (s >= 60) cl = '<span style="color:#ff9800;font-weight:bold;">MODERATE ⚠️</span>';
                        else if (s >= 30) cl = '<span style="color:#dc3545;font-weight:bold;">LOW ⚠️</span>';
                        else cl = '<span style="color:#999;font-weight:bold;">VERY LOW ❌</span>';
                        
                        gb.innerHTML += '<div class="genus-item ' + (i === 0 ? 'best-match' : '') + '"><div class="genus-label"><span style="' + (i === 0 ? 'font-weight:bold;font-size:1.1rem;' : '') + '">' + g.genus + '</span><span style="' + (i === 0 ? 'font-weight:bold;' : '') + '">' + s + '% — ' + (i === 0 ? 'Best Match' : 'Possible') + ' [' + cl + ']</span></div><div class="progress-bar"><div class="progress-fill" style="width:' + s + '%"></div></div></div>';
                    }
                }
            }

            progressIndicator.style.display = 'none';
            resultsSection.classList.add('show');
            submitBtn.disabled = false;
            window.scrollTo({top: Math.max(0, resultsSection.offsetTop - 240), behavior:'smooth'});

            // Save to collection for PREMIUM+ users
            const userTier = (localStorage.getItem('ammonite_tier') || 'FREE').toUpperCase();
            if (window.tierAtLeast && window.tierAtLeast(userTier, 'PREMIUM')) try {
                const topGenus = result.genus_breakdown && result.genus_breakdown.length > 0 ? result.genus_breakdown[0].genus : 'Unknown';
                let saveFamily, saveGenus, saveConfidence;
                if (result.scenario === 'non_ammonite') {
                    saveFamily = result.non_am_display || result.top_non_am || 'Not an ammonite';
                    saveGenus = result.non_am_category || 'N/A';
                    saveConfidence = result.non_am_total || 0;
                } else if (result.scenario === 'uncertain') {
                    saveFamily = 'Uncertain';
                    saveGenus = 'Unknown';
                    saveConfidence = result.family_confidence || 0;
                } else {
                    saveFamily = result.top_family || 'Unknown';
                    saveGenus = topGenus;
                    saveConfidence = result.family_confidence || 0;
                }

                const fossils = JSON.parse(localStorage.getItem('ammoniteMyLogs') || '[]');
                let photoBase64 = '';
                if (selectedFiles.length > 0) {
                    photoBase64 = await new Promise(res => { const r = new FileReader(); r.onload = e => res(e.target.result); r.onerror = () => res(''); r.readAsDataURL(selectedFiles[0]); });
                }
                const localEntry = {
                    id: identification_id,
                    date: new Date().toISOString(),
                    family: saveFamily,
                    genus: saveGenus,
                    family_label: result.family_label || '',
                    confidence: saveConfidence,
                    photos: photoBase64 ? [photoBase64] : [],
                    genusBreakdown: result.genus_breakdown || [],
                    scenario: result.scenario || '',
                    notes: '',
                    favorite: false,
                    keepForever: false,
                    source: isOffline ? 'offline' : 'online'
                };
                fossils.unshift(localEntry);
                localStorage.setItem('ammoniteMyLogs', JSON.stringify(fossils));

                try {
                    await fetch('/api/collection/save', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            user_id: userId,
                            identification_id: identification_id,
                            family: saveFamily,
                            genus: saveGenus,
                            family_label: result.family_label || '',
                            confidence: saveConfidence,
                            scenario: result.scenario || '',
                            formatted_output: result.formatted_output || '',
                            genus_breakdown: result.genus_breakdown || [],
                            notes: ''
                        })
                    });
                } catch(e) { console.warn('DB save failed:', e.message); }
            } catch(e) { console.warn('Could not save to collection:', e); }

            try {
                const queue = JSON.parse(localStorage.getItem('ammoniteReviewQueue') || '[]');
                queue.unshift({id:Date.now(), date:new Date().toISOString(), family:saveFamily, confidence:saveConfidence, genus_breakdown:result.genus_breakdown||[], scenario:result.scenario||'', status:'pending', autoDeleteDate:new Date(Date.now()+30*24*60*60*1000).toISOString().split('T')[0]});
                localStorage.setItem('ammoniteReviewQueue', JSON.stringify(queue));
            } catch(e) { console.warn('Could not save to queue:', e); }

        } catch(error) {
            if (error.message === 'NO_SIGNAL') {
                alert('📵 No internet signal.\n\nTake photos now and identify when back online.\n\n⭐ Premium users can identify offline — upgrade to unlock!');
            } else {
                alert('Error identifying fossil. Please check your connection and try again.');
            }
            document.getElementById('progressIndicator').style.display = 'none';
            document.getElementById('submitBtn').disabled = false;
        }
    });
</script>

<script>
    let partners=[], bannerSlid=false;
    async function loadAdPartners() {
        try {
            const data = await (await fetch('/api/admin/partners')).json();
            partners = (data.partners||[]).filter(p=>p.status==='active'&&p.active).map(p=>({name:p.name,url:p.url,email:p.email||'',phone:p.phone||'',bgColor:p.bg_color,anchor:p.anchor||p.partner_id,description:p.description||'',offer:p.offer||'',logo_emoji:p.logo_emoji||'🏪',logo_path:p.logo_path||'',display_duration:(p.display_duration||15)*1000,rotation_weight:p.rotation_weight||1}));
            partners.length ? initializeAds() : (document.getElementById('partner-ad-banner').style.display='none');
        } catch { partners=[{name:"Lyme Regis Museum",url:"https://www.lymeregismuseum.co.uk",email:"info@lymeregismuseum.co.uk",phone:"+44 1297 443370",bgColor:"rgba(255,182,193,1.0)",anchor:"lyme-regis-museum",description:"Discover millions of years of history",offer:"",logo_emoji:"🏛️",logo_path:"",display_duration:15000,rotation_weight:1}]; initializeAds(); }
    }
    function showAd(index) {
        const banner=document.getElementById('partner-ad-banner'); if(!banner||!partners[index]) return;
        const p=partners[index]; const ex=banner.querySelector('.ad-content'); if(ex) ex.remove();
        banner.style.backgroundColor=p.bgColor; localStorage.setItem('adCurrentIndex',index); localStorage.setItem('adShownTime',Date.now());
        const logo=p.logo_path?'<img src="'+p.logo_path+'" alt="" style="width:26px;height:26px;border-radius:50%;object-fit:cover;vertical-align:middle;margin-right:6px;">':'';
        const website=p.url?p.url.replace(/^https?:\/\/(www\.)?/,'').replace(/\/$/,''):'';
        let details=[]; if(website) details.push('<span class="ad-detail"><a href="'+p.url+'" target="_blank">'+website+'</a></span>'); if(p.phone) details.push('<span class="ad-detail"><a href="tel:'+p.phone+'">'+p.phone+'</a></span>'); if(p.email) details.push('<span class="ad-detail"><a href="mailto:'+p.email+'">'+p.email+'</a></span>'); if(p.description) details.push('<span class="ad-detail">'+(p.description.length>60?p.description.slice(0,60)+'…':p.description)+'</span>');
        const bar='<span class="ad-bar">|</span>'; const adEl=document.createElement('div'); adEl.className='ad-content active'; adEl.style.opacity='1';
        adEl.innerHTML='<div class="ad-left"><a href="'+(p.url||'/static/partners.html#'+p.anchor)+'" target="_blank" class="ad-partner-name">'+logo+p.name+'</a>'+(details.length?bar+details.join(bar):'')+(p.offer?'<span class="ad-offer">🎁 '+p.offer+'</span>':'')+'</div><a href="/static/partners.html#'+p.anchor+'" class="ad-more-info">More info →</a>';
        banner.appendChild(adEl);
        if(!bannerSlid){banner.classList.remove('banner-in','banner-out');requestAnimationFrame(()=>banner.classList.add('banner-in'));bannerSlid=true;}
    }
    let rotationList=[],rotationPosition=0,adRotationInterval;
    function buildRotationList(){let l=[];partners.forEach((p,i)=>{for(let w=0;w<(p.rotation_weight||1);w++)l.push(i);});return l;}
    function rotateAd(){if(!rotationList.length)return;rotationPosition=(rotationPosition+1)%rotationList.length;const pi=rotationList[rotationPosition];clearTimeout(adRotationInterval);const ac=document.getElementById('partner-ad-banner')?.querySelector('.ad-content');if(ac){ac.style.transition='opacity 0.25s';ac.style.opacity='0';}setTimeout(()=>showAd(pi),260);adRotationInterval=setTimeout(rotateAd,partners[pi].display_duration||15000);}
    function initializeAds(){if(!partners.length){document.getElementById('partner-ad-banner').style.display='none';return;}rotationList=buildRotationList();const si=parseInt(localStorage.getItem('adCurrentIndex')||'0');const st=parseInt(localStorage.getItem('adShownTime')||'0');const elapsed=Date.now()-st;let sp=rotationList.indexOf(si);if(sp===-1)sp=0;const cp=partners[rotationList[sp]]||partners[0];const remaining=Math.max((cp.display_duration||15000)-elapsed,1000);rotationPosition=sp;showAd(rotationList[sp]);if(partners.length>1)adRotationInterval=setTimeout(rotateAd,remaining);}
    window.addEventListener('load',loadAdPartners);
</script>
<script src="/static/ad-tracking.js"></script>
<script src="/static/feature-gate.js"></script>

<script>
    function updateOfflineStatus(){const bar=document.getElementById('offlineBar');const isOff=!navigator.onLine;const mr=window.offlineReady&&window.offlineReady();if(isOff&&mr){bar.style.display='block';bar.style.background='#e8f5e9';bar.style.borderLeft='4px solid #2c5f2d';bar.innerHTML='📡 <strong>Offline mode active</strong> — identifying using local AI model';}else if(isOff){bar.style.display='block';bar.style.background='#fff3cd';bar.style.borderLeft='4px solid #ff9800';bar.innerHTML='📵 <strong>No signal</strong> — <a href="/static/upgrade.html" style="color:#e67e22;font-weight:bold;">Upgrade for offline mode →</a>';}else if(mr){bar.style.display='block';bar.style.background='#e8f5e9';bar.style.borderLeft='4px solid #2c5f2d';bar.innerHTML='✅ <strong>Online</strong> — offline mode ready as backup';}else{bar.style.display='none';}}
    window.addEventListener('online',updateOfflineStatus);window.addEventListener('offline',updateOfflineStatus);window.addEventListener('offline-ready',updateOfflineStatus);
    function checkOfflineDownloadVisibility(){const section=document.getElementById('offlineDownloadSection');const warning=document.getElementById('premiumWarning');const mr=window.offlineReady&&window.offlineReady();const isPremium=document.querySelector('.account-badge.premium')!==null;if(isPremium&&!mr){warning.style.display='block';section.style.display='block';}else if(mr){warning.style.display='none';section.style.display='none';}else{warning.style.display='none';section.style.display='none';}}
    async function startOfflineDownload(){const btn=document.getElementById('downloadModelBtn');const progress=document.getElementById('downloadProgress');const bar=document.getElementById('downloadBar');const status=document.getElementById('downloadStatus');btn.disabled=true;btn.textContent='⬇️ Downloading...';progress.style.display='block';const success=await window.downloadOfflineModel(function(info){if(info.stage==='downloading'){bar.style.width=info.progress+'%';status.textContent='Downloading... '+info.progress+'%';}else if(info.stage==='saving'){status.textContent='Saving to device...';}else if(info.stage==='done'){status.textContent='✅ Offline mode ready!';}else if(info.stage==='error'){status.textContent='❌ Failed: '+info.error;}});if(success){setTimeout(()=>{document.getElementById('offlineDownloadSection').style.display='none';updateOfflineStatus();},1500);}else{btn.disabled=false;btn.textContent='⬇️ Enable Offline Mode';}}
    window.startOfflineDownload=startOfflineDownload;
    document.addEventListener('DOMContentLoaded',()=>{updateOfflineStatus();setTimeout(checkOfflineDownloadVisibility,1500);});
</script>

</body>
</html>
