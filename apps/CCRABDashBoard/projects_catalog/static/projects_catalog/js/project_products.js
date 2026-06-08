(function () {
  class ProductCardTemplateModel {
    kindFromDataType(dataType)
    {
      const dt = String(dataType || "").toLowerCase();
      if (!dt)
        return null;
      if (/(map|storymap|gis|spatial)/.test(dt))
        return "map";
      if (/(video|photo|image|media|multimedia|gallery)/.test(dt))
        return "media";
      if (/(report|paper|publication|brief|pdf|document|docx?)/.test(dt))
        return "document";
      if (/(data|dataset|csv|api|database|table|download)/.test(dt))
        return "data";
      return "link";
    }

    inferProductKind(categoryName, item) {
      const parts = [];
      const candidates = [categoryName, item?.data_type, item?.data_summary, item?.url];
      for (const candidate of candidates) {
        if (candidate) {
          parts.push(String(candidate));
        }
      }
      const haystack = parts.join(" ").toLowerCase();

      if (/(map|storymap|gis|spatial)/.test(haystack)) return "map";
      if (/(video|photo|image|media|multimedia|gallery)/.test(haystack)) return "media";
      if (/(report|paper|publication|brief|pdf|document|docx?)/.test(haystack)) return "document";
      if (/(data|dataset|csv|api|database|table|download)/.test(haystack)) return "data";
      return "link";
    }

    selectProductIconKind(dataType, categoryName, item) {
      return this.kindFromDataType(dataType) || this.inferProductKind(categoryName, item);
    }

    productIconSvg(kind) {
      if (kind === "data") {
        return '<svg viewBox="0 0 24 24" aria-hidden="true"><ellipse cx="12" cy="5.5" rx="6.5" ry="2.5"></ellipse><path d="M5.5 5.5v5c0 1.4 2.9 2.5 6.5 2.5s6.5-1.1 6.5-2.5v-5"></path><path d="M5.5 10.5v5c0 1.4 2.9 2.5 6.5 2.5s6.5-1.1 6.5-2.5v-5"></path></svg>';
      }
      if (kind === "document") {
        return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 3.5h6l4 4V20a.5.5 0 0 1-.5.5h-9A2.5 2.5 0 0 1 6 18V6a2.5 2.5 0 0 1 2-2.5Z"></path><path d="M14 3.5V8h4"></path><path d="M9 12h6"></path><path d="M9 15h6"></path></svg>';
      }
      if (kind === "map") {
        return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3.5 6.5 8 4l8 3.5 4.5-2v12L16 20l-8-3.5-4.5 2Z"></path><path d="M8 4v12.5"></path><path d="M16 7.5V20"></path></svg>';
      }
      if (kind === "media") {
        return '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="5" width="16" height="14" rx="2"></rect><path d="m11 10 5 2.5-5 2.5Z"></path></svg>';
      }
      return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 10h4.5a3.5 3.5 0 0 1 0 7H14"></path><path d="M10 14H5.5a3.5 3.5 0 0 1 0-7H10"></path><path d="M8.5 12h7"></path></svg>';
    }

    fromCategory(categoryName, items) {
      const safeItems = Array.isArray(items) ? items : [];
      const firstItem = safeItems[0] || {};
      const category = categoryName || "Uncategorized";
      const iconKind = this.selectProductIconKind(firstItem.data_type, category, firstItem);

      const links = [];
      for (const item of safeItems) {
        const safeItem = item || {};
        const detailUrl = safeItem.resource_detail_url || null;
        const externalUrl = safeItem.url || null;
        const href = detailUrl || externalUrl;
        if (!href) {
          continue;
        }

        const linkLabel = safeItem.data_summary || safeItem.data_type || safeItem.url;
        const opensExternally = !detailUrl;
        links.push({
          href,
          label: linkLabel,
          target: opensExternally ? "_blank" : "",
          rel: opensExternally ? "noopener noreferrer" : "",
        });
      }

      return {
        category,
        title: "Resources",
        iconKind,
        iconSvg: this.productIconSvg(iconKind),
        links,
      };
    }

    cloneTemplateElement(template) {
      if (!(template instanceof HTMLTemplateElement)) {
        return null;
      }
      return template.content.firstElementChild?.cloneNode(true) || null;
    }

    buildFallbackProductLink(linkModel) {
      const li = document.createElement("li");
      const anchor = document.createElement("a");
      anchor.setAttribute("data-role", "product-link");
      anchor.href = linkModel.href;
      anchor.textContent = linkModel.label;
      li.appendChild(anchor);
      return li;
    }

    buildFallbackEmptyLinks() {
      const li = document.createElement("li");
      li.className = "is-size-7 has-text-grey";
      li.textContent = "No links available.";
      return li;
    }

    clearChildren(el) {
      if (!el) return;
      while (el.firstChild) {
        el.removeChild(el.firstChild);
      }
    }

    handleProductCategory(categoryEl, cardModel) {
      if (!categoryEl) {
        return;
      }
      categoryEl.textContent = cardModel.category;
    }

    handleProductTitle(titleEl, cardModel) {
      if (!titleEl) {
        return;
      }
      titleEl.textContent = cardModel.title;
    }

    handleProductIcon(iconEl, cardModel) {
      if (!iconEl) {
        return;
      }

      iconEl.dataset.kind = cardModel.iconKind;
      iconEl.innerHTML = cardModel.iconSvg;
    }

    handleProductLink(linkEl, linkModel) {
      const anchor = linkEl.querySelector("[data-role='product-link']");
      if (!anchor) {
        return;
      }

      anchor.href = linkModel.href;
      anchor.textContent = linkModel.label;
      if (linkModel.target) {
        anchor.target = linkModel.target;
      }
      if (linkModel.rel) {
        anchor.rel = linkModel.rel;
      }
    }

    handleProductLinks(linksEl, cardModel, templates) {
      const safeTemplates = templates || {};
      if (!linksEl) {
        return;
      }

      this.clearChildren(linksEl);

      if (Array.isArray(cardModel.links) && cardModel.links.length > 0) {
        for (const linkModel of cardModel.links) {
          const linkEl = (
            this.cloneTemplateElement(safeTemplates.productLinkTemplate)
            || this.buildFallbackProductLink(linkModel)
          );
          this.handleProductLink(linkEl, linkModel);
          linksEl.appendChild(linkEl);
        }
        return;
      }

      const emptyLinksEl = (
        this.cloneTemplateElement(safeTemplates.productLinksEmptyTemplate)
        || this.buildFallbackEmptyLinks()
      );
      linksEl.appendChild(emptyLinksEl);
    }

    bind(card, cardModel, templates) {
      const safeTemplates = templates || {};
      const categoryEl = card.querySelector("[data-role='product-category']");
      const titleEl = card.querySelector("[data-role='product-title']");
      const linksEl = card.querySelector("[data-role='product-links']");
      const iconEl = card.querySelector("[data-role='product-icon']");

      this.handleProductCategory(categoryEl, cardModel);
      this.handleProductTitle(titleEl, cardModel);
      this.handleProductIcon(iconEl, cardModel);
      this.handleProductLinks(linksEl, cardModel, safeTemplates);
    }
  }

  class ProjectProductsRenderer {
    constructor(dom, productCardTemplateModel) {
      this.dom = dom;
      this.productCardTemplateModel = productCardTemplateModel;
    }

    clearChildren(el) {
      if (!el) return;
      while (el.firstChild) el.removeChild(el.firstChild);
    }

    cloneTemplateElement(template) {
      if (!(template instanceof HTMLTemplateElement)) {
        return null;
      }
      return template.content.firstElementChild?.cloneNode(true) || null;
    }

    buildFallbackMessage(message) {
      const col = document.createElement("div");
      col.className = "column is-12";

      const p = document.createElement("p");
      p.className = "has-text-grey";
      p.textContent = message;

      col.appendChild(p);
      return col;
    }

    appendTemplateOrFallback(container, template, fallbackMessage) {
      const el = (
        this.cloneTemplateElement(template)
        || this.buildFallbackMessage(fallbackMessage)
      );
      container.appendChild(el);
    }

    getProductCardTemplates() {
      return {
        productLinkTemplate: this.dom.productLinkTemplate,
        productLinksEmptyTemplate: this.dom.productLinksEmptyTemplate,
      };
    }

    renderProducts(productsPayload) {
      const {
        productsBlock,
        productsCallout,
        productCardTemplate,
        productsEmptyTemplate,
        productsTemplateMissingTemplate,
      } = this.dom;
      if (!productsBlock || !productsCallout) return;

      this.clearChildren(productsBlock);

      const categories = productsPayload?.categories || {};
      if (!(productCardTemplate instanceof HTMLTemplateElement)) {
        this.appendTemplateOrFallback(
          productsBlock,
          productsTemplateMissingTemplate,
          "Product card template is missing."
        );
        return;
      }

      const categoryEntries = [];
      if (categories && typeof categories === "object" && !Array.isArray(categories)) {
        for (const categoryName in categories) {
          if (!Object.prototype.hasOwnProperty.call(categories, categoryName)) {
            continue;
          }
          const categoryItems = categories[categoryName];
          const items = Array.isArray(categoryItems) ? categoryItems : [];
          categoryEntries.push({ categoryName, items });
        }
      }

      if (categoryEntries.length === 0) {
        this.appendTemplateOrFallback(
          productsBlock,
          productsEmptyTemplate,
          "No products listed."
        );
        return;
      }

      const productCardTemplates = this.getProductCardTemplates();
      for (const entry of categoryEntries) {
        const card = this.cloneTemplateElement(productCardTemplate);
        if (!card) continue;

        const cardModel = this.productCardTemplateModel.fromCategory(entry.categoryName, entry.items);
        this.productCardTemplateModel.bind(card, cardModel, productCardTemplates);
        productsBlock.appendChild(card);
      }
    }
  }

  window.ProductCardTemplateModel = ProductCardTemplateModel;
  window.ProjectProductsRenderer = ProjectProductsRenderer;
})();
