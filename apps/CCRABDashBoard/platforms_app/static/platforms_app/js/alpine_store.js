import Alpine from "alpinejs";

/** A key/value interface to a named, reactive Alpine store. */
export class AlpineStore {
    constructor(name) {
        if (typeof name !== "string" || name.trim() === "") {
            throw new TypeError("An Alpine store name must be a non-empty string.");
        }

        this.name = name;

        if (Alpine.store(name) === undefined) {
            Alpine.store(name, {});
        }

        const store = Alpine.store(name);
        if (store === null || typeof store !== "object" || Array.isArray(store)) {
            throw new TypeError("AlpineStore requires an object-valued store.");
        }
    }

    /** Set a property and return its stored value. */
    set(key, value) {
        Alpine.store(this.name)[key] = value;
        return this.get(key);
    }

    /** Return a property, or undefined when the key is missing. */
    get(key) {
        const store = Alpine.store(this.name);
        return Object.prototype.hasOwnProperty.call(store, key) ? store[key] : undefined;
    }

    /** Remove a property; return whether it existed and was deleted. */
    delete(key) {
        const store = Alpine.store(this.name);
        if (!Object.prototype.hasOwnProperty.call(store, key)) {
            return false;
        }

        return delete store[key];
    }
}
