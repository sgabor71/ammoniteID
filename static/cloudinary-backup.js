// ============================================================
// static/cloudinary-backup.js
// Cloudinary Backup Module for AmmoniteID
// Supports: Premium, Expert, Admin tiers
// v1.1 — sync delete, admin full backup, tier-aware
// ============================================================

const CLOUDINARY_CLOUD_NAME = 'dds5rebi2';
const CLOUDINARY_UPLOAD_PRESET = 'ammonite_backup';

// ============================================================
// 1. BACKUP TO CLOUDINARY (tier-aware)
// ============================================================

async function backupToCloudinary(userId, fossilData, userTier) {
    userTier = (userTier || 'PREMIUM').toUpperCase();

    if (!userId || !fossilData || fossilData.length === 0) {
        console.warn('No data to backup');
        return { success: false, error: 'No data to backup' };
    }

    const backupData = {
        user_id: userId,
        user_tier: userTier,
        backup_date: new Date().toISOString(),
        fossil_count: fossilData.length,
        fossils: fossilData,
        app_version: '1.1'
    };

    const jsonStr = JSON.stringify(backupData);
    const blob = new Blob([jsonStr], { type: 'application/json' });
    const file = new File(
        [blob],
        `backup_${userTier}_${userId}_${Date.now()}.json`,
        { type: 'application/json' }
    );

    // Tier-based folder structure
    const folder = `ammonite_backups/${userTier.toLowerCase()}/${userId}`;

    const formData = new FormData();
    formData.append('file', file);
    formData.append('upload_preset', CLOUDINARY_UPLOAD_PRESET);
    formData.append('folder', folder);
    formData.append('public_id', `backup_${Date.now()}`);

    try {
        const response = await fetch(
            `https://api.cloudinary.com/v1_1/${CLOUDINARY_CLOUD_NAME}/auto/upload`,
            { method: 'POST', body: formData }
        );

        const data = await response.json();
        if (data.secure_url) {
            const lastBackup = {
                url: data.secure_url,
                public_id: data.public_id,
                date: new Date().toISOString(),
                fossil_count: fossilData.length,
                tier: userTier
            };
            localStorage.setItem('last_cloudinary_backup', JSON.stringify(lastBackup));
            return {
                success: true,
                url: data.secure_url,
                public_id: data.public_id,
                backup_date: lastBackup.date
            };
        } else {
            throw new Error(data.error?.message || 'Upload failed');
        }
    } catch (error) {
        console.error('Cloudinary backup failed:', error);
        return { success: false, error: error.message };
    }
}


// ============================================================
// 2. ADMIN FULL BACKUP (includes all admin page data)
// ============================================================

async function adminFullBackup(userId) {
    try {
        // Fetch full admin data from backend
        const res = await fetch('/api/retention/admin-backup', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId })
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Admin backup failed');
        }

        const adminData = await res.json();

        // Upload to Cloudinary
        const jsonStr = JSON.stringify(adminData);
        const blob = new Blob([jsonStr], { type: 'application/json' });
        const file = new File(
            [blob],
            `admin_full_backup_${Date.now()}.json`,
            { type: 'application/json' }
        );

        const folder = `ammonite_backups/admin/${userId}`;

        const formData = new FormData();
        formData.append('file', file);
        formData.append('upload_preset', CLOUDINARY_UPLOAD_PRESET);
        formData.append('folder', folder);
        formData.append('public_id', `admin_full_${Date.now()}`);

        const response = await fetch(
            `https://api.cloudinary.com/v1_1/${CLOUDINARY_CLOUD_NAME}/auto/upload`,
            { method: 'POST', body: formData }
        );

        const data = await response.json();
        if (data.secure_url) {
            const lastBackup = {
                url: data.secure_url,
                public_id: data.public_id,
                date: new Date().toISOString(),
                type: 'ADMIN_FULL',
                stats: adminData.stats
            };
            localStorage.setItem('last_admin_backup', JSON.stringify(lastBackup));
            return {
                success: true,
                url: data.secure_url,
                public_id: data.public_id,
                backup_date: lastBackup.date,
                stats: adminData.stats
            };
        } else {
            throw new Error(data.error?.message || 'Upload failed');
        }
    } catch (error) {
        console.error('Admin full backup failed:', error);
        return { success: false, error: error.message };
    }
}


