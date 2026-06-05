// static/cloudinary-backup.js
// Cloudinary Backup Module for Premium Users
// Requires Cloudinary SDK: https://upload-widget.cloudinary.com/global/upload.js

const CLOUDINARY_CLOUD_NAME = 'dds5rebi2';
const CLOUDINARY_UPLOAD_PRESET = 'ammonite_backup';

// Backup entire collection to Cloudinary
async function backupToCloudinary(userId, fossilData) {
    if (!userId || !fossilData || fossilData.length === 0) {
        console.warn('No data to backup');
        return { success: false, error: 'No data to backup' };
    }

    const backupData = {
        user_id: userId,
        backup_date: new Date().toISOString(),
        fossil_count: fossilData.length,
        fossils: fossilData,
        app_version: '1.0'
    };

    const jsonStr = JSON.stringify(backupData);
    const blob = new Blob([jsonStr], { type: 'application/json' });
    const file = new File([blob], `backup_${userId}_${Date.now()}.json`, { type: 'application/json' });

    const formData = new FormData();
    formData.append('file', file);
    formData.append('upload_preset', CLOUDINARY_UPLOAD_PRESET);
    formData.append('folder', `ammonite_backups/${userId}`);
    formData.append('public_id', `backup_${Date.now()}`);

    try {
        const response = await fetch(`https://api.cloudinary.com/v1_1/${CLOUDINARY_CLOUD_NAME}/auto/upload`, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        if (data.secure_url) {
            // Save backup URL to localStorage for reference
            const lastBackup = {
                url: data.secure_url,
                date: new Date().toISOString(),
                fossil_count: fossilData.length
            };
            localStorage.setItem('last_cloudinary_backup', JSON.stringify(lastBackup));
            return { success: true, url: data.secure_url, backup_date: lastBackup.date };
        } else {
            throw new Error(data.error?.message || 'Upload failed');
        }
    } catch (error) {
        console.error('Cloudinary backup failed:', error);
        return { success: false, error: error.message };
    }
}

// Restore collection from Cloudinary backup URL
async function restoreFromCloudinary(backupUrl) {
    try {
        const response = await fetch(backupUrl);
        if (!response.ok) throw new Error('Failed to fetch backup file');
        const backupData = await response.json();
        
        if (!backupData.fossils || !Array.isArray(backupData.fossils)) {
            throw new Error('Invalid backup format');
        }
        
        return { success: true, fossils: backupData.fossils, backup_date: backupData.backup_date };
    } catch (error) {
        console.error('Restore failed:', error);
        return { success: false, error: error.message };
    }
}

// Get last backup info
function getLastBackupInfo() {
    const lastBackup = localStorage.getItem('last_cloudinary_backup');
    return lastBackup ? JSON.parse(lastBackup) : null;
}

// Export functions for use in other files
window.backupToCloudinary = backupToCloudinary;
window.restoreFromCloudinary = restoreFromCloudinary;
window.getLastBackupInfo = getLastBackupInfo;