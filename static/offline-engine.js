// ============================================================
// offline-engine.js  —  AmmoniteID offline identification
// EfficientNetB0 · 17 classes · 224×224 · TFJS layers-model
// 5 weight shards · IndexedDB cache · auto-download on load
// ============================================================
//
//  <script src="https://cdn.jsdelivr.net/npm/@tensorflow/tfjs@4.20.0/dist/tf.min.js"></script>
//  <script src="/static/offline-engine.js"></script>
// ============================================================

(function () {
    'use strict';

    // ── Config ───────────────────────────────────────────────
    const MODEL_BASE   = '/static/tfjs_model/';
    const MODEL_URL    = MODEL_BASE + 'model.json';
    const CLASS_URL    = '/static/class_info.json';
    const IMAGE_SIZE   = 224;
    const NUM_CLASSES  = 17;
    const NUM_SHARDS   = 5;

    // IndexedDB
    const DB_NAME    = 'AmmoniteID_Offline';
    const DB_VERSION = 2;                    // bumped from v1 — shards stored individually
    const STORE      = 'model_store';

    // IDB keys
    const KEY_MODEL_JSON  = 'model_json';
    const KEY_CLASS_INFO  = 'class_info';
    const KEY_SHARD       = (i) => `shard_${i}`;   // shard_0 … shard_4
    const KEY_SHARD_COUNT = 'shard_count';

    // ── State ────────────────────────────────────────────────
    let _model       = null;   // loaded tf.LayersModel
    let _classInfo   = null;
    let _ready       = false;
    let _downloading = false;

    // Taxonomy maps (populated from class_info.json)
    let INDEX_TO_CLASS   = {};
    let GENUS_TO_FAMILY  = {};
    let FAMILY_TO_GENERA = {};
    let NON_AMMONITE_MAP = {};
    let THRESHOLDS       = {};

    const NON_AM_DISPLAY = {
        'Not_Ammonite'    : 'a rock, pebble or non-fossil object',
        'NOT A FOSSIL'    : 'a rock, pebble or non-fossil object',
        'Belemnite Fossil': 'a Belemnite',
        'Bivalve'         : 'a Bivalve',
        'Devils toenail'  : 'a Devils Toenail (Gryphaea)',
    };

    // ── Public API ───────────────────────────────────────────
    window.offlineReady       = () => _ready;
    window.offlineDownloading = () => _downloading;
    window.isOffline          = () => !navigator.onLine;

    // ── IndexedDB helpers ────────────────────────────────────
    function openDB() {
        return new Promise((resolve, reject) => {
            const req = indexedDB.open(DB_NAME, DB_VERSION);
            req.onupgradeneeded = (e) => {
                const db = e.target.result;
                if (!db.objectStoreNames.contains(STORE)) {
                    db.createObjectStore(STORE);
                }
            };
            req.onsuccess = () => resolve(req.result);
            req.onerror   = () => reject(req.error);
        });
    }

    async function idbGet(key) {
        const db = await openDB();
        return new Promise((resolve, reject) => {
            const tx  = db.transaction(STORE, 'readonly');
            const req = tx.objectStore(STORE).get(key);
            req.onsuccess = () => resolve(req.result !== undefined ? req.result : null);
            req.onerror   = () => reject(req.error);
        });
    }

    async function idbSet(key, value) {
        const db = await openDB();
        return new Promise((resolve, reject) => {
            const tx = db.transaction(STORE, 'readwrite');
            tx.objectStore(STORE).put(value, key);
            tx.oncomplete = () => resolve();
            tx.onerror    = () => reject(tx.error);
        });
    }

    async function idbDelete(key) {
        const db = await openDB();
        return new Promise((resolve, reject) => {
            const tx = db.transaction(STORE, 'readwrite');
            tx.objectStore(STORE).delete(key);
            tx.oncomplete = () => resolve();
            tx.onerror    = () => reject(tx.error);
        });
    }

    // ── Load class_info ──────────────────────────────────────
    async function loadClassInfo() {
        try {
            // Refresh from server when online, fall back to IDB cache
            if (navigator.onLine) {
                try {
                    const res = await fetch(CLASS_URL, { cache: 'no-cache' });
                    if (res.ok) {
                        _classInfo = await res.json();
                        await idbSet(KEY_CLASS_INFO, JSON.stringify(_classInfo));
                    }
                } catch (_) { /* fall through to cache */ }
            }
            if (!_classInfo) {
                const cached = await idbGet(KEY_CLASS_INFO);
                if (cached) _classInfo = JSON.parse(cached);
            }
            if (!_classInfo) throw new Error('class_info unavailable');

            INDEX_TO_CLASS   = {};
            for (const [k, v] of Object.entries(_classInfo.index_to_class || {})) {
                INDEX_TO_CLASS[parseInt(k)] = v;
            }
            GENUS_TO_FAMILY  = _classInfo.genus_to_family  || {};
            FAMILY_TO_GENERA = _classInfo.family_to_genera || {};
            NON_AMMONITE_MAP = _classInfo.non_ammonite_map || {};
            THRESHOLDS       = Object.assign(
                { family_likely: 0.75, family_possible: 0.55, genus_best_match: 0.6, genus_possible: 0.3 },
                _classInfo.thresholds || {}
            );
            return true;
        } catch (e) {
            console.error('offline-engine: loadClassInfo failed', e);
            return false;
        }
    }

    // ── Build a TF.js IOHandler from IDB data ────────────────
    // layers-model format: model.json contains modelTopology +
    // weightsManifest.  Each shard path maps to an ArrayBuffer
    // we stored individually in IDB as shard_0 … shard_N.
    function buildIOHandler(modelJson, shardBuffers) {
        return {
            load: async () => {
                const weightsManifest = modelJson.weightsManifest || [];

                // Collect all weight specs in manifest order
                const weightSpecs = weightsManifest.flatMap(g => g.weights);

                // Collect all shard buffers in manifest path order
                // (paths are listed across manifest groups in order)
                const allPaths   = weightsManifest.flatMap(g => g.paths);
                const weightData = new ArrayBuffer(
                    shardBuffers.reduce((s, b) => s + b.byteLength, 0)
                );
                const dst = new Uint8Array(weightData);
                let offset = 0;
                for (let i = 0; i < allPaths.length; i++) {
                    const src = new Uint8Array(shardBuffers[i]);
                    dst.set(src, offset);
                    offset += src.byteLength;
                }

                return {
                    modelTopology   : modelJson.modelTopology,
                    weightSpecs,
                    weightData,
                    // Signal that output is already normalised (sigmoid/softmax)
                    format          : modelJson.format,
                    generatedBy     : modelJson.generatedBy,
                    convertedBy     : modelJson.convertedBy,
                };
            }
        };
    }

    // ── Download & cache the model ───────────────────────────
    window.downloadOfflineModel = async function (progressCb) {
        if (_downloading) return false;
        _downloading = true;

        const progress = (stage, pct, extra) => {
            if (progressCb) progressCb({ stage, progress: pct, ...extra });
        };

        try {
            progress('downloading', 0);

            // 1. Fetch model.json
            const mjRes = await fetch(MODEL_URL, { cache: 'no-cache' });
            if (!mjRes.ok) throw new Error(`model.json fetch failed: ${mjRes.status}`);
            const modelJson = await mjRes.json();

            // 2. Resolve shard URLs from weightsManifest
            const allPaths = (modelJson.weightsManifest || []).flatMap(g => g.paths);
            if (allPaths.length === 0) throw new Error('No weight shards listed in model.json');

            console.log(`offline-engine: downloading ${allPaths.length} shard(s)`);

            // 3. Download each shard and store individually in IDB
            const shardBuffers = [];
            for (let i = 0; i < allPaths.length; i++) {
                const url = MODEL_BASE + allPaths[i];
                const res = await fetch(url, { cache: 'no-cache' });
                if (!res.ok) throw new Error(`Shard ${allPaths[i]} fetch failed: ${res.status}`);
                const buf = await res.arrayBuffer();
                await idbSet(KEY_SHARD(i), buf);   // store each shard individually
                shardBuffers.push(buf);
                progress('downloading', Math.round(((i + 1) / allPaths.length) * 80));
                console.log(`offline-engine: shard ${i + 1}/${allPaths.length} cached (${(buf.byteLength / 1024 / 1024).toFixed(1)} MB)`);
            }

            // 4. Store shard count and model.json
            progress('saving', 85);
            await idbSet(KEY_SHARD_COUNT, allPaths.length);
            await idbSet(KEY_MODEL_JSON,  JSON.stringify(modelJson));

            // 5. Load class info
            progress('saving', 90);
            await loadClassInfo();

            // 6. Pre-load the model into memory so first inference is fast
            progress('loading', 95);
            _model = await tf.loadLayersModel(buildIOHandler(modelJson, shardBuffers));
            // Warm up with a dummy tensor
            const dummy = tf.zeros([1, IMAGE_SIZE, IMAGE_SIZE, 3]);
            _model.predict(dummy).dispose();
            dummy.dispose();

            _ready       = true;
            _downloading = false;
            progress('done', 100);
            console.log('offline-engine: model ready');
            window.dispatchEvent(new Event('offline-ready'));
            return true;

        } catch (e) {
            console.error('offline-engine: download failed', e);
            _downloading = false;
            progress('error', 0, { error: e.message });
            return false;
        }
    };

    // ── Delete the cached model ──────────────────────────────
    window.deleteOfflineModel = async function () {
        try {
            const count = await idbGet(KEY_SHARD_COUNT) || NUM_SHARDS;
            for (let i = 0; i < count; i++) await idbDelete(KEY_SHARD(i));
            await idbDelete(KEY_SHARD_COUNT);
            await idbDelete(KEY_MODEL_JSON);
            await idbDelete(KEY_CLASS_INFO);
            _ready = false;
            _model = null;
            return true;
        } catch (e) {
            console.error('offline-engine: deleteOfflineModel failed', e);
            return false;
        }
    };

    // ── Load model from IDB (if not already in memory) ───────
    async function ensureModel() {
        if (_model) return;

        const mjStr = await idbGet(KEY_MODEL_JSON);
        if (!mjStr) throw new Error('Model JSON not in storage');
        const modelJson = JSON.parse(mjStr);

        const count = await idbGet(KEY_SHARD_COUNT) || NUM_SHARDS;
        const shardBuffers = [];
        for (let i = 0; i < count; i++) {
            const buf = await idbGet(KEY_SHARD(i));
            if (!buf) throw new Error(`Shard ${i} missing from storage`);
            shardBuffers.push(buf);
        }

        _model = await tf.loadLayersModel(buildIOHandler(modelJson, shardBuffers));
        console.log('offline-engine: model loaded from IDB');
    }

    // ── Preprocess image → Float32Array [1,224,224,3] ────────
    // EfficientNetB0 expects pixels in [0, 1] (Keras default rescaling)
    function preprocessImage(file) {
        return new Promise((resolve, reject) => {
            const img = new Image();
            img.onload = () => {
                const canvas = document.createElement('canvas');
                canvas.width  = IMAGE_SIZE;
                canvas.height = IMAGE_SIZE;
                canvas.getContext('2d').drawImage(img, 0, 0, IMAGE_SIZE, IMAGE_SIZE);
                const px   = canvas.getContext('2d').getImageData(0, 0, IMAGE_SIZE, IMAGE_SIZE).data;
                const f32  = new Float32Array(IMAGE_SIZE * IMAGE_SIZE * 3);
                for (let i = 0; i < IMAGE_SIZE * IMAGE_SIZE; i++) {
                    f32[i * 3]     = px[i * 4]     / 255.0;   // R
                    f32[i * 3 + 1] = px[i * 4 + 1] / 255.0;   // G
                    f32[i * 3 + 2] = px[i * 4 + 2] / 255.0;   // B
                }
                if (file instanceof Blob) URL.revokeObjectURL(img.src);
                resolve(f32);
            };
            img.onerror = (e) => reject(new Error('Image load failed: ' + e));
            img.src = (file instanceof Blob) ? URL.createObjectURL(file) : file;
        });
    }

    // ── Run inference on one Float32Array ─────────────────────
    async function runInference(f32) {
        if (typeof tf === 'undefined') throw new Error('TensorFlow.js not loaded');
        await ensureModel();

        const input  = tf.tensor4d(f32, [1, IMAGE_SIZE, IMAGE_SIZE, 3]);
        const output = _model.predict(input);
        const scores = Array.from(await output.data());
        input.dispose();
        output.dispose();

        return processScores(scores);
    }

    // ── Map raw scores to genus/family/non-am ─────────────────
    function processScores(raw) {
        const effectiveN = Math.min(raw.length, NUM_CLASSES, Object.keys(INDEX_TO_CLASS).length);
        const classScores = {};
        for (let i = 0; i < effectiveN; i++) {
            const name = INDEX_TO_CLASS[i];
            if (name) classScores[name] = raw[i];
        }

        const genusScores = {};
        const nonAmScores = {};
        for (const [name, score] of Object.entries(classScores)) {
            if (GENUS_TO_FAMILY[name]) genusScores[name] = score;
            else                       nonAmScores[name]  = score;
        }

        const familyScores = {};
        for (const [family, genera] of Object.entries(FAMILY_TO_GENERA)) {
            familyScores[family] = genera.reduce((s, g) => s + (genusScores[g] || 0), 0);
        }

        const nonAmTotal = Object.values(nonAmScores).reduce((a, b) => a + b, 0);
        const keys       = Object.keys(nonAmScores);
        const topNonAm   = keys.length
            ? keys.reduce((a, b) => nonAmScores[a] > nonAmScores[b] ? a : b)
            : 'NOT A FOSSIL';

        return { classScores, genusScores, familyScores, nonAmScores, nonAmTotal, topNonAm };
    }

    // ── Average results from multiple images ──────────────────
    function combineResults(results) {
        if (results.length === 1) return results[0];

        const allClasses = Object.keys(results[0].classScores);
        const avgClass   = {};
        for (const cls of allClasses) {
            avgClass[cls] = results.reduce((s, r) => s + (r.classScores[cls] || 0), 0) / results.length;
        }

        // Re-derive genus/family/non-am from averaged class scores
        const genusScores  = {};
        const nonAmScores  = {};
        for (const [name, score] of Object.entries(avgClass)) {
            if (GENUS_TO_FAMILY[name]) genusScores[name] = score;
            else                       nonAmScores[name]  = score;
        }
        const familyScores = {};
        for (const [family, genera] of Object.entries(FAMILY_TO_GENERA)) {
            familyScores[family] = genera.reduce((s, g) => s + (genusScores[g] || 0), 0);
        }
        const nonAmTotal = Object.values(nonAmScores).reduce((a, b) => a + b, 0);
        const topNonAm   = Object.keys(nonAmScores).length
            ? Object.keys(nonAmScores).reduce((a, b) => nonAmScores[a] > nonAmScores[b] ? a : b)
            : 'NOT A FOSSIL';

        return { classScores: avgClass, genusScores, familyScores, nonAmScores, nonAmTotal, topNonAm };
    }

    // ── Build the final result object (mirrors server output) ─
    function buildResult(combined, numPhotos) {
        const { familyScores, genusScores, nonAmScores, nonAmTotal, topNonAm } = combined;

        const familyKeys    = Object.keys(familyScores);
        const topFamily     = familyKeys.length
            ? familyKeys.reduce((a, b) => familyScores[a] > familyScores[b] ? a : b)
            : 'Unknown';
        const topFamilyScore = (familyScores[topFamily] || 0) * 100;
        const topNonAmScore  = (nonAmScores[topNonAm]   || 0) * 100;

        const TH = THRESHOLDS;
        let scenario;
        if (nonAmTotal * 100 > topFamilyScore) {
            scenario = 'non_ammonite';
        } else if (topFamilyScore >= (TH.family_likely   || 75)) {
            scenario = 'likely';
        } else if (topFamilyScore >= (TH.family_possible || 55)) {
            scenario = 'possible';
        } else {
            scenario = 'uncertain';
        }

        // Genus breakdown (only for ammonite scenarios)
        const genusBreakdown = [];
        if (scenario === 'likely' || scenario === 'possible') {
            const genera     = FAMILY_TO_GENERA[topFamily] || [];
            const familyTotal = familyScores[topFamily] || 1;
            for (const genus of genera) {
                const raw  = genusScores[genus] || 0;
                const norm = raw / familyTotal;
                const pct  = Math.round(norm * 100);
                const wording = norm >= (TH.genus_best_match || 0.6) ? 'best match'
                              : norm >= (TH.genus_possible   || 0.3) ? 'possible'
                              : 'less likely';
                genusBreakdown.push({
                    genus,
                    normalised_score: norm,
                    bar    : buildBar(norm),
                    wording,
                    percentage: pct
                });
            }
            genusBreakdown.sort((a, b) => b.normalised_score - a.normalised_score);
        }

        const nonAmCategory = NON_AMMONITE_MAP[topNonAm] || 'Other_Fossil';
        const nonAmDisplay  = NON_AM_DISPLAY[topNonAm]   || topNonAm;

        const topGenusScore = genusBreakdown.length ? genusBreakdown[0].percentage : 0;
        const confLabel     = s => s >= 75 ? 'HIGH ✅' : s >= 55 ? 'MODERATE ⚠️' : 'LOW ❌';

        const result = {
            scenario,
            num_photos         : numPhotos,
            top_family         : topFamily,
            top_family_score   : Math.round(topFamilyScore),
            family_confidence  : Math.round(topFamilyScore),   // alias used by test.html
            family_scores      : Object.fromEntries(
                Object.entries(familyScores).map(([k, v]) => [k, Math.round(v * 1000) / 10])
            ),
            genus_breakdown    : genusBreakdown,
            non_am_total       : Math.round(nonAmTotal * 100),
            top_non_am         : topNonAm,
            top_non_am_score   : Math.round(topNonAmScore),
            non_am_category    : nonAmCategory,
            non_am_display     : nonAmDisplay,
            family_label       : confLabel(topFamilyScore),
            genus_label        : topGenusScore ? confLabel(topGenusScore) : null,
            feedback_message   : generateFeedback(scenario, topFamilyScore, topGenusScore),
            feedback_style     : topFamilyScore >= 55 ? 'info' : 'warning',
            model_version      : 'v1-offline',
            offline            : true,
            formatted_output   : '',
        };
        result.formatted_output = formatOutput(result);
        return result;
    }

    function buildBar(score, width = 10) {
        const n = Math.round(Math.min(1, Math.max(0, score)) * width);
        return '█'.repeat(n) + '░'.repeat(width - n);
    }

    function generateFeedback(scenario, familyScore, genusScore) {
        if (scenario === 'non_ammonite')
            return '💡 If you believe this is an ammonite, try retaking with the spiral/coiling pattern clearly visible';
        if (scenario === 'uncertain' || familyScore < 55)
            return '⚠️ Low confidence — try: closer photo, better lighting, or fill 80%+ of frame';
        if (familyScore < 75)
            return '💡 This result is likely correct. For even better accuracy, try filling 80%+ of frame or rotating 30–90°';
        if (genusScore && genusScore < 55)
            return '⚠️ Genus unclear — a closer photo showing ribs/sutures may help';
        return '';
    }

    function formatOutput(r) {
        const lines = [];
        if (r.scenario === 'likely' || r.scenario === 'possible') {
            const w = r.scenario === 'likely' ? 'Likely' : 'Possible';
            lines.push(`FAMILY:  ${r.top_family}     [${w} — ${r.top_family_score}% confidence]`);
            if (r.num_photos > 1) lines.push(`         Based on ${r.num_photos} photographs`);
            lines.push('', 'GENUS:');
            for (const g of r.genus_breakdown)
                lines.push(`  ${g.genus.padEnd(28)}  ${g.bar}  ${g.wording}`);
            lines.push('', 'If a more accurate identification is required,');
            lines.push('it is recommended to consult with an expert.');
        } else if (r.scenario === 'uncertain') {
            lines.push('FAMILY:  Uncertain — confidence too low to suggest a family');
            lines.push('', 'GENUS:   Cannot be determined from this image.', '');
            lines.push('For best results:');
            lines.push('  — Crop so the fossil fills most of the frame');
            lines.push('  — Photograph from directly above');
            lines.push('  — Use even lighting with no shadows across the ribs');
            lines.push('  — Try a second photo from a different angle');
        } else {
            const cat = r.non_am_category;
            if (cat === 'Not_Fossil') {
                lines.push('FAMILY:  No ammonite detected', '');
                lines.push('This appears to be ' + r.non_am_display + '.', '');
                lines.push('For best results:');
                lines.push('  — Crop so the fossil fills most of the frame');
                lines.push('  — Ensure the specimen is well lit with no strong shadows');
                lines.push('  — Photograph from directly above');
            } else {
                lines.push('FAMILY:  Other fossil type detected');
                lines.push('         (not an ammonite)', '');
                lines.push(r.top_non_am_score > 60
                    ? 'This appears to be ' + r.non_am_display + '.'
                    : 'This resembles another fossil type but the image is not clear enough to determine which.');
                lines.push('', 'If a more accurate identification is required, it is recommended to consult with an expert.');
            }
        }
        return lines.join('\n');
    }

    // ── Public: run offline identification ────────────────────
    window.identifyOffline = async function (imageFiles) {
        if (!_ready)      throw new Error('Offline model not downloaded');
        if (!_classInfo)  await loadClassInfo();
        await ensureModel();

        const results = [];
        for (const file of imageFiles) {
            const f32    = await preprocessImage(file);
            const scored = await runInference(f32);
            results.push(scored);
        }

        const combined = combineResults(results);
        return buildResult(combined, imageFiles.length);
    };

    // ── Boot: check IDB, auto-download when online ────────────
    async function init() {
        try {
            const mjStr = await idbGet(KEY_MODEL_JSON);
            const count = await idbGet(KEY_SHARD_COUNT);

            if (mjStr && count) {
                // Verify all shards are present
                let allPresent = true;
                for (let i = 0; i < count; i++) {
                    const s = await idbGet(KEY_SHARD(i));
                    if (!s) { allPresent = false; break; }
                }
                if (allPresent) {
                    await loadClassInfo();
                    _ready = true;
                    console.log(`offline-engine: model ready (${count} shards from IDB)`);
                    window.dispatchEvent(new Event('offline-ready'));
                    return;
                } else {
                    console.warn('offline-engine: incomplete shard cache — re-downloading');
                }
            }

            // Auto-download silently in background if online
            if (navigator.onLine) {
                console.log('offline-engine: auto-downloading model...');
                const ok = await window.downloadOfflineModel((info) => {
                    if (info.stage === 'done') {
                        console.log('offline-engine: auto-download complete');
                        window.dispatchEvent(new Event('offline-ready'));
                    }
                });
                if (!ok) console.warn('offline-engine: auto-download failed — will retry next load');
            } else {
                console.log('offline-engine: offline and no cache — cannot download');
            }
        } catch (e) {
            console.warn('offline-engine: init error', e);
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
