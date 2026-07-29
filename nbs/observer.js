// observer.js
// @ts-check

/**
 * @typedef {Object} ObserverConfig
 * @property {Element} target - Element to observe or null
 * @property {MutationObserverInit} options - Observer configuration
 * @property {Set<MutationCallback|{callback: MutationCallback, selector: string}>} callbacks - Set of callbacks
 */

/**
 * Normalize callback param: function (records pattern) or {callback, selector} (selector pattern)
 * @param {MutationCallback|{callback: MutationCallback, selector: string}} entry
 * @returns {MutationCallback|{callback: MutationCallback, selector: string}|null}
 */
function _normalizeCallback(entry) {
    if (typeof entry === 'function') return entry;
    if (entry && typeof entry.callback === 'function' && typeof entry.selector === 'string') return entry;
    return null;
}

/**
 * Find callback entry in Set by function reference
 * @param {Set<MutationCallback|{callback: MutationCallback, selector: string}>} callbacks
 * @param {MutationCallback|{callback: MutationCallback, selector: string}} ref
 * @returns {MutationCallback|{callback: MutationCallback, selector: string}|null}
 */
function _findCallback(callbacks, ref) {
    const fn = typeof ref === 'function' ? ref : ref?.callback;
    if (!fn) return null;
    for (const entry of callbacks) {
        if (entry === ref || (typeof entry === 'object' && entry?.callback === fn)) return entry;
    }
    return null;
}

class ObserverManager {
    constructor() {
        this.observers = new Map();  // name -> {observer, target, options, callbacks}
        this.active = new Set();
    }

    has(name) { return this.observers.has(name); }

    /**
     * Register a new observer or add callback to existing observer.
     * Callback: function (records pattern) or {callback, selector} (selector pattern; receives elements).
     * @param {string} name - Observer name
     * @param {{target: Element|null, options: MutationObserverInit}} config - Observer configuration
     * @param {MutationCallback|{callback: MutationCallback, selector: string}} callback - Callback or {callback, selector}
     * @param {boolean} [autostart=false] - Start observing immediately
     * @param {boolean} [append=false] - Add callback to existing observer
     * @returns {boolean} - True if registered or callbacks added
     */
    register(name, { target, options }, callback, autostart=false, append=false) {
        const entry = _normalizeCallback(callback);
        if (!entry) return false;
        if (this.has(name)) {
            if (!append) return false;
            this.addCallback(name, entry);
        } else {
            const callbacks = new Set([entry]);
            const observer = new MutationObserver(records => {
                const config = this.observers.get(name);
                if (!config) return;
                config.callbacks.forEach(cb => {
                    try {
                        if (typeof cb === 'function') cb(records);
                        else if (config.target) cb.callback([...config.target.querySelectorAll(cb.selector)]);
                        else cb.callback([]);
                    } catch (e) { console.error('[ObserverManager] callback error:', e); }
                });
            });
            this.observers.set(name, {observer, target, options, callbacks});
        }
        if (autostart) this.start(name);
        return true;
    }

    isEmpty(name) { return !this.has(name) || this.observers.get(name).callbacks.size === 0; }

    /**
     * Add callback to existing observer. Callback: function or {callback, selector}
     * @param {string} name - Observer name
     * @param {MutationCallback|{callback: MutationCallback, selector: string}} callback
     * @returns {boolean}
     */
    addCallback(name, callback) {
        if (!this.has(name)) return false;
        const entry = _normalizeCallback(callback);
        if (!entry) return false;
        this.observers.get(name).callbacks.add(entry);
        return true;
    }

    /**
     * Remove callback by function or {callback, selector} reference
     * @param {string} name - Observer name
     * @param {MutationCallback|{callback: MutationCallback, selector: string}} callback
     * @returns {boolean}
     */
    removeCallback(name, callback) {
        if (!this.has(name)) return false;
        const config = this.observers.get(name);
        const entry = _findCallback(config.callbacks, callback);
        return entry ? config.callbacks.delete(entry) : false;
    }

    /**
     * Check if callback is registered
     * @param {string} name - Observer name
     * @param {MutationCallback|{callback: MutationCallback, selector: string}} callback
     * @returns {boolean}
     */
    hasCallback(name, callback) {
        if (!this.has(name)) return false;
        return _findCallback(this.observers.get(name).callbacks, callback) !== null;
    }

    unregister(name) {
        if (!this.has(name)) return;
        const config = this.observers.get(name);
        this.stop(name);
        config.callbacks.clear();
        this.observers.delete(name);
    }

    isActive(name) { return this.active.has(name); }

    /**
     * @param {string} name - Observer name
     * @param {{target?: Element|null, options?: MutationObserverInit}} [opts] - Optional overrides
     */
    start(name, { target:_target, options:_options } = {}) {
        if (!this.has(name) || this.isActive(name)) return;
        const config = this.observers.get(name);
        // Must provide new target if previous was removed
        if (!config.target && !_target) return;
        const finalConfig = {
            ...config,
            target: _target ?? config.target,
            options: _options ?? config.options
        };
        this.observers.set(name, finalConfig);
        finalConfig.observer.observe(finalConfig.target, finalConfig.options);
        this.active.add(name);
    }

    stop(name, { removeTarget=false } = {}) {
        if (!this.has(name) || !this.isActive(name)) return;
        const config = this.observers.get(name);
        config.observer.disconnect();
        if (removeTarget) config.target = null;  // Mark target as needing replacement
        this.active.delete(name);
    }

}

/** Get or create the global ObserverManager instance
 * @returns {ObserverManager}
 */
export function getObserverManager() {
    window.observerManager ??= new ObserverManager();
    return window.observerManager;
}
