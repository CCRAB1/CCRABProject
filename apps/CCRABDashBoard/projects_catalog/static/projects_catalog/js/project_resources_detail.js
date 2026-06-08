(function () {
  class ResourceDetailDomRefs {
    constructor(rootId = "project-resource-page") {
      this.root = document.getElementById(rootId);

      this.errorBox = document.getElementById("resource-error-box");
      this.resourceTitle = document.getElementById("resource-title");
      this.aboutProjectContent = document.getElementById("about-project-content");
      this.aboutResourceContent = document.getElementById("about-resource-content");

      this.resourceCategory = document.getElementById("resource-category");
      this.resourceTypesWrap = document.getElementById("resource-types-wrap");
      this.resourceTypes = document.getElementById("resource-types");
      this.resourceLinkWrap = document.getElementById("resource-link-wrap");
      this.resourceLink = document.getElementById("resource-link");

      this.focusAreasTags = document.getElementById("focus-areas-tags");
      this.keywordsTags = document.getElementById("keywords-tags");
      this.neighborhoodsText = document.getElementById("neighborhoods-text");
    }

    get payloadScriptId() {
      return this.root?.dataset?.payloadScriptId || "project-resource-payload";
    }
  }

  class BaseRenderer {
    clearChildren(element) {
      if (!element) return;
      while (element.firstChild) {
        element.removeChild(element.firstChild);
      }
    }

    setText(element, value) {
      if (!element) return;
      if (value === null || value === undefined || value === "") {
        element.textContent = "—";
        return;
      }
      element.textContent = value;
    }
  }

  class ResourceDetailPayloadClient {
    constructor(scriptId) {
      this.scriptId = scriptId;
    }

    readPayload() {
      const scriptTag = document.getElementById(this.scriptId);
      if (!scriptTag) {
        throw new Error("Resource payload script not found.");
      }

      const raw = scriptTag.textContent || "";
      if (!raw.trim()) {
        throw new Error("Resource payload is empty.");
      }

      return JSON.parse(raw);
    }
  }

  class ResourceDetailRenderer extends BaseRenderer {
    constructor(dom) {
      super();
      this.dom = dom;
    }

    renderParagraphs(container, paragraphs, fallbackText) {
      if (!container) return;
      this.clearChildren(container);

      if (!Array.isArray(paragraphs) || paragraphs.length === 0) {
        const p = document.createElement("p");
        p.className = "has-text-grey";
        p.textContent = fallbackText;
        container.appendChild(p);
        return;
      }

      for (const paragraph of paragraphs) {
        const p = document.createElement("p");
        p.textContent = paragraph;
        container.appendChild(p);
      }
    }

    renderTags(container, values) {
      if (!container) return;
      this.clearChildren(container);

      if (!Array.isArray(values) || values.length === 0) {
        const span = document.createElement("span");
        span.className = "tag is-light";
        span.textContent = "—";
        container.appendChild(span);
        return;
      }

      for (const value of values) {
        const span = document.createElement("span");
        span.className = "tag is-light";
        span.textContent = value;
        container.appendChild(span);
      }
    }

    renderResourceTypes(types) {
      if (!this.dom.resourceTypesWrap || !this.dom.resourceTypes) return;

      if (!Array.isArray(types) || types.length === 0) {
        this.dom.resourceTypesWrap.hidden = true;
        this.setText(this.dom.resourceTypes, "—");
        return;
      }

      this.dom.resourceTypesWrap.hidden = false;
      this.dom.resourceTypes.textContent = types.join(", ");
    }

    renderResourceLink(url) {
      if (!this.dom.resourceLinkWrap || !this.dom.resourceLink) return;

      if (!url) {
        this.dom.resourceLinkWrap.hidden = true;
        this.dom.resourceLink.href = "#";
        return;
      }

      this.dom.resourceLinkWrap.hidden = false;
      this.dom.resourceLink.href = url;
    }

    renderNeighborhoods(neighborhoods) {
      if (!this.dom.neighborhoodsText) return;

      if (!Array.isArray(neighborhoods) || neighborhoods.length === 0) {
        this.dom.neighborhoodsText.classList.add("has-text-grey");
        this.dom.neighborhoodsText.textContent = "—";
        return;
      }

      this.dom.neighborhoodsText.classList.remove("has-text-grey");
      this.dom.neighborhoodsText.textContent = neighborhoods.join("; ");
    }

    render(payload) {
      this.setText(this.dom.resourceTitle, payload.resource_title);
      this.setText(this.dom.resourceCategory, payload.resource_category);

      this.renderParagraphs(
        this.dom.aboutProjectContent,
        payload.about_project_paragraphs,
        "Project details are not available.",
      );
      this.renderParagraphs(
        this.dom.aboutResourceContent,
        payload.about_resource_paragraphs,
        "Resource details are not available.",
      );

      this.renderResourceTypes(payload.resource_types);
      this.renderResourceLink(payload.resource_external_url);
      this.renderTags(this.dom.focusAreasTags, payload.focus_areas);
      this.renderTags(this.dom.keywordsTags, payload.keywords);
      this.renderNeighborhoods(payload.neighborhoods);
    }
  }

  class ResourceDetailController {
    constructor({ dom, payloadClient, renderer }) {
      this.dom = dom;
      this.payloadClient = payloadClient;
      this.renderer = renderer;
    }

    showError(message) {
      if (!this.dom.errorBox) return;
      this.dom.errorBox.hidden = false;
      this.dom.errorBox.textContent = message;
    }

    init() {
      if (!this.dom.root) return;

      try {
        const payload = this.payloadClient.readPayload();
        this.renderer.render(payload);
      } catch (error) {
        this.showError(error?.message || "Failed to load resource details.");
      }
    }
  }

  const dom = new ResourceDetailDomRefs();
  const payloadClient = new ResourceDetailPayloadClient(dom.payloadScriptId);
  const renderer = new ResourceDetailRenderer(dom);
  const controller = new ResourceDetailController({ dom, payloadClient, renderer });
  controller.init();
})();
