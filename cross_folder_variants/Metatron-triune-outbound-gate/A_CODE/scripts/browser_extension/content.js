/**
 * Seraph AI Browser Shield - Content Script
 * Runs on every page to detect threats in real-time
 */

(function() {
  'use strict';
  
  // Check if already injected
  if (window.__seraphShieldInjected) return;
  window.__seraphShieldInjected = true;
  
  /**
   * XSS Detection
   */
  function detectXSS() {
    // Monitor DOM for XSS payloads
    const xssPatterns = [
      /<script[^>]*>.*?<\/script>/gi,
      /javascript:/gi,
      /on\w+\s*=\s*["']?[^"']*["']?/gi,
      /eval\s*\(/gi,
      /document\.cookie/gi,
      /document\.write/gi,
      /innerHTML\s*=/gi,
      /\.src\s*=\s*['"]?data:/gi
    ];
    
    // Check URL for XSS
    const url = window.location.href;
    for (const pattern of xssPatterns) {
      if (pattern.test(decodeURIComponent(url))) {
        chrome.runtime.sendMessage({ 
          type: 'reportXSS', 
          payload: url.substring(0, 500) 
        });
        console.warn('[Seraph Shield] XSS attempt detected in URL');
        return true;
      }
    }
    
    return false;
  }
  
  /**
   * Phishing Detection
   */
  function detectPhishing() {
    const indicators = [];
    
    // Check for password fields on non-HTTPS pages
    const passwordFields = document.querySelectorAll('input[type="password"]');
    if (passwordFields.length > 0 && window.location.protocol !== 'https:') {
      indicators.push('insecure_password');
    }
    
    // Check for suspicious form actions
    const forms = document.querySelectorAll('form');
    for (const form of forms) {
      const action = form.action || '';
      if (action && !action.startsWith(window.location.origin)) {
        // Cross-origin form submission
        if (form.querySelector('input[type="password"]')) {
          indicators.push('cross_origin_password_form');
        }
      }
    }
    
    // Check page title vs URL mismatch (common phishing indicator)
    const title = document.title.toLowerCase();
    const hostname = window.location.hostname.toLowerCase();
    const brandMismatches = ['paypal', 'amazon', 'google', 'microsoft', 'apple', 'facebook', 'netflix', 'bank'];
    
    for (const brand of brandMismatches) {
      if (title.includes(brand) && !hostname.includes(brand)) {
        indicators.push('title_hostname_mismatch');
        break;
      }
    }
    
    // Check for suspicious login text without proper domain
    const pageText = document.body?.innerText?.toLowerCase() || '';
    if (pageText.includes('verify your account') || 
        pageText.includes('confirm your identity') ||
        pageText.includes('suspended') && pageText.includes('login')) {
      indicators.push('suspicious_urgency_text');
    }
    
    return indicators;
  }
  
  /**
   * Cryptojacking Detection
   */
  function detectCryptojacking() {
    // Check for high CPU usage scripts
    const scripts = document.querySelectorAll('script[src]');
    const cryptoIndicators = ['coinhive', 'cryptonight', 'miner', 'monero', 'webminer'];
    
    for (const script of scripts) {
      const src = script.src.toLowerCase();
      for (const indicator of cryptoIndicators) {
        if (src.includes(indicator)) {
          return true;
        }
      }
    }
    
    // Check inline scripts
    const inlineScripts = document.querySelectorAll('script:not([src])');
    for (const script of inlineScripts) {
      const content = script.textContent.toLowerCase();
      if (content.includes('cryptonight') || 
          content.includes('webassembly') && content.includes('miner')) {
        return true;
      }
    }
    
    return false;
  }
  
  /**
   * Keylogger Detection
   */
  function detectKeylogger() {
    // Check for suspicious event listeners
    const suspiciousListeners = [];
    
    // Monitor for key capture attempts
    const originalAddEventListener = EventTarget.prototype.addEventListener;
    EventTarget.prototype.addEventListener = function(type, listener, options) {
      if (type === 'keydown' || type === 'keyup' || type === 'keypress') {
        // Check if this might be a keylogger
        const listenerStr = listener.toString();
        if (listenerStr.includes('XMLHttpRequest') || 
            listenerStr.includes('fetch') ||
            listenerStr.includes('sendBeacon')) {
          console.warn('[Seraph Shield] Suspicious key capture detected');
          suspiciousListeners.push({ type, suspicious: true });
        }
      }
      return originalAddEventListener.call(this, type, listener, options);
    };
    
    return suspiciousListeners.length > 0;
  }
  
  /**
   * Clickjacking Detection
   */
  function detectClickjacking() {
    // Check if page is in an iframe
    if (window.self !== window.top) {
      // We're in an iframe - check if this is suspicious
      try {
        // This will throw if cross-origin
        const parentUrl = window.parent.location.href;
      } catch (e) {
        // Cross-origin iframe - potential clickjacking
        console.warn('[Seraph Shield] Cross-origin iframe detected');
        return true;
      }
    }
    
    // Check for invisible overlays
    const allElements = document.querySelectorAll('*');
    for (const el of allElements) {
      const style = window.getComputedStyle(el);
      if (style.opacity === '0' && 
          (style.position === 'absolute' || style.position === 'fixed') &&
          parseInt(style.zIndex) > 1000) {
        console.warn('[Seraph Shield] Suspicious invisible overlay detected');
        return true;
      }
    }
    
    return false;
  }
  
  /**
   * Data Exfiltration Detection
   */
  function monitorDataExfiltration() {
    // Monitor fetch/XHR for suspicious data sends
    const originalFetch = window.fetch;
    window.fetch = function(url, options) {
      if (options?.body) {
        const bodyStr = typeof options.body === 'string' ? options.body : '';
        if (bodyStr.includes('password') || 
            bodyStr.includes('credit') || 
            bodyStr.includes('ssn')) {
          console.warn('[Seraph Shield] Potential data exfiltration detected');
          chrome.runtime.sendMessage({
            type: 'reportXSS',
            payload: `Data exfiltration to ${url}`
          });
        }
      }
      return originalFetch.apply(this, arguments);
    };
    
    // Monitor sendBeacon
    const originalSendBeacon = navigator.sendBeacon;
    if (originalSendBeacon) {
      navigator.sendBeacon = function(url, data) {
        console.log('[Seraph Shield] sendBeacon intercepted:', url);
        return originalSendBeacon.apply(this, arguments);
      };
    }
  }
  
  /**
   * Analyze page and report to background
   */
  function analyzePage() {
    const forms = Array.from(document.querySelectorAll('form')).map(f => ({
      action: f.action,
      method: f.method,
      hasPasswordField: !!f.querySelector('input[type="password"]')
    }));
    
    const scripts = Array.from(document.querySelectorAll('script:not([src])'))
      .map(s => s.textContent?.substring(0, 200) || '');
    
    chrome.runtime.sendMessage({
      type: 'contentAnalysis',
      data: {
        url: window.location.href,
        isHttps: window.location.protocol === 'https:',
        forms,
        scripts
      }
    });
  }
  
  /**
   * Show warning banner for threats
   */
  function showWarningBanner(message) {
    const banner = document.createElement('div');
    banner.id = 'seraph-warning-banner';
    banner.innerHTML = `
      <div style="
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        background: linear-gradient(135deg, #ef4444, #dc2626);
        color: white;
        padding: 12px 20px;
        z-index: 999999;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        display: flex;
        align-items: center;
        justify-content: space-between;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
      ">
        <div style="display: flex; align-items: center; gap: 12px;">
          <span style="font-size: 24px;">🛡️</span>
          <div>
            <strong>Seraph Shield Warning</strong><br>
            <span style="font-size: 13px; opacity: 0.9;">${message}</span>
          </div>
        </div>
        <button onclick="this.parentElement.parentElement.remove()" style="
          background: rgba(255,255,255,0.2);
          border: none;
          color: white;
          padding: 8px 16px;
          border-radius: 4px;
          cursor: pointer;
        ">Dismiss</button>
      </div>
    `;
    document.body.prepend(banner);
  }
  
  /**
   * Initialize protection
   */
  function init() {
    // Wait for DOM
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', runChecks);
    } else {
      runChecks();
    }
  }
  
  function runChecks() {
    // XSS check
    if (detectXSS()) {
      showWarningBanner('⚠️ Potential XSS attack detected on this page');
    }
    
    // Phishing check
    const phishingIndicators = detectPhishing();
    if (phishingIndicators.length > 0) {
      if (phishingIndicators.includes('insecure_password')) {
        showWarningBanner('⚠️ This page has password fields but is not using HTTPS');
      }
      if (phishingIndicators.includes('title_hostname_mismatch')) {
        showWarningBanner('⚠️ This page may be impersonating another website');
      }
    }
    
    // Cryptojacking check
    if (detectCryptojacking()) {
      showWarningBanner('⚠️ Cryptocurrency mining script detected');
    }
    
    // Setup ongoing monitoring
    monitorDataExfiltration();
    detectKeylogger();
    
    // Analyze page
    analyzePage();
    
    console.log('[Seraph Shield] Page protection active');
  }
  
  init();
})();
