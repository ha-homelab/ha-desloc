/* Progressive enhancement only: the wiki remains readable without JavaScript. */
(() => {
  "use strict";
  const root = document.documentElement;
  const storageKey = "desloc-wiki-theme";
  const modes = ["system", "light", "dark"];
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  const themeButtons = document.querySelectorAll(".theme-toggle");
  const messages = Object.fromEntries([...document.querySelectorAll("#wiki-messages [data-message]")]
    .map((node) => [node.dataset.message, node.textContent]));
  const validMode = (mode) => modes.includes(mode) ? mode : "system";
  const currentMode = () => validMode(root.dataset.themeMode);

  function applyTheme(mode, persist) {
    mode = validMode(mode);
    const resolved = mode === "system" ? (media.matches ? "dark" : "light") : mode;
    root.dataset.themeMode = mode;
    root.dataset.theme = resolved;
    root.style.colorScheme = resolved;
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.content = resolved === "dark" ? "#091d24" : "#f7f8f3";
    for (const button of themeButtons) {
      const label = messages[`theme_${mode}`];
      button.setAttribute("aria-label", label);
      button.title = label;
      const text = button.querySelector(".theme-label");
      if (text) text.textContent = messages[`mode_${mode}`];
    }
    if (persist) {
      try {
        if (mode === "system") localStorage.removeItem(storageKey);
        else localStorage.setItem(storageKey, mode);
      } catch (_) { /* The current page still works when storage is unavailable. */ }
    }
  }

  let initial = currentMode();
  if (!root.dataset.themeMode) {
    try { initial = validMode(localStorage.getItem(storageKey)); } catch (_) { /* Use system. */ }
  }
  applyTheme(initial, false);
  for (const button of themeButtons) {
    button.addEventListener("click", () => {
      applyTheme(modes[(modes.indexOf(currentMode()) + 1) % modes.length], true);
    });
    button.hidden = false;
  }
  media.addEventListener("change", () => {
    if (currentMode() === "system") applyTheme("system", false);
  });
  window.addEventListener("storage", (event) => {
    if (event.key === storageKey || event.key === null) applyTheme(validMode(event.newValue), false);
  });

  const mobileMenu = document.querySelector("details.mobile-nav");
  if (mobileMenu) {
    mobileMenu.addEventListener("click", (event) => {
      if (event.target.closest('a[href^="#"]')) mobileMenu.open = false;
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && mobileMenu.open) {
        mobileMenu.open = false;
        mobileMenu.querySelector("summary").focus();
      }
    });
  }

  const languageMenu = document.querySelector("details.language-menu");
  if (languageMenu) {
    const links = [...languageMenu.querySelectorAll("a[hreflang]")];
    // Preserve the section when changing language; plain links still work without JS.
    const syncLanguageLinks = () => {
      for (const link of links) link.hash = window.location.hash;
    };
    syncLanguageLinks();
    window.addEventListener("hashchange", syncLanguageLinks);
    languageMenu.addEventListener("toggle", () => {
      if (languageMenu.open && mobileMenu) mobileMenu.open = false;
    });
    if (mobileMenu) mobileMenu.addEventListener("toggle", () => {
      if (mobileMenu.open) languageMenu.open = false;
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && languageMenu.open) {
        languageMenu.open = false;
        languageMenu.querySelector("summary").focus();
      }
    });
    document.addEventListener("click", (event) => {
      if (!languageMenu.contains(event.target)) languageMenu.open = false;
    });
  }

  // Pick the last section above the reading line. This also handles very tall guides.
  const header = document.querySelector(".site-header");
  const navLinks = [...document.querySelectorAll('.toc nav a[href^="#"], .primary-nav a[href^="#"], .mobile-nav a[href^="#"]')];
  const sectionIds = new Set(navLinks.map((link) => link.hash.slice(1)));
  const sections = [...document.querySelectorAll("main section[id]")].filter((section) => sectionIds.has(section.id));
  let scheduled = false;
  function updateActiveSection() {
    scheduled = false;
    if (!sections.length) return;
    const readingLine = (header ? header.getBoundingClientRect().bottom : 0) + 34;
    let active = null;
    for (const section of sections) {
      if (section.getBoundingClientRect().top <= readingLine) active = section.id;
    }
    if (window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 3) {
      active = sections[sections.length - 1].id;
    }
    for (const link of navLinks) {
      if (link.hash === `#${active}`) link.setAttribute("aria-current", "location");
      else link.removeAttribute("aria-current");
    }
  }
  function scheduleActiveSection() {
    if (!scheduled) {
      scheduled = true;
      requestAnimationFrame(updateActiveSection);
    }
  }
  window.addEventListener("scroll", scheduleActiveSection, { passive: true });
  window.addEventListener("resize", scheduleActiveSection, { passive: true });
  window.addEventListener("hashchange", scheduleActiveSection);
  window.addEventListener("load", scheduleActiveSection);
  updateActiveSection();

  // Search is local and never removes guide content, so browser Find still works.
  const searchInput = document.getElementById("guide-search");
  const searchResults = document.getElementById("search-results");
  const searchStatus = document.getElementById("search-status");
  if (searchInput && searchResults && searchStatus) {
    const form = searchInput.closest("form");
    function headingText(section) {
      const heading = section.querySelector("h2, h1");
      if (!heading) return section.id.replaceAll("-", " ");
      const clone = heading.cloneNode(true);
      for (const br of clone.querySelectorAll("br")) br.replaceWith(" ");
      return clone.textContent.replace(/\s+/g, " ").trim();
    }
    const entries = [...document.querySelectorAll("section[data-search][id]")].map((section) => ({
      id: section.id,
      title: headingText(section),
      text: `${section.dataset.search} ${section.textContent}`.toLocaleLowerCase(root.lang),
    }));
    function search() {
      const query = searchInput.value.trim().toLocaleLowerCase(root.lang);
      searchResults.replaceChildren();
      if (!query) { searchStatus.textContent = ""; return; }
      const terms = query.split(/\s+/).filter(Boolean);
      const matches = entries.filter((entry) => terms.every((term) => entry.text.includes(term)));
      for (const entry of matches) {
        const li = document.createElement("li");
        const link = document.createElement("a");
        link.href = `#${entry.id}`;
        link.textContent = entry.title;
        li.append(link);
        searchResults.append(li);
      }
      searchStatus.textContent = matches.length
        ? messages.search_matches.replace("{count}", new Intl.NumberFormat(root.lang).format(matches.length))
        : messages.search_empty;
    }
    searchInput.addEventListener("input", search);
    if (form) {
      form.addEventListener("submit", (event) => { event.preventDefault(); search(); });
      form.hidden = false;
    }
  }

  for (const button of document.querySelectorAll("button.copy-button[data-copy]")) {
    const original = button.textContent;
    button.addEventListener("click", async () => {
      const target = document.getElementById(button.dataset.copy);
      if (!target) return;
      try {
        if (!navigator.clipboard || !window.isSecureContext) throw new Error("Clipboard unavailable");
        await navigator.clipboard.writeText(target.textContent.trim());
        button.textContent = messages.copied;
      } catch (_) {
        const selection = window.getSelection();
        if (selection) {
          const range = document.createRange();
          range.selectNodeContents(target);
          selection.removeAllRanges();
          selection.addRange(range);
        }
        button.textContent = messages.copy_manual;
      }
      window.setTimeout(() => { button.textContent = original; }, 3000);
    });
    button.hidden = false;
  }
})();
