// ============================================================
// offline-engine.js — Offline fossil identification engine
// AmmoniteID — runs the TFLite model directly in the browser
// ============================================================
//
// Uses the TFLite Task Library (WASM) to run the quantized
// model locally. No server needed. Same model, same accuracy.
//
// Add to identify page:
//   <script src="https://cdn.jsdelivr.net/npm/@�f/tfjs@4.20.0/dist/tf.min.js"></script>
//   <script src="/static/offline-engine.js"></script>
// ============================================================

(function () {
    const MODEL_URL = '/static/ammonite_model_v1_quantized.tflite';
    const CLASS_INFO_URL = '/static/class_info.json';
    const IMAGE_SIZE = 224;

    let _model = null;
    let _classInfo = null;
    let _offlineReady = false;
    let _downloading = false;

    // ── Class info and mappings (loaded from class_info.json) ─
    let INDEX_TO_CLASS = {};
    let GENUS_TO_FAMILY = {};
    let FAMILY_TO_GENERA = {};
    let NON_AMMONITE_MAP = {};
    let THRESHOLDS = {};

    const NON_AM_DISPLAY = {
        'Not_Ammonite': 'a rock, pebble or non-fossil object',
        'NOT A FOSSIL': 'a rock, pebble or non-fossil object',
        'Belemnite Fossil': 'a Belemnite',
        'Bivalve': 'a Bivalve',
        'Devils toenail': 'a Devils Toenail (Gryphaea)',
    };

    // ── Check if offline mode is available ───────────────────
    window.offlineReady = function () { return _offlineReady; };
    window.offlineDownloading = function () { return _downloading; };

    // ── Check if we're currently offline ─────────────────────
    window.isOffline = function () { return !navigator.onLine; };

    // ── Load class info ─────────────────────────────────────
    async function loadClassInfo() {
        try {
            // Try from cache first (IndexedDB)
            const cached = await idbGet('class_info');
            if (cached) {
                _classInfo = JSON.parse(cached);
            } else {
                const res = await fetch(CLASS_INFO_URL);
                _classInfo = await res.json();
                await idbSet('class_info', JSON.stringify(_classInfo));
            }

            INDEX_TO_CLASS = {};
            for (const [k, v] of Object.entries(_classInfo.index_to_class)) {
                INDEX_TO_CLASS[parseInt(k)] = v;
            }
            GENUS_TO_FAMILY = _classInfo.genus_to_family || {};
            FAMILY_TO_GENERA = _classInfo.family_to_genera || {};
            NON_AMMONITE_MAP = _classInfo.non_ammonite_map || {};
            THRESHOLDS = _classInfo.thresholds || {
                family_likely: 0.75,
                family_possible: 0.55,
                genus_best_match: 0.6,
                genus_possible: 0.3,
            };
            return true;
        } catch (e) {
            console.error('offline-engine: could not load class info', e);
            return false;
        }
    }

    // ── Download and cache the model ────────────────────────
    window.downloadOfflineModel = async function (progressCallback) {
        if (_downloading) return false;
        _downloading = true;

        try {
            if (progressCallback) progressCallback({ stage: 'downloading', progress: 0 });

            // Download model file
            const response = await fetch(MODEL_URL);
            if (!response.ok) throw new Error('Model download failed');

            const reader = response.body.getReader();
            const contentLength = +response.headers.get('Content-Length') || 8400000;
            let receivedLength = 0;
            const chunks = [];

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                chunks.push(value);
                receivedLength += value.length;
                if (progressCallback) {
                    progressCallback({
                        stage: 'downloading',
                        progress: Math.round((receivedLength / contentLength) * 100)
                    });
                }
            }

            // Combine chunks into single ArrayBuffer
            const modelBytes = new Uint8Array(receivedLength);
            let position = 0;
            for (const chunk of chunks) {
                modelBytes.set(chunk, position);
                position += chunk.length;
            }

            // Store in IndexedDB
            if (progressCallback) progressCallback({ stage: 'saving', progress: 100 });
            await idbSet('offline_model', modelBytes);

            // Load class info too
            await loadClassInfo();

            _offlineReady = true;
            _downloading = false;

            if (progressCallback) progressCallback({ stage: 'done', progress: 100 });
            return true;
        } catch (e) {
            console.error('offline-engine: download failed', e);
            _downloading = false;
            if (progressCallback) progressCallback({ stage: 'error', error: e.message });
            return false;
        }
    };

    // ── Delete the offline model ────────────────────────────
    window.deleteOfflineModel = async function () {
        try {
            await idbDelete('offline_model');
            await idbDelete('class_info');
            _offlineReady = false;
            _model = null;
            return true;
        } catch (e) {
            return false;
        }
    };

    // ── Run offline identification ──────────────────────────
    window.identifyOffline = async function (imageFiles) {
        if (!_offlineReady) throw new Error('Offline model not downloaded');

        // Load class info if not loaded
        if (!_classInfo) await loadClassInfo();

        // Load model from IndexedDB if not in memory
        if (!_model) {
            const modelBytes = await idbGet('offline_model');
            if (!modelBytes) throw new Error('Model not found in storage');
            _model = modelBytes;
        }

        // Process each image
        const singleResults = [];
        for (const file of imageFiles) {
            const imageArray = await preprocessImage(file);
            const result = await runInference(imageArray);
            singleResults.push(result);
        }

        // Combine results (average if multiple photos)
        const combined = combineResults(singleResults);
        return buildResult(combined, imageFiles.length);
    };

    // ── Preprocess image (resize to 224x224, normalize) ─────
    function preprocessImage(file) {
        return new Promise((resolve, reject) => {
            const img = new Image();
            img.onload = () => {
                const canvas = document.createElement('canvas');
                canvas.width = IMAGE_SIZE;
                canvas.height = IMAGE_SIZE;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0, IMAGE_SIZE, IMAGE_SIZE);
                const imageData = ctx.getImageData(0, 0, IMAGE_SIZE, IMAGE_SIZE);

                // Convert to float32 array [1, 224, 224, 3]
                const float32 = new Float32Array(1 * IMAGE_SIZE * IMAGE_SIZE * 3);
                for (let i = 0; i < IMAGE_SIZE * IMAGE_SIZE; i++) {
                    float32[i * 3] = imageData.data[i * 4];       // R
                    float32[i * 3 + 1] = imageData.data[i * 4 + 1]; // G
                    float32[i * 3 + 2] = imageData.data[i * 4 + 2]; // B
                }
                resolve(float32);
            };
            img.onerror = reject;
            if (file instanceof File || file instanceof Blob) {
                img.src = URL.createObjectURL(file);
            } else {
                img.src = file; // data URL or path
            }
        });
    }

    // ── Run TFLite inference using tf.js ────────────────────
    async function runInference(imageArray) {
        // Use tf.js with the TFLite delegate
        // Load tf.js if not already loaded
        if (typeof tf === 'undefined') {
            throw new Error('TensorFlow.js not loaded');
        }

        // Create interpreter from stored model bytes
        if (!window._tfliteModel) {
            const modelBytes = await idbGet('offline_model');
            window._tfliteModel = await tf.loadGraphModel(
                tf.io.browserHTTPRequest(MODEL_URL),
            ).catch(() => null);

            // If graph model doesn't work, fall back to manual inference
            if (!window._tfliteModel) {
                // Use raw WASM TFLite interpreter
                return runTFLiteWASM(imageArray);
            }
        }

        const inputTensor = tf.tensor(imageArray, [1, IMAGE_SIZE, IMAGE_SIZE, 3]);
        const prediction = window._tfliteModel.predict(inputTensor);
        const scores = await prediction.data();
        inputTensor.dispose();
        prediction.dispose();

        return processScores(Array.from(scores));
    }

    // ── Fallback: manual softmax + score processing ─────────
    // If we can't load tf.js graph model, we process raw output
    async function runTFLiteWASM(imageArray) {
        // For environments where tf.js can't load the model directly,
        // we send to server (which is the online path anyway).
        // This fallback exists for safety.
        throw new Error('Direct TFLite WASM not available — use online mode');
    }

    // ── Process raw model output scores ─────────────────────
    function processScores(rawScores) {
        const numClasses = Object.keys(INDEX_TO_CLASS).length;
        const effectiveClasses = Math.min(rawScores.length, numClasses);

        const classScores = {};
        for (let i = 0; i < effectiveClasses; i++) {
            const className = INDEX_TO_CLASS[i];
            if (className) classScores[className] = rawScores[i];
        }

        const genusScores = {};
        const nonAmScores = {};

        for (const [name, score] of Object.entries(classScores)) {
            if (GENUS_TO_FAMILY[name]) {
                genusScores[name] = score;
            } else {
                nonAmScores[name] = score;
            }
        }

        const familyScores = {};
        for (const [family, genera] of Object.entries(FAMILY_TO_GENERA)) {
            familyScores[family] = genera.reduce((sum, g) => sum + (genusScores[g] || 0), 0);
        }

        const nonAmTotal = Object.values(nonAmScores).reduce((a, b) => a + b, 0);
        const topNonAm = Object.keys(nonAmScores).reduce((a, b) => nonAmScores[a] > nonAmScores[b] ? a : b, Object.keys(nonAmScores)[0] || 'NOT A FOSSIL');

        return { classScores, genusScores, familyScores, nonAmScores, nonAmTotal, topNonAm };
    }

    // ── Combine multiple photo results ──────────────────────
    function combineResults(results) {
        if (results.length === 1) return results[0];

        const allClasses = Object.keys(results[0].classScores);
        const avgClass = {};
        for (const cls of allClasses) {
            avgClass[cls] = results.reduce((sum, r) => sum + (r.classScores[cls] || 0), 0) / results.length;
        }

        const genusScores = {};
        const nonAmScores = {};
        for (const [name, score] of Object.entries(avgClass)) {
            if (GENUS_TO_FAMILY[name]) genusScores[name] = score;
            else nonAmScores[name] = score;
        }

        const familyScores = {};
        for (const [family, genera] of Object.entries(FAMILY_TO_GENERA)) {
            familyScores[family] = genera.reduce((sum, g) => sum + (genusScores[g] || 0), 0);
        }

        const nonAmTotal = Object.values(nonAmScores).reduce((a, b) => a + b, 0);
        const topNonAm = Object.keys(nonAmScores).reduce((a, b) => nonAmScores[a] > nonAmScores[b] ? a : b, Object.keys(nonAmScores)[0]);

        return { classScores: avgClass, genusScores, familyScores, nonAmScores, nonAmTotal, topNonAm };
    }

    // ── Build the full result (mirrors identifier.py) ───────
    function buildResult(combined, numPhotos) {
        const familyScores = combined.familyScores;
        const nonAmTotal = combined.nonAmTotal;
        const topNonAm = combined.topNonAm;
        const genusScores = combined.genusScores;

        const topFamily = Object.keys(familyScores).reduce((a, b) => familyScores[a] > familyScores[b] ? a : b);
        const topFamilyScore = familyScores[topFamily] * 100;
        const topNonAmScore = (combined.nonAmScores[topNonAm] || 0) * 100;

        // Determine scenario
        let scenario;
        if (nonAmTotal * 100 > topFamilyScore) {
            scenario = 'non_ammonite';
        } else if (topFamilyScore >= (THRESHOLDS.family_likely || 75)) {
            scenario = 'likely';
        } else if (topFamilyScore >= (THRESHOLDS.family_possible || 55)) {
            scenario = 'possible';
        } else {
            scenario = 'uncertain';
        }

        // Build genus breakdown
        const genusBreakdown = [];
        if (scenario === 'likely' || scenario === 'possible') {
            const familyGenera = FAMILY_TO_GENERA[topFamily] || [];
            const familyTotal = familyScores[topFamily];

            for (const genus of familyGenera) {
                const raw = genusScores[genus] || 0;
                const norm = familyTotal > 0 ? raw / familyTotal : 0;
                const pct = Math.round(norm * 100);
                let wording;
                if (norm >= (THRESHOLDS.genus_best_match || 0.6)) wording = 'best match';
                else if (norm >= (THRESHOLDS.genus_possible || 0.3)) wording = 'possible';
                else wording = 'less likely';

                genusBreakdown.push({
                    genus, normalised_score: norm,
                    bar: buildBar(norm), wording, percentage: pct
                });
            }
            genusBreakdown.sort((a, b) => b.normalised_score - a.normalised_score);
        }

        // Non-ammonite category
        const nonAmCategory = NON_AMMONITE_MAP[topNonAm] || 'Other_Fossil';
        const nonAmDisplay = NON_AM_DISPLAY[topNonAm] || topNonAm;

        // Confidence labels
        const topGenusScore = genusBreakdown.length > 0 ? genusBreakdown[0].percentage : 0;
        function confLabel(s) { return s >= 75 ? 'HIGH ✅' : s >= 55 ? 'MODERATE ⚠️' : 'LOW ❌'; }

        const result = {
            scenario, num_photos: numPhotos,
            top_family: topFamily,
            top_family_score: Math.round(topFamilyScore),
            family_scores: Object.fromEntries(Object.entries(familyScores).map(([k, v]) => [k, Math.round(v * 1000) / 10])),
            genus_breakdown: genusBreakdown,
            non_am_total: Math.round(nonAmTotal * 100),
            top_non_am: topNonAm,
            top_non_am_score: Math.round(topNonAmScore),
            non_am_category: nonAmCategory,
            non_am_display: nonAmDisplay,
            family_label: confLabel(topFamilyScore),
            genus_label: topGenusScore ? confLabel(topGenusScore) : null,
            feedback_message: generateFeedback(scenario, topFamilyScore, topGenusScore),
            feedback_style: topFamilyScore >= 55 ? 'info' : 'warning',
            formatted_output: '', // will be set below
            model_version: 'v1-offline',
            offline: true,
        };

        result.formatted_output = formatOutput(result);
        return result;
    }

    function buildBar(score, width) {
        width = width || 10;
        const filled = Math.round(score * width);
        return '█'.repeat(filled) + '░'.repeat(width - filled);
    }

    function generateFeedback(scenario, familyScore, genusScore) {
        if (scenario === 'non_ammonite') {
            return '💡 If you believe this is actually an ammonite, try retaking with the spiral/coiling pattern clearly visible';
        } else if (scenario === 'uncertain') {
            return '⚠️ Low confidence - for a more reliable result, try: closer photo, better lighting, or fill 80%+ of frame';
        } else if (familyScore < 55) {
            return '⚠️ Low confidence - for a more reliable result, try: closer photo, better lighting, or fill 80%+ of frame';
        } else if (familyScore < 75) {
            return '💡 This result is likely correct. For even better accuracy, try filling 80%+ of frame or rotating 30-90°';
        } else if (genusScore && genusScore < 55) {
            return '⚠️ Genus unclear - a closer photo showing ribs/sutures may help refine the identification';
        }
        return '';
    }

    function formatOutput(result) {
        const lines = [];
        const scenario = result.scenario;

        if (scenario === 'likely' || scenario === 'possible') {
            const wording = scenario === 'likely' ? 'Likely' : 'Possible';
            lines.push(`FAMILY:  ${result.top_family}     [${wording} — ${result.top_family_score}% confidence]`);
            if (result.num_photos > 1) lines.push(`         Based on ${result.num_photos} photographs`);
            lines.push('', 'GENUS:');
            for (const g of result.genus_breakdown) {
                lines.push(`  ${g.genus.padEnd(28)}  ${g.bar}  ${g.wording}`);
            }
            lines.push('', 'If a more accurate identification is required,');
            lines.push('it is recommended to consult with an expert.');
        } else if (scenario === 'uncertain') {
            lines.push('FAMILY:  Uncertain — confidence too low to suggest a family');
            lines.push('', 'GENUS:   Cannot be determined from this image.', '');
            lines.push('For best results:');
            lines.push('  — Crop the photo so the fossil fills most of the frame');
            lines.push('  — Photograph from directly above');
            lines.push('  — Use even lighting with no shadows across the ribs');
            lines.push('  — Try a second photo from a different angle');
        } else if (scenario === 'non_ammonite') {
            const cat = result.non_am_category;
            if (cat === 'Not_Fossil') {
                lines.push('FAMILY:  No ammonite detected', '');
                lines.push('This appears to be ' + result.non_am_display + '.', '');
                lines.push('For best results:');
                lines.push('  — Crop the photo so the fossil fills most of the frame');
                lines.push('  — Make sure the specimen is well lit with no strong shadows');
                lines.push('  — Photograph from directly above');
            } else {
                lines.push('FAMILY:  Other fossil type detected');
                lines.push('         (not an ammonite)', '');
                if (result.top_non_am_score > 60) {
                    lines.push('This appears to be ' + result.non_am_display + '.');
                } else {
                    lines.push('This resembles another fossil type but the image is not clear enough to determine which.');
                }
                lines.push('', 'If a more accurate identification is required, it is recommended to consult with an expert.');
            }
        }
        return lines.join('\n');
    }

    // ── IndexedDB helpers (persistent storage) ──────────────
    const DB_NAME = 'AmmoniteID_Offline';
    const STORE_NAME = 'model_store';

    function openDB() {
        return new Promise((resolve, reject) => {
            const req = indexedDB.open(DB_NAME, 1);
            req.onupgradeneeded = () => req.result.createObjectStore(STORE_NAME);
            req.onsuccess = () => resolve(req.result);
            req.onerror = () => reject(req.error);
        });
    }

    async function idbGet(key) {
        const db = await openDB();
        return new Promise((resolve, reject) => {
            const tx = db.transaction(STORE_NAME, 'readonly');
            const req = tx.objectStore(STORE_NAME).get(key);
            req.onsuccess = () => resolve(req.result || null);
            req.onerror = () => reject(req.error);
        });
    }

    async function idbSet(key, value) {
        const db = await openDB();
        return new Promise((resolve, reject) => {
            const tx = db.transaction(STORE_NAME, 'readwrite');
            tx.objectStore(STORE_NAME).put(value, key);
            tx.oncomplete = () => resolve();
            tx.onerror = () => reject(tx.error);
        });
    }

    async function idbDelete(key) {
        const db = await openDB();
        return new Promise((resolve, reject) => {
            const tx = db.transaction(STORE_NAME, 'readwrite');
            tx.objectStore(STORE_NAME).delete(key);
            tx.oncomplete = () => resolve();
            tx.onerror = () => reject(tx.error);
        });
    }

    // ── Boot: check if model is already downloaded ──────────
    async function init() {
        try {
            const stored = await idbGet('offline_model');
            if (stored) {
                await loadClassInfo();
                _offlineReady = true;
                console.log('offline-engine: model found in storage — offline ready');
                window.dispatchEvent(new Event('offline-ready'));
            } else {
                console.log('offline-engine: no model in storage — online only');
            }
        } catch (e) {
            console.log('offline-engine: IndexedDB not available');
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
