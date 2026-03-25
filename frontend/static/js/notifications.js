/**
 * notifications.js — Browser push notification manager
 * 
 * Handles:
 *  - Permission requests
 *  - Sending desktop notifications
 *  - Persisting notification settings
 */

const NotificationManager = {
    settingsKey: 'desktop_notifications_enabled',

    init() {
        this.updateCheckbox();
    },

    isEnabled() {
        return localStorage.getItem(this.settingsKey) === 'true';
    },

    async requestPermission() {
        if (!("Notification" in window)) {
            console.warn("This browser does not support desktop notification");
            showToast("Desktop notifications are not supported by your browser.", "warning");
            return false;
        }

        if (Notification.permission === "granted") {
            return true;
        }

        const permission = await Notification.requestPermission();
        if (permission === "granted") {
            showToast("Desktop notifications enabled successfully!", "success");
            return true;
        } else {
            showToast("Notification permission denied.", "error");
            return false;
        }
    },

    async toggleNotifications(enabled) {
        if (enabled) {
            const granted = await this.requestPermission();
            if (granted) {
                localStorage.setItem(this.settingsKey, 'true');
            } else {
                localStorage.setItem(this.settingsKey, 'false');
                this.updateCheckbox();
            }
        } else {
            localStorage.setItem(this.settingsKey, 'false');
            showToast("Desktop notifications disabled.", "info");
        }
    },

    sendNotification(title, body, icon = '/static/images/Title_Image.png') {
        if (!this.isEnabled()) return;

        if (Notification.permission === "granted") {
            const options = {
                body: body,
                icon: icon,
                badge: icon,
                timestamp: Date.now(),
            };
            const n = new Notification(title, options);
            
            n.onclick = () => {
                window.focus();
                n.close();
            };
        }
    },

    updateCheckbox() {
        const checkbox = document.getElementById('notificationToggle');
        if (checkbox) {
            checkbox.checked = this.isEnabled();
        }
    }
};

// Initialize notification system
document.addEventListener('DOMContentLoaded', () => {
    NotificationManager.init();
});
