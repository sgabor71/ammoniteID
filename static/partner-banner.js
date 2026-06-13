// ============================================================
// partner-banner.js — Shared partner ad banner for all pages
// Include on any page with: <div id="partner-ad-banner"></div>
//                           <script src="/static/partner-banner.js"></script>
// ============================================================
(function () {
    // ── Inject CSS ──────────────────────────────────────────
    const css = document.createElement('style');
    css.textContent = `
        #partner-ad-banner {
            position: sticky;
            top: 70px;
            z-index: 99;
            box-shadow: 0 2px 6px rgba(0,0,0,0.12);
            min-height: 140px;
            overflow: hidden;
            transform: translateY(-110%);
            opacity: 0;
        }
        @keyframes bannerSlideIn {
            from { transform: translateY(-110%); opacity: 0; }
            to   { transform: translateY(0);     opacity: 1; }
        }
        @keyframes bannerSlideOut {
            from { transform: translateY(0);     opacity: 1; }
            to   { transform: translateY(-110%); opacity: 0; }
        }
        .banner-in  { animation: bannerSlideIn  0.6s cubic-bezier(0.22,1,0.36,1) forwards; }
        .banner-out { animation: bannerSlideOut 0.4s ease forwards; }
        @keyframes adFromLeft {
            from { transform: translateX(-40px); opacity: 0; }
            to   { transform: translateX(0);     opacity: 1; }
        }
        @keyframes adFromRight {
            from { transform: translateX(40px); opacity: 0; }
            to   { transform: translateX(0);    opacity: 1; }
        }
        @keyframes adFromTop {
            from { transform: translateY(-30px); opacity: 0; }
            to   { transform: translateY(0);     opacity: 1; }
        }
        @keyframes adFromBottom {
            from { transform: translateY(30px); opacity: 0; }
            to   { transform: translateY(0);    opacity: 1; }
        }
        @keyframes adFadeIn {
            from { opacity: 0; }
            to   { opacity: 1; }
        }
        .ad-content {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            min-height: 140px;
            padding: 1rem 2rem;
            flex-wrap: wrap;
        }
        .ad-left {
            display: flex;
            align-items: center;
            gap: 1rem;
            flex: 1;
            min-width: 0;
        }
        .ad-partner-info {
            display: flex;
            flex-direction: column;
            gap: 4px;
        }
        .ad-partner-name {
            font-size: 1.6rem;
            font-weight: bold;
            color: #1a1a1a;
            text-decoration: none;
            cursor: pointer;
            transition: all 0.2s;
        }
        .ad-partner-name:hover { text-decoration: underline; color: #2c5f2d; }
        img.ad-logo {
            width: 50px;
            height: 50px;
            border-radius: 8px;
            object-fit: cover;
            border: 2px solid rgba(255,255,255,0.8);
            box-shadow: 0 1px 3px rgba(0,0,0,0.15);
            flex-shrink: 0;
        }
        .ad-description {
            font-size: 1.1rem;
            color: #333;
            font-family: Arial, sans-serif;
            line-height: 1.4;
        }
        .ad-offer {
            font-size: 1rem;
            color: #2c5f2d;
            font-weight: bold;
            margin-top: 2px;
        }
        .ad-more-link {
            flex-shrink: 0;
            font-size: 0.95rem;
            color: #2c5f2d;
            text-decoration: none;
            font-weight: bold;
            white-space: nowrap;
            padding: 0.6rem 1.2rem;
            border: 2px solid #2c5f2d;
            border-radius: 8px;
            transition: all 0.3s;
            display: inline-block;
        }
        .ad-more-link:hover { background: #2c5f2d; color: white; transform: translateY(-2px); }
        @media (max-width: 768px) {
            #partner-ad-banner { min-height: 70px; top: 52px; }
            .ad-content { padding: 0.8rem 1rem; min-height: 70px; gap: 0.8rem; }
            .ad-partner-name { font-size: 1.2rem; }
            img.ad-logo { width: 40px; height: 40px; }
            .ad-description { font-size: 0.95rem; }
            .ad-offer { font-size: 0.85rem; }
            .ad-more-link { font-size: 0.8rem; padding: 0.4rem 0.8rem; }
        }
    `;
    document.head.appendChild(css);

    // ── State ────────────────────────────────────────────────
    let partners = [];
    let rotationTimer = null;
    let rotationIndex = 0;
    let rotationList = [];
    const adAnimations = ['adFromLeft', 'adFromRight', 'adFromTop', 'adFromBottom', 'adFadeIn'];

    // ── Load partners (with offline cache) ──────────────────
    async function loadAdPartners() {
        try {
            const response = await fetch('/api/admin/partners');
            const data = await response.json();
            partners = (data.partners || []).filter(p => p.status === 'active' && p.active).map(p => ({
                name: p.name,
                url: p.url,
                email: p.email || '',
                phone: p.phone || '',
                bgColor: p.bg_color,
                anchor: p.anchor || p.partner_id,
                description: p.description || '',
                offer: p.offer || '',
                logo_emoji: p.logo_emoji || '🏪',
                logo_path: p.logo_path || '',
                display_duration: (p.display_duration || 15) * 1000,
                rotation_weight: p.rotation_weight || 1
            }));
            // Cache for offline
            if (partners.length) {
                try { localStorage.setItem('ammonite_partners_cache', JSON.stringify(partners)); } catch (e) {}
            }
            partners.length ? initializeAds() : hideBanner();
        } catch (e) {
            // Offline — load from cache
            try {
                var cached = localStorage.getItem('ammonite_partners_cache');
                if (cached) {
                    partners = JSON.parse(cached);
                    partners.length ? initializeAds() : hideBanner();
                } else {
                    hideBanner();
                }
            } catch (ex) {
                hideBanner();
            }
        }
    }

    function hideBanner() {
        var b = document.getElementById('partner-ad-banner');
        if (b) b.style.display = 'none';
    }

    // ── Show ad ─────────────────────────────────────────────
    function showAd(index) {
        var banner = document.getElementById('partner-ad-banner');
        if (!banner || !partners[index]) return;
        var p = partners[index];

        // Persist state across pages
        localStorage.setItem('adCurrentIndex', index);
        localStorage.setItem('adShownTime', Date.now());

        // Track impression
        if (typeof trackAdImpression === 'function') trackAdImpression(p.anchor, p.name);
        var adShownTime = Date.now();

        // Remove old content
        var existing = banner.querySelector('.ad-content');
        if (existing) existing.remove();

        // Set background
        banner.style.backgroundColor = p.bgColor;

        // Build logo
        var logo = p.logo_path
            ? '<img src="' + p.logo_path + '" alt="" class="ad-logo">'
            : (p.logo_emoji ? '<span style="font-size:2.5rem;flex-shrink:0;">' + p.logo_emoji + '</span>' : '');

        // Build link
        var link = p.url || '/static/partners.html#' + p.anchor;
        var target = p.url ? '_blank' : '_self';

        // Random animation (slow, 1.2s)
        var anim = adAnimations[Math.floor(Math.random() * adAnimations.length)];

        // Build content
        var adEl = document.createElement('div');
        adEl.className = 'ad-content';
        adEl.style.animation = anim + ' 1.2s ease forwards';
        adEl.innerHTML =
            '<div class="ad-left">' +
                logo +
                '<div class="ad-partner-info">' +
                    '<a href="' + link + '" target="' + target + '" class="ad-partner-name">' + p.name + '</a>' +
                    (p.description ? '<span class="ad-description">' + p.description + '</span>' : '') +
                    (p.offer ? '<span class="ad-offer">🎁 ' + p.offer + '</span>' : '') +
                '</div>' +
            '</div>' +
            '<a href="/static/partners.html#' + p.anchor + '" class="ad-more-link">More info →</a>';

        banner.appendChild(adEl);

        // Slide whole banner in
        banner.classList.remove('banner-in', 'banner-out');
        requestAnimationFrame(function () { banner.classList.add('banner-in'); });

        // Track clicks
        if (typeof trackAdClick === 'function') {
            var nameEl = adEl.querySelector('.ad-partner-name');
            var moreEl = adEl.querySelector('.ad-more-link');
            if (nameEl) nameEl.addEventListener('click', function () { trackAdClick(p.anchor, p.name, Math.round((Date.now() - adShownTime) / 1000)); });
            if (moreEl) moreEl.addEventListener('click', function () { trackAdClick(p.anchor, p.name, Math.round((Date.now() - adShownTime) / 1000)); });
        }
    }

    // ── Rotation ────────────────────────────────────────────
    function buildRotationList() {
        var list = [];
        partners.forEach(function (p, i) {
            var w = p.rotation_weight || 1;
            for (var k = 0; k < w; k++) list.push(i);
        });
        return list;
    }

    function rotateAd() {
        if (rotationList.length === 0) return;
        rotationIndex = (rotationIndex + 1) % rotationList.length;
        var pIndex = rotationList[rotationIndex];
        var banner = document.getElementById('partner-ad-banner');
        var duration = partners[pIndex].display_duration || 15000;
        clearTimeout(rotationTimer);

        // Slide banner out, swap content, slide back in
        if (banner) {
            banner.classList.remove('banner-in');
            banner.classList.add('banner-out');
            setTimeout(function () { showAd(pIndex); }, 400);
        } else {
            showAd(pIndex);
        }
        rotationTimer = setTimeout(rotateAd, duration);
    }

    function initializeAds() {
        var banner = document.getElementById('partner-ad-banner');
        if (partners.length === 0) { hideBanner(); return; }

        rotationList = buildRotationList();

        // Resume from localStorage
        var savedIndex = parseInt(localStorage.getItem('adCurrentIndex') || '0');
        var savedTime = parseInt(localStorage.getItem('adShownTime') || '0');
        var elapsed = Date.now() - savedTime;

        var startPos = rotationList.indexOf(savedIndex);
        if (startPos === -1) startPos = 0;

        var currentPartner = partners[rotationList[startPos]] || partners[0];
        var duration = currentPartner.display_duration || 15000;
        var remaining = Math.max(duration - elapsed, 1000);

        rotationIndex = startPos;
        showAd(rotationList[rotationIndex]);

        if (partners.length > 1) {
            rotationTimer = setTimeout(rotateAd, remaining);
        }
    }

    // ── Init on load ────────────────────────────────────────
    window.addEventListener('load', loadAdPartners);
})();