// ============================================================
// 3. RESTORE FROM CLOUDINARY
// ============================================================

async function restoreFromCloudinary(backupUrl) {
    try {
        const response = await fetch(backupUrl);
        if (!response.ok) throw new Error('Failed to fetch backup file');
        const backupData = await response.json();

        if (!backupData.fossils || !Array.isArray(backupData.fossils)) {
            throw new Error('Invalid backup format');
        }

        return {
            success: true,
            fossils: backupData.fossils,
            backup_date: backupData.backup_date,
            tier: backupData.user_tier
        };
    } catch (error) {
        console.error('Restore failed:', error);
        return { success: false, error: error.message };
    }
}


// ============================================================
// 4. SYNC DELETE (local + Cloudinary)
// ============================================================

async function syncDelete(userId, identificationId, cloudinaryPublicId) {
    try {
        const res = await fetch('/api/retention/sync-delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: userId,
                identification_id: identificationId,
                cloudinary_public_id: cloudinaryPublicId || null
            })
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Sync delete failed');
        }

        const result = await res.json();
        return {
            success: true,
            deleted: result.deleted,
            cloudinary_deleted: result.cloudinary_deleted,
            local_deleted: result.local_deleted
        };
    } catch (error) {
        console.error('Sync delete failed:', error);
        return { success: false, error: error.message };
    }
}


// ============================================================
// 5. ADMIN MANUAL DELETE (local + Cloudinary)
// ============================================================

async function adminDelete(userId, identificationId) {
    try {
        const res = await fetch(
            `/api/retention/admin-delete/${identificationId}?user_id=${userId}`,
            { method: 'POST' }
        );

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Admin delete failed');
        }

        const result = await res.json();
        return { success: true, deleted: result.deleted };
    } catch (error) {
        console.error('Admin delete failed:', error);
        return { success: false, error: error.message };
    }
}


// ============================================================
// 6. KEEP FOREVER TOGGLE
// ============================================================

async function toggleKeepForever(identificationId, keepForever) {
    try {
        const res = await fetch('/api/retention/keep-forever', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                identification_id: identificationId,
                keep_forever: keepForever
            })
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Toggle failed');
        }

        return { success: true, keep_forever: keepForever };
    } catch (error) {
        console.error('Keep forever toggle failed:', error);
        return { success: false, error: error.message };
    }
}


// ============================================================
// 7. RETENTION STATUS
// ============================================================

async function getRetentionStatus(userId) {
    try {
        const res = await fetch(`/api/retention/status/${userId}`);
        if (!res.ok) throw new Error('Failed to get retention status');
        return await res.json();
    } catch (error) {
        console.error('Retention status failed:', error);
        return null;
    }
}


// ============================================================
// 8. ML DATA EXPORT (Admin only)
// ============================================================

async function exportMLData(userId) {
    try {
        const res = await fetch(`/api/retention/ml-export?user_id=${userId}`);
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'ML export failed');
        }

        const data = await res.json();

        // Download as JSON file
        const jsonStr = JSON.stringify(data, null, 2);
        const blob = new Blob([jsonStr], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `ml_training_data_${new Date().toISOString().slice(0, 19)}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        return { success: true, total_items: data.total_items };
    } catch (error) {
        console.error('ML export failed:', error);
        return { success: false, error: error.message };
    }
}


// ============================================================
// UTILITY FUNCTIONS
// ============================================================

function getLastBackupInfo() {
    const lastBackup = localStorage.getItem('last_cloudinary_backup');
    return lastBackup ? JSON.parse(lastBackup) : null;
}

function getLastAdminBackupInfo() {
    const lastBackup = localStorage.getItem('last_admin_backup');
    return lastBackup ? JSON.parse(lastBackup) : null;
}


// ============================================================
// EXPORT ALL FUNCTIONS
// ============================================================

window.backupToCloudinary    = backupToCloudinary;
window.adminFullBackup       = adminFullBackup;
window.restoreFromCloudinary = restoreFromCloudinary;
window.syncDelete            = syncDelete;
window.adminDelete           = adminDelete;
window.toggleKeepForever     = toggleKeepForever;
window.getRetentionStatus    = getRetentionStatus;
window.exportMLData          = exportMLData;
window.getLastBackupInfo     = getLastBackupInfo;
window.getLastAdminBackupInfo = getLastAdminBackupInfo;
