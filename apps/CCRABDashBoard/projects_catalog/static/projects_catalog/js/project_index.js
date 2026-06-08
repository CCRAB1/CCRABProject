(function () {
    const root = document.getElementById("projects-page");
    const apiBase = (root?.dataset?.apiBase || "").replace(/\/$/, "");
    const apiToken = root?.dataset?.apiToken || "";

    const facetsUrl = `${apiBase}/facets/`;
    const listUrl = `${apiBase}/`;

    const errorBox = document.getElementById("error-box");
    const summaryEl = document.getElementById("results-summary");
    const gridEl = document.getElementById("projects-grid");
    const emptyEl = document.getElementById("empty-state");

    const form = document.getElementById("filters-form");
    const resetBtn = document.getElementById("reset-btn");

    const fQ = document.getElementById("f-q");
    const fType = document.getElementById("f-project-type");
    const fNeighborhood = document.getElementById("f-neighborhood");
    const fRegion = document.getElementById("f-region");
    //const fFocus = document.getElementById("f-focus-area");
    //const fNum = document.getElementById("f-num-reserves");

    const pagination = document.getElementById("pagination");
    const pagePrev = document.getElementById("page-prev");
    const pageNext = document.getElementById("page-next");
    const pageList = document.getElementById("pagination-list");

    function showError(msg) {
        errorBox.hidden = false;
        errorBox.textContent = msg;
    }

    function clearError() {
        errorBox.hidden = true;
        errorBox.textContent = "";
    }

    function clearChildren(el) {
        while (el.firstChild) el.removeChild(el.firstChild);
    }

    function addOption(select, value, label) {
        const opt = document.createElement("option");
        opt.value = value;
        opt.textContent = label;
        select.appendChild(opt);
    }

    function getParamsFromUI(page = 1) {
        const params = new URLSearchParams();

        if (fQ.value.trim()) params.set("q", fQ.value.trim());
        if (fType.value) params.set("project_type", fType.value);
        if (fNeighborhood.value) params.set("neighborhood", fNeighborhood.value);
        if (fRegion.value) params.set("region", fRegion.value);
        //if (fFocus.value) params.set("focus_area", fFocus.value);
        //if (fNum.value) params.set("num_reserves", fNum.value);

        params.set("page", String(page));
        return params;
    }

    function applyParamsToUI(params) {
        fQ.value = params.get("q") || "";
        fType.value = params.get("project_type") || "";
        fNeighborhood.value = params.get("neighborhood") || "";
        fRegion.value = params.get("region") || "";
        //fFocus.value = params.get("focus_area") || "";
        //fNum.value = params.get("num_reserves") || "";
    }

    function updateUrl(params) {
        const url = new URL(window.location.href);
        url.search = params.toString();
        window.history.pushState({}, "", url);
    }

    function jsonHeaders() {
        const headers = {"Accept": "application/json"};
        if (apiToken) {
            headers.Authorization = `Bearer ${apiToken}`;
        }
        return headers;
    }

    async function fetchJson(url) {
        const res = await fetch(url, {headers: jsonHeaders()});
        if (!res.ok) throw new Error(`Request failed (${res.status})`);
        return await res.json();
    }

    function displayProjectTitle(project) {
        return project?.project_full_title || project?.project_name || "Untitled project";
    }

    function formatDate(value) {
        if (!value) return "";
        const dateValue = new Date(value);
        if (Number.isNaN(dateValue.getTime())) return String(value);
        return new Intl.DateTimeFormat("en-US", {
            month: "short",
            year: "numeric",
        }).format(dateValue);
    }

    function formatDateRange(project) {
        const start = formatDate(project?.start_date);
        const end = formatDate(project?.end_date);
        if (start && end) return `${start} - ${end}`;
        if (start) return `${start} - Present`;
        if (end) return `Through ${end}`;
        return "—";
    }

    function firstPicture(pictures) {
        if (!Array.isArray(pictures)) return null;
        for (const picture of pictures) {
            if (picture?.picture_path) {
                return picture;
            }
        }
        return null;
    }

    function renderCards(items) {
        clearChildren(gridEl);

        if (!Array.isArray(items) || items.length === 0) {
            emptyEl.hidden = false;
            return;
        }
        emptyEl.hidden = true;

        for (const p of items) {
            const projectTitle = displayProjectTitle(p);
            const picture = firstPicture(p.pictures);
            const col = document.createElement("div");
            col.className = "column is-12-mobile is-6-tablet is-4-desktop";

            const card = document.createElement("div");
            card.className = "card";

            if (picture?.picture_path) {
                const cardImage = document.createElement("div");
                cardImage.className = "card-image";
                const figure = document.createElement("figure");
                figure.className = "image is-4by3";
                const img = document.createElement("img");
                img.src = picture.picture_path;
                img.alt = picture.name || projectTitle || "Project image";
                figure.appendChild(img);
                cardImage.appendChild(figure);
                card.appendChild(cardImage);
            }

            const content = document.createElement("div");
            content.className = "card-content";

            const duration = document.createElement("p");
            duration.className = "is-size-7 has-text-grey mb-2";
            duration.textContent = formatDateRange(p);

            const title = document.createElement("p");
            title.className = "title is-6 mb-0";

            const a = document.createElement("a");
            a.href = p.project_detail_url || "#";
            a.textContent = projectTitle;

            title.appendChild(a);

            content.appendChild(duration);
            content.appendChild(title);

            card.appendChild(content);
            col.appendChild(card);
            gridEl.appendChild(col);
        }
    }

    function renderSummary(meta) {
        const start = meta?.displaying?.start ?? 0;
        const end = meta?.displaying?.end ?? 0;
        const count = meta?.count ?? 0;

        summaryEl.textContent = `Displaying ${start} - ${end} of ${count}`;
    }

    function pageNumbersToShow(current, total) {
        // Show: 1, …, (current-2..current+2), …, total
        const out = new Set([1, total, current, current - 1, current - 2, current + 1, current + 2]);
        return Array.from(out)
            .filter(n => n >= 1 && n <= total)
            .sort((a, b) => a - b);
    }

    function renderPagination(meta, currentParams) {
        const page = meta?.page ?? 1;
        const total = meta?.total_pages ?? 1;

        if (total <= 1) {
            pagination.hidden = true;
            return;
        }
        pagination.hidden = false;

        pagePrev.classList.toggle("is-disabled", page <= 1);
        pageNext.classList.toggle("is-disabled", page >= total);

        pagePrev.onclick = (e) => {
            e.preventDefault();
            if (page <= 1) return;
            loadProjects(page - 1);
        };

        pageNext.onclick = (e) => {
            e.preventDefault();
            if (page >= total) return;
            loadProjects(page + 1);
        };

        clearChildren(pageList);

        const nums = pageNumbersToShow(page, total);
        let last = 0;

        for (const n of nums) {
            if (last && n > last + 1) {
                const liDots = document.createElement("li");
                const spanDots = document.createElement("span");
                spanDots.className = "pagination-ellipsis";
                spanDots.innerHTML = "&hellip;";
                liDots.appendChild(spanDots);
                pageList.appendChild(liDots);
            }

            const li = document.createElement("li");
            const a = document.createElement("a");
            a.className = "pagination-link";
            if (n === page) a.classList.add("is-current");
            a.textContent = String(n);
            a.href = "#";
            a.onclick = (e) => {
                e.preventDefault();
                loadProjects(n);
            };
            li.appendChild(a);
            pageList.appendChild(li);

            last = n;
        }
    }

    async function loadFacets() {
        const facets = await fetchJson(facetsUrl);

        // Reset selects (keep “Any”)
        fType.length = 1;
        fNeighborhood.length = 1;
        fRegion.length = 1;
        //fFocus.length = 1;

        for (const t of (facets.project_types || [])) addOption(fType, t, t);
        for (const n of (facets.neighborhoods || facets.neighborhood || [])) addOption(fNeighborhood, n, n);
        for (const r of (facets.regions || [])) addOption(fRegion, r, r);
        //for (const f of (facets.focus_areas || [])) addOption(fFocus, f, f);
    }

    async function loadProjects(page = 1) {
        clearError();

        const params = getParamsFromUI(page);
        updateUrl(params);

        const url = `${listUrl}?${params.toString()}`;
        const data = await fetchJson(url);

        renderSummary(data);
        renderCards(data.results);
        renderPagination(data, params);
    }

    async function init() {
        try {
            const params = new URLSearchParams(window.location.search);

            // Load dropdown options first
            await loadFacets();

            // Then apply query params into the now-populated selects
            applyParamsToUI(params);

            const initialPage = Number(params.get("page") || 1);
            await loadProjects(Number.isFinite(initialPage) ? initialPage : 1);

            form.addEventListener("submit", (e) => {
                e.preventDefault();
                loadProjects(1);
            });

            resetBtn.addEventListener("click", () => {
                fQ.value = "";
                fType.value = "";
                fNeighborhood.value = "";
                fRegion.value = "";
                //fFocus.value = "";
                //fNum.value = "";
                loadProjects(1);
            });

            window.addEventListener("popstate", async () => {
                const p = new URLSearchParams(window.location.search);
                applyParamsToUI(p);
                const pg = Number(p.get("page") || 1);
                await loadProjects(Number.isFinite(pg) ? pg : 1);
            });

        } catch (err) {
            showError(err?.message || "Failed to load projects.");
        }
    }

    init();
})();
