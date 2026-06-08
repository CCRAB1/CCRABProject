(function () {
  console.log("project_detail.js anonymous initializer");

  class ProjectDomRefs {
    constructor(rootId = "project-page") {
      console.log("project_detail.js ProjectDomRefs.constructor", { rootId });
      this.root = document.getElementById(rootId);
      this.errorBox = document.getElementById("error-box");

      this.crumbTitle = document.getElementById("crumb-title");
      this.projectFullTitle = document.getElementById("project-full-title");
      this.neighborhood = document.getElementById("neighborhood");
      this.startDate = document.getElementById("start-date");
      this.endDate = document.getElementById("end-date");
      this.projectDescriptionSummary = document.getElementById("project-description-summary");

      this.featuredWrap = document.getElementById("featured-wrap");
      this.featuredImg = document.getElementById("featured-img");
      this.projectDescription = document.getElementById("project-description");
      this.projectImpact = document.getElementById("project-impact");
      this.galleryWrap = document.getElementById("gallery-wrap");
      this.gallery = document.getElementById("gallery");

      this.prevNext = document.getElementById("prev-next");
      this.prevSlot = document.getElementById("prev-slot");
      this.nextSlot = document.getElementById("next-slot");

      this.projectLead = document.getElementById("project-lead");
      this.partners = document.getElementById("partners");

      this.projectUrl = document.getElementById("project-url");
      this.productTypes = document.getElementById("product-types");
      this.keywords = document.getElementById("keywords");

      this.productsBlock = document.getElementById("products-block");
      this.productsCallout = document.getElementById("products-callout");
      this.productCardTemplate = document.getElementById("product-card-template");
      this.productLinkTemplate = document.getElementById("product-link-template");
      this.productLinksEmptyTemplate = document.getElementById("product-links-empty-template");
      this.productsEmptyTemplate = document.getElementById("products-empty-template");
      this.productsTemplateMissingTemplate = document.getElementById(
        "products-template-missing-template"
      );

      this.theProjectParagraphTemplate = document.getElementById("the-project-paragraph-template");
      this.theProjectEmptyTemplate = document.getElementById("the-project-empty-template");
      this.impactItemTemplate = document.getElementById("impact-item-template");
      this.impactEmptyTemplate = document.getElementById("impact-empty-template");
      this.tagTemplate = document.getElementById("tag-template");
      this.tagEmptyTemplate = document.getElementById("tag-empty-template");
      this.personTemplate = document.getElementById("person-template");
      this.personEmptyTemplate = document.getElementById("person-empty-template");
      this.projectUrlLinkTemplate = document.getElementById("project-url-link-template");
      this.projectUrlEmptyTemplate = document.getElementById("project-url-empty-template");
      this.galleryCardTemplate = document.getElementById("gallery-card-template");
      this.previousProjectLinkTemplate = document.getElementById("previous-project-link-template");
      this.nextProjectLinkTemplate = document.getElementById("next-project-link-template");
    }

    get projectCode() {
      console.log("project_detail.js ProjectDomRefs.projectCode");
      return this.root?.dataset?.projectCode || "";
    }

    get apiBase() {
      console.log("project_detail.js ProjectDomRefs.apiBase");
      return (this.root?.dataset?.projectApiBase || "").replace(/\/$/, "");
    }

    get apiToken() {
      console.log("project_detail.js ProjectDomRefs.apiToken");
      return this.root?.dataset?.apiToken || "";
    }
  }

  class BaseRenderer {
    clearChildren(el) {
      console.log("project_detail.js BaseRenderer.clearChildren", { el });
      if (!el) return;
      while (el.firstChild) el.removeChild(el.firstChild);
    }

    setText(el, value) {
      console.log("project_detail.js BaseRenderer.setText", { el, value });
      if (!el) return;
      el.textContent = value === null || value === undefined || value === "" ? "—" : value;
    }

    cloneTemplateElement(template) {
      console.log("project_detail.js BaseRenderer.cloneTemplateElement", { template });
      if (!(template instanceof HTMLTemplateElement)) {
        return null;
      }
      return template.content.firstElementChild?.cloneNode(true) || null;
    }

    roleElement(root, role) {
      console.log("project_detail.js BaseRenderer.roleElement", { root, role });
      if (!root) {
        return null;
      }
      if (root.matches?.(`[data-role='${role}']`)) {
        return root;
      }
      return root.querySelector(`[data-role='${role}']`);
    }
  }

  class ProjectContentRenderer extends BaseRenderer {
    constructor(dom) {
      super();
      console.log("project_detail.js ProjectContentRenderer.constructor", { dom });
      this.dom = dom;
    }

    displayProjectTitle(project) {
      console.log("project_detail.js ProjectContentRenderer.displayProjectTitle", { project });
      return project?.project_full_title || project?.project_name || "Untitled project";
    }

    formatDate(value) {
      console.log("project_detail.js ProjectContentRenderer.formatDate", { value });
      if (!value) return "—";
      const dateValue = new Date(value);
      if (Number.isNaN(dateValue.getTime())) return String(value);
      return new Intl.DateTimeFormat("en-US", {
        month: "short",
        year: "numeric",
      }).format(dateValue);
    }

    splitParagraphs(text) {
      console.log("project_detail.js ProjectContentRenderer.splitParagraphs", { text });
      const paragraphs = [];
      if (!text) return paragraphs;

      const parts = String(text).split(/\n\s*\n/);
      for (const part of parts) {
        const cleanedPart = part.trim();
        if (cleanedPart) {
          paragraphs.push(cleanedPart);
        }
      }

      return paragraphs;
    }

    splitBullets(text) {
      console.log("project_detail.js ProjectContentRenderer.splitBullets", { text });
      const bullets = [];
      if (!text) return bullets;

      const lines = String(text).split(/\r?\n/);
      for (const line of lines) {
        const cleanedLine = line.replace(/^\s*[-*]\s*/, "").trim();
        if (cleanedLine) {
          bullets.push(cleanedLine);
        }
      }

      return bullets;
    }

    firstParagraph(text) {
      console.log("project_detail.js ProjectContentRenderer.firstParagraph", { text });
      const paragraphs = this.splitParagraphs(text);
      return paragraphs[0] || "";
    }

    normalizeTags(value) {
      console.log("project_detail.js ProjectContentRenderer.normalizeTags", { value });
      const tags = [];
      if (Array.isArray(value)) {
        for (const item of value) {
          const tag = String(item || "").trim();
          if (tag) {
            tags.push(tag);
          }
        }
        return tags;
      }

      if (typeof value === "string") {
        const parts = value.split(",");
        for (const part of parts) {
          const tag = part.trim();
          if (tag) {
            tags.push(tag);
          }
        }
      }

      return tags;
    }

    productTypeNames(hostingLocations) {
      console.log(
        "project_detail.js ProjectContentRenderer.productTypeNames",
        { hostingLocations },
      );
      const names = [];
      if (!Array.isArray(hostingLocations)) {
        return names;
      }

      for (const location of hostingLocations) {
        const productTypes = Array.isArray(location?.product_types) ? location.product_types : [];
        for (const productType of productTypes) {
          const name = productType?.name;
          if (name && !names.includes(name)) {
            names.push(name);
          }
        }
      }

      names.sort();
      return names;
    }

    projectLeadPeople(project) {
      console.log("project_detail.js ProjectContentRenderer.projectLeadPeople", { project });
      const people = [];
      if (project?.project_lead || project?.project_lead_email) {
        people.push({
          name: project.project_lead || project.project_lead_email,
          email: project.project_lead_email,
        });
      }
      return people;
    }

    partnerPeople(partners) {
      console.log("project_detail.js ProjectContentRenderer.partnerPeople", { partners });
      const people = [];
      if (!Array.isArray(partners)) {
        return people;
      }

      for (const partner of partners) {
        if (partner?.name || partner?.affiliation) {
          people.push({
            name: partner.name,
            organization: partner.affiliation,
          });
        }
      }

      return people;
    }

    buildFallbackTextElement(tagName, text, className = "") {
      console.log(
        "project_detail.js ProjectContentRenderer.buildFallbackTextElement",
        { tagName, text, className },
      );
      const el = document.createElement(tagName);
      if (className) {
        el.className = className;
      }
      el.textContent = text;
      return el;
    }

    handleProjectDescription(project) {
      console.log("project_detail.js ProjectContentRenderer.handleProjectDescription", { project });
      this.setText(
        this.dom.projectDescriptionSummary,
        this.firstParagraph(project.project_description)
      );
    }

    handleTheProject(project) {
      console.log("project_detail.js ProjectContentRenderer.handleTheProject", { project });
      const paragraphs = this.splitParagraphs(project.project_description);
      this.renderTheProject(this.dom.projectDescription, paragraphs);
    }

    handleTheProjectParagraph(paragraphEl, text) {
      console.log(
        "project_detail.js ProjectContentRenderer.handleTheProjectParagraph",
        { paragraphEl, text },
      );
      const target = this.roleElement(paragraphEl, "the-project-paragraph") || paragraphEl;
      if (!target) {
        return;
      }
      target.textContent = text;
    }

    renderTheProject(container, paragraphs) {
      console.log(
        "project_detail.js ProjectContentRenderer.renderTheProject",
        { container, paragraphs },
      );
      if (!container) return;
      this.clearChildren(container);

      if (!Array.isArray(paragraphs) || paragraphs.length === 0) {
        const emptyEl = (
          this.cloneTemplateElement(this.dom.theProjectEmptyTemplate)
          || this.buildFallbackTextElement("p", "No description available.", "has-text-grey")
        );
        container.appendChild(emptyEl);
        return;
      }

      for (const text of paragraphs) {
        const paragraphEl = (
          this.cloneTemplateElement(this.dom.theProjectParagraphTemplate)
          || this.buildFallbackTextElement("p", "")
        );
        this.handleTheProjectParagraph(paragraphEl, text);
        container.appendChild(paragraphEl);
      }
    }

    handleImpact(project) {
      console.log("project_detail.js ProjectContentRenderer.handleImpact", { project });
      const bullets = this.splitBullets(project.project_impact);
      this.renderImpact(this.dom.projectImpact, bullets);
    }

    handleImpactItem(itemEl, text) {
      console.log("project_detail.js ProjectContentRenderer.handleImpactItem", { itemEl, text });
      const target = this.roleElement(itemEl, "impact-item") || itemEl;
      if (!target) {
        return;
      }
      target.textContent = text;
    }

    renderImpact(ul, bullets) {
      console.log("project_detail.js ProjectContentRenderer.renderImpact", { ul, bullets });
      if (!ul) return;
      this.clearChildren(ul);

      if (!Array.isArray(bullets) || bullets.length === 0) {
        const emptyEl = (
          this.cloneTemplateElement(this.dom.impactEmptyTemplate)
          || this.buildFallbackTextElement("li", "No impact statements available.", "has-text-grey")
        );
        ul.appendChild(emptyEl);
        return;
      }

      for (const bullet of bullets) {
        const itemEl = (
          this.cloneTemplateElement(this.dom.impactItemTemplate)
          || this.buildFallbackTextElement("li", "")
        );
        this.handleImpactItem(itemEl, bullet);
        ul.appendChild(itemEl);
      }
    }

    handleTag(tagEl, value) {
      console.log("project_detail.js ProjectContentRenderer.handleTag", { tagEl, value });
      const target = this.roleElement(tagEl, "tag") || tagEl;
      if (!target) {
        return;
      }
      target.textContent = value;
    }

    renderTags(container, items) {
      console.log("project_detail.js ProjectContentRenderer.renderTags", { container, items });
      if (!container) return;
      this.clearChildren(container);

      if (!Array.isArray(items) || items.length === 0) {
        const emptyEl = (
          this.cloneTemplateElement(this.dom.tagEmptyTemplate)
          || this.buildFallbackTextElement("span", "—", "tag is-light")
        );
        container.appendChild(emptyEl);
        return;
      }

      for (const item of items) {
        const tagEl = (
          this.cloneTemplateElement(this.dom.tagTemplate)
          || this.buildFallbackTextElement("span", "", "tag is-light")
        );
        this.handleTag(tagEl, item);
        container.appendChild(tagEl);
      }
    }

    personLabel(person) {
      console.log("project_detail.js ProjectContentRenderer.personLabel", { person });
      const parts = [];
      if (person.name) parts.push(person.name);
      if (person.organization) parts.push(person.organization);
      if (!parts.length && person.email) parts.push(person.email);
      return parts.join(", ");
    }

    handlePerson(personEl, person) {
      console.log("project_detail.js ProjectContentRenderer.handlePerson", { personEl, person });
      if (!personEl) {
        return;
      }

      const label = this.personLabel(person);
      const link = this.roleElement(personEl, "person-link");
      const text = this.roleElement(personEl, "person-text");

      if (person.email && link) {
        link.hidden = false;
        link.href = `mailto:${person.email}`;
        link.textContent = label;
        if (text) {
          text.hidden = true;
          text.textContent = "";
        }
        return;
      }

      if (link) {
        link.hidden = true;
        link.removeAttribute("href");
        link.textContent = "";
      }

      if (text) {
        text.hidden = false;
        text.textContent = label;
        return;
      }

      this.clearChildren(personEl);
      if (person.email) {
        const fallbackLink = document.createElement("a");
        fallbackLink.href = `mailto:${person.email}`;
        fallbackLink.textContent = label;
        personEl.appendChild(fallbackLink);
        return;
      }
      personEl.textContent = label;
    }

    renderPeopleList(ul, people) {
      console.log("project_detail.js ProjectContentRenderer.renderPeopleList", { ul, people });
      if (!ul) return;
      this.clearChildren(ul);

      if (!Array.isArray(people) || people.length === 0) {
        const emptyEl = (
          this.cloneTemplateElement(this.dom.personEmptyTemplate)
          || this.buildFallbackTextElement("li", "—", "has-text-grey")
        );
        ul.appendChild(emptyEl);
        return;
      }

      for (const person of people) {
        const personEl = (
          this.cloneTemplateElement(this.dom.personTemplate)
          || this.buildFallbackTextElement("li", "")
        );
        this.handlePerson(personEl, person);
        ul.appendChild(personEl);
      }
    }

    handleProjectUrlLink(linkEl, url) {
      console.log("project_detail.js ProjectContentRenderer.handleProjectUrlLink", { linkEl, url });
      const link = this.roleElement(linkEl, "project-url-link") || linkEl;
      if (!link) {
        return;
      }
      link.href = url;
    }

    renderProjectUrl(container, url) {
      console.log("project_detail.js ProjectContentRenderer.renderProjectUrl", { container, url });
      if (!container) return;
      this.clearChildren(container);

      if (!url) {
        const emptyEl = (
          this.cloneTemplateElement(this.dom.projectUrlEmptyTemplate)
          || this.buildFallbackTextElement("span", "—", "has-text-grey")
        );
        container.appendChild(emptyEl);
        return;
      }

      const linkEl = (
        this.cloneTemplateElement(this.dom.projectUrlLinkTemplate)
        || this.buildFallbackTextElement("a", "Open project link")
      );
      this.handleProjectUrlLink(linkEl, url);
      container.appendChild(linkEl);
    }

    renderFeaturedImage(pictures, projectTitle) {
      console.log(
        "project_detail.js ProjectContentRenderer.renderFeaturedImage",
        { pictures, projectTitle },
      );
      if (!this.dom.featuredWrap || !this.dom.featuredImg) return;

      let featuredPicture = null;
      if (Array.isArray(pictures)) {
        for (const picture of pictures) {
          if (picture?.picture_path) {
            featuredPicture = picture;
            break;
          }
        }
      }

      if (!featuredPicture) {
        this.dom.featuredWrap.hidden = true;
        return;
      }

      this.dom.featuredWrap.hidden = false;
      this.dom.featuredImg.src = featuredPicture.picture_path;
      this.dom.featuredImg.alt = featuredPicture.name || projectTitle || "Project photo";
    }

    buildFallbackGalleryCard() {
      console.log("project_detail.js ProjectContentRenderer.buildFallbackGalleryCard");
      const col = document.createElement("div");
      col.className = "column is-6";

      const card = document.createElement("div");
      card.className = "card gallery-card";

      const cardImage = document.createElement("div");
      cardImage.className = "card-image";

      const figure = document.createElement("figure");
      figure.className = "image is-4by3";

      const image = document.createElement("img");
      image.setAttribute("data-role", "gallery-image");
      image.alt = "";

      const cardContent = document.createElement("div");
      cardContent.className = "card-content";

      const caption = document.createElement("p");
      caption.className = "is-size-7 has-text-grey";
      caption.setAttribute("data-role", "gallery-caption");

      figure.appendChild(image);
      cardImage.appendChild(figure);
      cardContent.appendChild(caption);
      card.appendChild(cardImage);
      card.appendChild(cardContent);
      col.appendChild(card);

      return col;
    }

    handleGalleryCard(cardEl, picture, projectTitle) {
      console.log(
        "project_detail.js ProjectContentRenderer.handleGalleryCard",
        { cardEl, picture, projectTitle },
      );
      const image = this.roleElement(cardEl, "gallery-image");
      if (image) {
        image.src = picture.picture_path;
        image.alt = picture.name || projectTitle || "Project photo";
      }

      const caption = this.roleElement(cardEl, "gallery-caption");
      if (caption) {
        caption.textContent = picture.name || "";
      }
    }

    renderGallery(pictures, projectTitle) {
      console.log(
        "project_detail.js ProjectContentRenderer.renderGallery",
        { pictures, projectTitle },
      );
      const { galleryWrap, gallery: galleryGrid } = this.dom;
      if (!galleryWrap || !galleryGrid) return;

      this.clearChildren(galleryGrid);

      const galleryPictures = [];
      if (Array.isArray(pictures)) {
        for (const picture of pictures) {
          if (picture?.picture_path) {
            galleryPictures.push(picture);
          }
        }
      }

      if (galleryPictures.length === 0) {
        galleryWrap.hidden = true;
        return;
      }

      galleryWrap.hidden = false;

      for (const picture of galleryPictures) {
        const cardEl = (
          this.cloneTemplateElement(this.dom.galleryCardTemplate)
          || this.buildFallbackGalleryCard()
        );
        this.handleGalleryCard(cardEl, picture, projectTitle);
        galleryGrid.appendChild(cardEl);
      }
    }

    buildFallbackPrevNextLink() {
      console.log("project_detail.js ProjectContentRenderer.buildFallbackPrevNextLink");
      const link = document.createElement("a");
      link.className = "button is-link is-light";
      link.setAttribute("data-role", "prev-next-link");
      return link;
    }

    handlePrevNextLink(linkEl, project, direction) {
      console.log(
        "project_detail.js ProjectContentRenderer.handlePrevNextLink",
        { linkEl, project, direction },
      );
      const link = this.roleElement(linkEl, "prev-next-link") || linkEl;
      if (!link) {
        return;
      }

      const label = this.displayProjectTitle(project);
      link.href = project.project_detail_url;

      const labelEl = this.roleElement(linkEl, "prev-next-label");
      if (labelEl) {
        labelEl.textContent = label;
        return;
      }

      if (direction === "previous") {
        link.textContent = `← ${label}`;
        return;
      }
      link.textContent = `${label} →`;
    }

    renderPrevNext(previousProject, nextProject) {
      console.log(
        "project_detail.js ProjectContentRenderer.renderPrevNext",
        { previousProject, nextProject },
      );
      const { prevNext, prevSlot, nextSlot } = this.dom;
      if (!prevNext || !prevSlot || !nextSlot) return;

      this.clearChildren(prevSlot);
      this.clearChildren(nextSlot);

      if (!previousProject && !nextProject) {
        prevNext.hidden = true;
        return;
      }

      prevNext.hidden = false;

      if (previousProject?.project_detail_url) {
        const previousLink = (
          this.cloneTemplateElement(this.dom.previousProjectLinkTemplate)
          || this.buildFallbackPrevNextLink()
        );
        this.handlePrevNextLink(previousLink, previousProject, "previous");
        prevSlot.appendChild(previousLink);
      }

      if (nextProject?.project_detail_url) {
        const nextLink = (
          this.cloneTemplateElement(this.dom.nextProjectLinkTemplate)
          || this.buildFallbackPrevNextLink()
        );
        this.handlePrevNextLink(nextLink, nextProject, "next");
        nextSlot.appendChild(nextLink);
      }
    }

    renderProject(project) {
      console.log("project_detail.js ProjectContentRenderer.renderProject", { project });
      const title = this.displayProjectTitle(project);
      this.setText(this.dom.crumbTitle, title);
      this.setText(this.dom.projectFullTitle, title);

      this.setText(this.dom.neighborhood, project.neighborhood);
      this.setText(this.dom.startDate, this.formatDate(project.start_date));
      this.setText(this.dom.endDate, this.formatDate(project.end_date));
      this.handleProjectDescription(project);

      this.renderFeaturedImage(project.pictures, title);
      this.handleTheProject(project);
      this.handleImpact(project);
      this.renderGallery(project.pictures, title);

      this.renderPeopleList(this.dom.projectLead, this.projectLeadPeople(project));
      this.renderPeopleList(this.dom.partners, this.partnerPeople(project.partners));

      this.renderProjectUrl(this.dom.projectUrl, project.project_url);
      this.renderTags(this.dom.productTypes, this.productTypeNames(project.hosting_locations));
      this.renderTags(this.dom.keywords, this.normalizeTags(project.keywords));

      this.renderPrevNext(project.previous_project, project.next_project);
    }
  }

  class ProjectApiClient {
    constructor(apiBase, projectCode, apiToken) {
      console.log(
        "project_detail.js ProjectApiClient.constructor",
        { apiBase, projectCode, apiToken },
      );
      this.apiBase = apiBase;
      this.projectCode = projectCode;
      this.apiToken = apiToken || "";
      this.projectUrl = `${this.apiBase}/${encodeURIComponent(this.projectCode)}/`;
      this.productsUrl = `${this.apiBase}/${encodeURIComponent(this.projectCode)}/products/`;
    }

    hasProjectCode() {
      console.log("project_detail.js ProjectApiClient.hasProjectCode");
      return Boolean(this.projectCode);
    }

    jsonHeaders() {
      console.log("project_detail.js ProjectApiClient.jsonHeaders");
      const headers = { Accept: "application/json" };
      if (this.apiToken) {
        headers.Authorization = `Bearer ${this.apiToken}`;
      }
      return headers;
    }

    async fetchJson(url) {
      console.log("project_detail.js ProjectApiClient.fetchJson", { url });
      const response = await fetch(url, { headers: this.jsonHeaders() });
      if (!response.ok) {
        throw new Error(`Request failed (${response.status}) for ${url}`);
      }
      return response.json();
    }

    fetchProject() {
      console.log("project_detail.js ProjectApiClient.fetchProject");
      return this.fetchJson(this.projectUrl);
    }

    fetchProducts() {
      console.log("project_detail.js ProjectApiClient.fetchProducts");
      return this.fetchJson(this.productsUrl);
    }
  }

  class ProjectDetailController {
    constructor({ dom, api, contentRenderer, productsRenderer }) {
      console.log(
        "project_detail.js ProjectDetailController.constructor",
        { dom, api, contentRenderer, productsRenderer },
      );
      this.dom = dom;
      this.api = api;
      this.contentRenderer = contentRenderer;
      this.productsRenderer = productsRenderer;
    }

    showError(message) {
      console.log("project_detail.js ProjectDetailController.showError", { message });
      if (!this.dom.errorBox) return;
      this.dom.errorBox.hidden = false;
      this.dom.errorBox.textContent = message;
    }

    async init() {
      console.log("project_detail.js ProjectDetailController.init");
      if (!this.dom.root) return;

      if (!this.api.hasProjectCode()) {
        this.showError("Missing project code in page context.");
        return;
      }

      try {
        const project = await this.api.fetchProject();
        this.contentRenderer.renderProject(project);

        const products = await this.api.fetchProducts();
        this.productsRenderer.renderProducts(products);
      } catch (err) {
        this.showError(err?.message || "Failed to load project.");
      }
    }
  }

  const dom = new ProjectDomRefs();
  const api = new ProjectApiClient(dom.apiBase, dom.projectCode, dom.apiToken);
  const contentRenderer = new ProjectContentRenderer(dom);
  const ProductCardTemplateModelClass = window.ProductCardTemplateModel;
  const ProjectProductsRendererClass = window.ProjectProductsRenderer;
  if (
    typeof ProductCardTemplateModelClass !== "function"
    || typeof ProjectProductsRendererClass !== "function"
  ) {
    console.error("Project product classes are not loaded.");
    return;
  }
  const productCardTemplateModel = new ProductCardTemplateModelClass();
  const productsRenderer = new ProjectProductsRendererClass(dom, productCardTemplateModel);
  const controller = new ProjectDetailController({ dom, api, contentRenderer, productsRenderer });
  controller.init();
})();
