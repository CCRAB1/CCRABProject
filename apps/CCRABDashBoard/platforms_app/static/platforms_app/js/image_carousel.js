(() => {
  function clamp(n, min, max) {
    return Math.max(min, Math.min(max, n));
  }

  function parseBool(value, defaultValue = false) {
    if (value === undefined) return defaultValue;
    return value === "true";
  }

  function initCarousel(carousel) {
    const viewport = carousel.querySelector("[data-carousel-viewport]");
    if (!viewport) return;

    const prevBtn = carousel.querySelector("[data-carousel-prev]");
    const nextBtn = carousel.querySelector("[data-carousel-next]");
    const slides = Array.from(carousel.querySelectorAll("[data-carousel-slide]"));
    const dots = Array.from(carousel.querySelectorAll("[data-carousel-dot]"));

    if (!slides.length) return;

    let activeIndex = 0;
    let rafPending = false;

    // Autoplay options via data- attributes
    const autoplayEnabled = parseBool(carousel.dataset.autoplay, false);
    const intervalMs = Number.parseInt(carousel.dataset.interval || "5000", 10) || 5000;
    const loop = parseBool(carousel.dataset.loop, true);
    const pauseOnHover = parseBool(carousel.dataset.pauseOnHover, true);

    const prefersReducedMotion =
      window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    let timer = null;
    let restartTimeout = null;
    let hoverOrFocusPaused = false;

    function canScroll() {
      return viewport.scrollWidth > viewport.clientWidth + 1;
    }

    function getStartIndex() {
      const vpRect = viewport.getBoundingClientRect();
      let best = 0;
      let bestDelta = Infinity;

      for (let i = 0; i < slides.length; i++) {
        const r = slides[i].getBoundingClientRect();
        const delta = Math.abs(r.left - vpRect.left);
        if (delta < bestDelta) {
          bestDelta = delta;
          best = i;
        }
      }
      return best;
    }

    function updateUI() {
      const maxScroll = viewport.scrollWidth - viewport.clientWidth;
      const atStart = viewport.scrollLeft <= 1;
      const atEnd = viewport.scrollLeft >= maxScroll - 1;

      if (prevBtn) prevBtn.disabled = atStart;
      if (nextBtn) nextBtn.disabled = atEnd;

      if (dots.length) {
        dots.forEach((dot, i) => {
          const isActive = i === activeIndex;
          dot.classList.toggle("is-primary", isActive);
          dot.classList.toggle("is-light", !isActive);
          dot.setAttribute("aria-current", isActive ? "true" : "false");
        });
      }
    }

    function setActiveIndexFromScroll() {
      activeIndex = getStartIndex();
      updateUI();
    }

    function scheduleScrollUpdate() {
      if (rafPending) return;
      rafPending = true;
      window.requestAnimationFrame(() => {
        rafPending = false;
        setActiveIndexFromScroll();
      });
    }

    function scrollToIndex(index, behavior = "smooth") {
      const i = clamp(index, 0, slides.length - 1);
      slides[i].scrollIntoView({ behavior, inline: "start", block: "nearest" });
    }

    // --- Autoplay control ---
    function stopAutoplay() {
      if (timer) {
        window.clearInterval(timer);
        timer = null;
      }
      if (restartTimeout) {
        window.clearTimeout(restartTimeout);
        restartTimeout = null;
      }
    }

    function startAutoplay() {
      if (!autoplayEnabled) return;
      if (prefersReducedMotion) return;
      if (hoverOrFocusPaused) return;
      if (!canScroll()) return;
      if (timer) return;

      timer = window.setInterval(() => {
        if (!canScroll()) return;

        const maxScroll = viewport.scrollWidth - viewport.clientWidth;
        const atEnd = viewport.scrollLeft >= maxScroll - 1;

        if (atEnd) {
          if (loop) {
            viewport.scrollTo({ left: 0, behavior: "smooth" });
          } else {
            stopAutoplay();
          }
        } else {
          scrollToIndex(activeIndex + 1, "smooth");
        }
      }, intervalMs);
    }

    function restartAutoplaySoon(delay = intervalMs) {
      if (!autoplayEnabled || prefersReducedMotion) return;

      stopAutoplay();
      restartTimeout = window.setTimeout(() => {
        restartTimeout = null;
        if (!hoverOrFocusPaused) startAutoplay();
      }, delay);
    }

    // Buttons (reset autoplay timer on manual nav)
    if (prevBtn) {
      prevBtn.addEventListener("click", () => {
        scrollToIndex(activeIndex - 1);
        restartAutoplaySoon();
      });
    }
    if (nextBtn) {
      nextBtn.addEventListener("click", () => {
        scrollToIndex(activeIndex + 1);
        restartAutoplaySoon();
      });
    }

    // Dots (reset autoplay timer on manual nav)
    dots.forEach((dot) => {
      dot.addEventListener("click", () => {
        const idx = Number.parseInt(dot.getAttribute("data-carousel-dot-index"), 10);
        if (!Number.isNaN(idx)) {
          scrollToIndex(idx);
          restartAutoplaySoon();
        }
      });
    });

    // Keyboard support
    viewport.addEventListener("keydown", (e) => {
      if (e.key === "ArrowLeft") {
        e.preventDefault();
        scrollToIndex(activeIndex - 1);
        restartAutoplaySoon();
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        scrollToIndex(activeIndex + 1);
        restartAutoplaySoon();
      }
    });

    // Pause/resume on hover/focus (optional)
    if (pauseOnHover) {
      carousel.addEventListener("mouseenter", () => {
        hoverOrFocusPaused = true;
        stopAutoplay();
      });
      carousel.addEventListener("mouseleave", () => {
        hoverOrFocusPaused = false;
        startAutoplay();
      });
      carousel.addEventListener("focusin", () => {
        hoverOrFocusPaused = true;
        stopAutoplay();
      });
      carousel.addEventListener("focusout", () => {
        hoverOrFocusPaused = false;
        startAutoplay();
      });
    }

    // If user interacts via touch/drag/wheel, pause and resume later
    viewport.addEventListener("pointerdown", () => restartAutoplaySoon(intervalMs), { passive: true });
    viewport.addEventListener("touchstart", () => restartAutoplaySoon(intervalMs), { passive: true });
    viewport.addEventListener("wheel", () => restartAutoplaySoon(intervalMs), { passive: true });

    // Update active slide on scroll/resize
    viewport.addEventListener("scroll", scheduleScrollUpdate, { passive: true });
    window.addEventListener("resize", () => {
      scheduleScrollUpdate();
      // On resize, restart autoplay (only if still scrollable)
      restartAutoplaySoon(250);
    });

    // Stop when tab is hidden; resume when visible
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) stopAutoplay();
      else startAutoplay();
    });

    // Initial state
    setActiveIndexFromScroll();
    startAutoplay();
  }

  function initAll(root = document) {
    const carousels = root.querySelectorAll("[data-bulma-carousel]");
    carousels.forEach(initCarousel);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => initAll());
  } else {
    initAll();
  }

  // For partial page updates (HTMX/Turbo/etc.)
  window.BulmaCarousel = { init: initAll };
})();
