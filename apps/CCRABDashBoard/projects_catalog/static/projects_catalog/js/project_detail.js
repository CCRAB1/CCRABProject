import Alpine from 'alpinejs';
import DOMPurify from 'dompurify';

// Restrict stored rich text to document formatting. In particular, never allow
// Alpine directives from database content to become executable expressions.
export function richText(value, bullets = false) {
    const text = String(value || '').trim();
    const options = {
        ALLOWED_TAGS: ['p', 'br', 'strong', 'b', 'em', 'i', 'u', 's', 'ul', 'ol', 'li',
            'a', 'h2', 'h3', 'h4', 'blockquote', 'pre', 'code', 'table', 'thead', 'tbody', 'tr', 'th', 'td'],
        ALLOWED_ATTR: ['href', 'title'],
        ALLOW_DATA_ATTR: false,
        ALLOW_ARIA_ATTR: false,
    };
    if (/<\/?[a-z][^>]*>/i.test(text)) return DOMPurify.sanitize(text, options);
    const container = document.createElement(bullets ? 'ul' : 'div');
    for (const part of text.split(bullets ? /\r?\n/ : /\n\s*\n/)) {
        if (!part.trim()) continue;
        const node = document.createElement(bullets ? 'li' : 'p');
        node.textContent = bullets ? part.replace(/^\s*[-*]\s*/, '').trim() : part.trim();
        container.append(node);
    }
    return container.outerHTML;
}

export function safeUrl(value) {
    if (!value) return null;
    try {
        const url = new URL(value, window.location.origin);
        return ['http:', 'https:'].includes(url.protocol) ? url.href : null;
    } catch {
        return null;
    }
}

export function projectDetail() {
    return {
        projectEndpoint: '', loading: true, error: '', productsError: '', project: {}, categories: [],
        photos: [], leads: [], productTypes: [], keywords: [],
        get title() {
            return this.project.project_full_title || this.project.project_name || 'Untitled project';
        },
        richText, safeUrl,
        formatDate(value) {
            if (!value) return '—';
            const date = new Date(value);
            if (Number.isNaN(date.getTime())) return value;
            return new Intl.DateTimeFormat('en-US', {month: 'short', year: 'numeric', timeZone: 'UTC'}).format(date);
        },
        async request(url) {
            const response = await fetch(url, {headers: {Accept: 'application/json'}});
            if (!response.ok) throw new Error(`Request failed (${response.status})`);
            return response.json();
        },
        async init() {
            const base = this.$el.dataset.projectApiBase.replace(/\/$/, '');
            this.projectEndpoint = `${base}/${encodeURIComponent(this.$el.dataset.projectCode)}/`;
            await this.load();
        },
        async load() {
            this.loading = true;
            this.error = '';
            this.productsError = '';
            const url = this.projectEndpoint;
            try {
                this.project = await this.request(url);
                this.leads = Array.isArray(this.project.project_leads) ? this.project.project_leads : [];
                this.photos = [];
                for (const picture of this.project.pictures || []) {
                    if (safeUrl(picture.picture_path)) this.photos.push(picture);
                }
                this.keywords = [];
                const keywords = this.project.keywords || [];
                for (const keyword of Array.isArray(keywords) ? keywords : keywords.split(',')) {
                    if (String(keyword).trim()) this.keywords.push(String(keyword).trim());
                }
                this.productTypes = [];
                for (const location of this.project.hosting_locations || []) {
                    for (const type of location.product_types || []) {
                        if (type.name && !this.productTypes.includes(type.name)) this.productTypes.push(type.name);
                    }
                }
                this.productTypes.sort();
                document.title = this.title;
                const crumb = document.getElementById('crumb-title');
                if (crumb) crumb.textContent = this.title;
                this.categories = [];
                try {
                    const products = await this.request(`${url}products/`);
                    for (const [name, items] of Object.entries(products.categories || {})) {
                        this.categories.push({name, items});
                    }
                } catch {
                    this.productsError = 'Unable to load project products. Please try again.';
                }
            } catch {
                this.error = 'Unable to load this project. Please try again.';
            } finally {
                this.loading = false;
            }
        },
    };
}

Alpine.data('projectDetail', projectDetail);
Alpine.start();
