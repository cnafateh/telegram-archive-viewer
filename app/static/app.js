(() => {
  "use strict";

  const state = {
    items: [],
    oldestId: null,
    hasMore: false,
    senders: [],
    q: "",
    sender: "",
    media: "",
    date: "",
    selfSender: null,
    stats: null
  };

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

  const messagesEl = $("#messages");
  const loadingEl = $("#loading");
  const emptyEl = $("#empty");
  const loadMoreEl = $("#load-more");
  const sidebar = $("#sidebar");
  const sidebarToggle = $("#sidebar-toggle");
  const sidebarClose = $("#sidebar-close");
  const sidebarBackdrop = $("#sidebar-backdrop");

  function escapeHtml(value = "") {
    return String(value).replace(/[&<>"']/g, (char) => {
      const map = {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;"
      };
      return map[char];
    });
  }

  function formatNumber(value) {
    return Number(value || 0).toLocaleString("en-US");
  }

  function formatDate(iso) {
    if (!iso) return "";
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return iso;

    return new Intl.DateTimeFormat("en", {
      month: "long",
      day: "numeric",
      year: "numeric"
    }).format(date);
  }

  function formatTime(iso) {
    if (!iso) return "";
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return "";

    return new Intl.DateTimeFormat("en", {
      hour: "numeric",
      minute: "2-digit"
    }).format(date);
  }

  function capitalize(value) {
    return value ? value.charAt(0).toUpperCase() + value.slice(1) : "";
  }

  function icon(name) {
    const icons = {
      download: '<path d="M12 3v12m0 0-4-4m4 4 4-4M5 20h14"/>',
      external: '<path d="M14 5h5v5M19 5l-8 8M18 13v6H5V6h6"/>'
    };
    return `<svg viewBox="0 0 24 24">${icons[name] || ""}</svg>`;
  }

  function mediaHtml(message) {
    if (!message.media_url) {
      if (!message.media_title) return "";

      return `
        <div class="media">
          <div class="file-card">
            <div class="file-icon">${icon("download")}</div>
            <div class="file-info">
              <strong>${escapeHtml(message.media_title)}</strong>
              <small>${escapeHtml(message.media_status || "Not included in this export")}</small>
            </div>
            <span class="file-open"></span>
          </div>
        </div>
      `;
    }

    const url = encodeURI(message.media_url);
    const title = escapeHtml(message.media_title || "Media");

    if (message.media_type === "photo" || message.media_type === "sticker") {
      return `
        <div class="media ${message.media_type === "sticker" ? "sticker" : ""}">
          <img class="zoomable" src="${url}" loading="lazy" alt="${title}" data-caption="${title}">
        </div>
      `;
    }

    if (message.media_type === "video") {
      return `
        <div class="media">
          <video controls preload="metadata" src="${url}"></video>
        </div>
      `;
    }

    if (message.media_type === "voice" || message.media_type === "audio") {
      return `
        <div class="media">
          <audio controls preload="metadata" src="${url}"></audio>
        </div>
      `;
    }

    return `
      <div class="media">
        <a class="file-card" href="${url}" target="_blank" rel="noopener">
          <div class="file-icon">${icon("download")}</div>
          <div class="file-info">
            <strong>${title}</strong>
            <small>${escapeHtml(message.media_status || "Open file")}</small>
          </div>
          <span class="file-open">${icon("external")}</span>
        </a>
      </div>
    `;
  }

  function reactionsHtml(list) {
    if (!Array.isArray(list) || list.length === 0) return "";

    return `
      <div class="reactions">
        ${list.map((reaction) => `
          <span class="reaction" title="${escapeHtml((reaction.users || []).join(", "))}">
            ${escapeHtml(reaction.emoji || "")}${reaction.count ? ` ${escapeHtml(reaction.count)}` : ""}
          </span>
        `).join("")}
      </div>
    `;
  }

  function replyHtml(message) {
    if (!message.reply_to) return "";

    return `
      <button class="reply" data-reply="${message.reply_to}" type="button">
        Reply to message #${message.reply_to}
      </button>
    `;
  }

  function messageHtml(message, previousDate) {
    const dateKey = message.sent_at ? message.sent_at.slice(0, 10) : null;
    const daySeparator = dateKey && dateKey !== previousDate
      ? `<div class="day-separator" data-date="${dateKey}">${formatDate(message.sent_at)}</div>`
      : "";

    const outgoing = state.selfSender && message.sender === state.selfSender;

    return {
      dateKey: dateKey || previousDate,
      html: `
        ${daySeparator}
        <div class="message-row ${outgoing ? "outgoing" : "incoming"}" id="msg-${message.telegram_id}">
          <article class="bubble">
            ${message.sender ? `<div class="sender">${escapeHtml(message.sender)}</div>` : ""}
            ${message.forwarded_from ? `<div class="forwarded">Forwarded from ${escapeHtml(message.forwarded_from)}</div>` : ""}
            ${replyHtml(message)}
            ${mediaHtml(message)}
            ${message.text ? `<div class="text">${escapeHtml(message.text)}</div>` : ""}
            ${reactionsHtml(message.reactions)}
            <div class="meta">
              <span>${formatTime(message.sent_at)}</span>
              <span class="message-id">#${message.telegram_id}</span>
            </div>
          </article>
        </div>
      `
    };
  }

  function bindMessageEvents() {
    $$(".reply", messagesEl).forEach((button) => {
      button.addEventListener("click", () => {
        jumpToMessage(Number(button.dataset.reply));
      });
    });

    $$(".zoomable", messagesEl).forEach((image) => {
      image.addEventListener("click", () => {
        openLightbox(image.src, image.dataset.caption || "Media preview");
      });
    });
  }

  function render(reset = true) {
    let previousDate = null;

    if (reset) {
      messagesEl.innerHTML = "";
    } else {
      const firstSeparator = $(".day-separator", messagesEl);
      previousDate = firstSeparator?.dataset.date || null;
    }

    let html = "";

    for (const message of state.items) {
      const rendered = messageHtml(message, previousDate);
      previousDate = rendered.dateKey;
      html += rendered.html;
    }

    if (reset) {
      messagesEl.innerHTML = html;
    } else {
      messagesEl.insertAdjacentHTML("afterbegin", html);
    }

    bindMessageEvents();
  }

  function buildQuery({ appendOlder = false } = {}) {
    const params = new URLSearchParams({ limit: "80" });

    if (state.q) params.set("q", state.q);
    if (state.sender) params.set("sender", state.sender);
    if (state.media) params.set("media", state.media);
    if (state.date) params.set("date", state.date);
    if (appendOlder && state.oldestId) params.set("before_id", state.oldestId);

    return params;
  }

  async function fetchMessages({ appendOlder = false, preserveScroll = false } = {}) {
    loadingEl.classList.remove("hidden");
    emptyEl.classList.add("hidden");

    const previousScrollHeight = messagesEl.scrollHeight;

    try {
      const response = await fetch(`/api/messages?${buildQuery({ appendOlder })}`);

      if (response.status === 401) {
        window.location.href = "/login";
        return;
      }

      if (!response.ok) {
        throw new Error(`Messages request failed with ${response.status}`);
      }

      const data = await response.json();
      const rows = Array.isArray(data.items) ? data.items.slice().reverse() : [];

      if (appendOlder) {
        state.items = rows;
        render(false);

        if (preserveScroll) {
          requestAnimationFrame(() => {
            messagesEl.scrollTop = messagesEl.scrollHeight - previousScrollHeight;
          });
        }
      } else {
        state.items = rows;
        render(true);

        if (rows.length) {
          requestAnimationFrame(() => {
            messagesEl.scrollTop = messagesEl.scrollHeight;
          });
        }
      }

      if (rows.length) {
        state.oldestId = rows[0].id;
      } else if (!appendOlder) {
        state.oldestId = null;
      }

      state.hasMore = Boolean(data.has_more);
      loadMoreEl.classList.toggle("hidden", !state.hasMore);
      emptyEl.classList.toggle("hidden", appendOlder || rows.length > 0);
      updateResultLabel();
    } catch (error) {
      console.error(error);
      showToast("Could not load messages.");
      emptyEl.classList.remove("hidden");
    } finally {
      loadingEl.classList.add("hidden");
    }
  }

  function updateResultLabel() {
    const parts = [];

    if (state.q) parts.push(`Search: “${state.q}”`);
    if (state.sender) parts.push(state.sender);
    if (state.media) parts.push(capitalize(state.media));
    if (state.date) parts.push(state.date);

    $("#result-label").textContent = parts.length ? parts.join(" · ") : "All messages";
  }

  async function loadStats() {
    try {
      const response = await fetch("/api/stats");

      if (response.status === 401) {
        window.location.href = "/login";
        return;
      }

      if (!response.ok) {
        throw new Error(`Stats request failed with ${response.status}`);
      }

      const stats = await response.json();

      state.stats = stats;
      state.senders = Array.isArray(stats.senders) ? stats.senders : [];
      state.selfSender = state.senders[0]?.sender || null;

      $("#archive-range").textContent = stats.first && stats.last
        ? `${stats.first.slice(0, 10)} — ${stats.last.slice(0, 10)}`
        : "Telegram HTML archive";

      const senderFilter = $("#sender-filter");

      senderFilter.insertAdjacentHTML(
        "beforeend",
        state.senders.map((sender) => `
          <option value="${escapeHtml(sender.sender)}">
            ${escapeHtml(sender.sender)} · ${formatNumber(sender.count)}
          </option>
        `).join("")
      );

      const media = stats.media || {};
      const mediaCount = Object.values(media).reduce((sum, value) => sum + Number(value || 0), 0);

      $("#stats").innerHTML = `
        <div class="metric"><b>${formatNumber(stats.total)}</b><span>Messages</span></div>
        <div class="metric"><b>${formatNumber(mediaCount)}</b><span>Media items</span></div>
        <div class="metric"><b>${formatNumber(state.senders.length)}</b><span>Senders</span></div>
        <div class="metric"><b>${formatNumber(Object.keys(media).length)}</b><span>Media types</span></div>
      `;

      $("#count-all").textContent = formatNumber(stats.total);
      $("#count-photo").textContent = formatNumber(media.photo || 0);
      $("#count-video").textContent = formatNumber(media.video || 0);
      $("#count-file").textContent = formatNumber(media.file || 0);
    } catch (error) {
      console.error(error);
      $("#stats").innerHTML = `
        <div class="metric"><b>—</b><span>Messages</span></div>
        <div class="metric"><b>—</b><span>Media items</span></div>
        <div class="metric"><b>—</b><span>Senders</span></div>
        <div class="metric"><b>—</b><span>Media types</span></div>
      `;
      showToast("Could not load archive statistics.");
    }
  }

  async function jumpToMessage(telegramId) {
    const existing = document.getElementById(`msg-${telegramId}`);

    if (existing) {
      existing.scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }

    loadingEl.classList.remove("hidden");

    try {
      const response = await fetch(`/api/around/${telegramId}`);

      if (!response.ok) {
        throw new Error(`Around request failed with ${response.status}`);
      }

      const data = await response.json();
      state.items = Array.isArray(data.items) ? data.items : [];
      render(true);

      requestAnimationFrame(() => {
        const target = document.getElementById(`msg-${telegramId}`);
        if (target) target.scrollIntoView({ behavior: "auto", block: "center" });
      });
    } catch (error) {
      console.error(error);
      showToast("The original message is not available.");
    } finally {
      loadingEl.classList.add("hidden");
    }
  }

  function resetFilters() {
    state.q = "";
    state.sender = "";
    state.media = "";
    state.date = "";
    state.oldestId = null;

    $("#search").value = "";
    $("#sender-filter").value = "";
    $("#media-filter").value = "";
    $("#date-filter").value = "";

    $$(".quick-filter").forEach((button) => {
      button.classList.toggle("active", !button.dataset.media);
    });

    fetchMessages();
  }

  function selectMedia(media) {
    state.media = media;
    state.oldestId = null;

    $("#media-filter").value = media;

    $$(".quick-filter").forEach((button) => {
      button.classList.toggle("active", button.dataset.media === media);
    });

    fetchMessages();
  }

  function openSidebar() {
    sidebar.classList.add("open");
    sidebarBackdrop.classList.add("open");
    document.body.classList.add("sidebar-open");
  }

  function closeSidebar() {
    sidebar.classList.remove("open");
    sidebarBackdrop.classList.remove("open");
    document.body.classList.remove("sidebar-open");
  }

  function openLightbox(src, caption) {
    $("#lightbox-image").src = src;
    $("#lightbox-caption").textContent = caption || "Media preview";
    $("#lightbox").classList.remove("hidden");
  }

  function closeLightbox() {
    $("#lightbox").classList.add("hidden");
    $("#lightbox-image").src = "";
  }

  let toastTimer = null;

  function showToast(message) {
    const toast = $("#toast");
    toast.textContent = message;
    toast.classList.remove("hidden");

    if (toastTimer) clearTimeout(toastTimer);

    toastTimer = setTimeout(() => {
      toast.classList.add("hidden");
    }, 2600);
  }

  function applySavedTheme() {
    const saved = localStorage.getItem("archive-theme");

    if (saved === "light" || saved === "dark") {
      document.documentElement.dataset.theme = saved;
      $("#theme-label").textContent = capitalize(saved);
    } else {
      $("#theme-label").textContent = "System";
    }
  }

  function toggleTheme() {
    const current = document.documentElement.dataset.theme ||
      (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");

    const next = current === "dark" ? "light" : "dark";

    document.documentElement.dataset.theme = next;
    localStorage.setItem("archive-theme", next);
    $("#theme-label").textContent = capitalize(next);
  }

  function bindUiEvents() {
    let searchTimer = null;

    $("#search").addEventListener("input", (event) => {
      if (searchTimer) clearTimeout(searchTimer);

      searchTimer = setTimeout(() => {
        state.q = event.target.value.trim();
        state.oldestId = null;
        fetchMessages();
      }, 260);
    });

    $("#sender-filter").addEventListener("change", (event) => {
      state.sender = event.target.value;
      state.oldestId = null;
      fetchMessages();
    });

    $("#media-filter").addEventListener("change", (event) => {
      selectMedia(event.target.value);
    });

    $("#date-filter").addEventListener("change", (event) => {
      state.date = event.target.value;
      state.oldestId = null;
      fetchMessages();
    });

    $("#clear-date").addEventListener("click", () => {
      $("#date-filter").value = "";
      state.date = "";
      state.oldestId = null;
      fetchMessages();
    });

    $("#reset-filters").addEventListener("click", resetFilters);
    $("#empty-reset").addEventListener("click", resetFilters);

    $$(".quick-filter").forEach((button) => {
      button.addEventListener("click", () => {
        selectMedia(button.dataset.media || "");
      });
    });

    loadMoreEl.addEventListener("click", () => {
      fetchMessages({ appendOlder: true, preserveScroll: true });
    });

    $("#scroll-latest").addEventListener("click", () => {
      if (state.q || state.sender || state.media || state.date) {
        resetFilters();
      } else {
        messagesEl.scrollTo({
          top: messagesEl.scrollHeight,
          behavior: "smooth"
        });
      }
    });

    $("#theme-toggle").addEventListener("click", toggleTheme);

    sidebarToggle.addEventListener("click", openSidebar);
    sidebarClose.addEventListener("click", closeSidebar);
    sidebarBackdrop.addEventListener("click", closeSidebar);

    $("#lightbox-close").addEventListener("click", closeLightbox);

    $("#lightbox").addEventListener("click", (event) => {
      if (event.target.id === "lightbox") {
        closeLightbox();
      }
    });

    document.addEventListener("keydown", (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        $("#search").focus();
      }

      if (event.key === "Escape") {
        closeSidebar();

        if (!$("#lightbox").classList.contains("hidden")) {
          closeLightbox();
        }
      }
    });

    window.addEventListener("resize", () => {
      if (window.innerWidth > 900) {
        closeSidebar();
      }
    });
  }

  async function init() {
    applySavedTheme();
    bindUiEvents();

    await loadStats();
    await fetchMessages();
  }

  init().catch((error) => {
    console.error("Archive UI initialization failed:", error);
    loadingEl.classList.add("hidden");
    emptyEl.classList.remove("hidden");
    showToast("The archive UI could not initialize.");
  });
})();
