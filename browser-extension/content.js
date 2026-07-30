"use strict";

(() => {
  const ROOT_ID = "bc-workspace-floating-root";

  if (document.getElementById(ROOT_ID)) {
    return;
  }

  const root = document.createElement("div");
  root.id = ROOT_ID;

  const shadow = root.attachShadow({ mode: "open" });

  const wrapper = document.createElement("div");
  wrapper.className = "bcw-wrapper";

  const bubble = document.createElement("button");
  bubble.className = "bcw-bubble";
  bubble.type = "button";
  bubble.title = "פתח את BC Workspace";
  bubble.setAttribute("aria-label", "פתח את BC Workspace");

  bubble.innerHTML = `
    <img
      src="${chrome.runtime.getURL("workspace-icon.svg")}"
      alt=""
      aria-hidden="true"
    />
    <span class="bcw-online"></span>
  `;

  const panel = document.createElement("section");
  panel.className = "bcw-panel";
  panel.hidden = true;
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-label", "BC Workspace");

  const header = document.createElement("header");
  header.className = "bcw-header";

  header.innerHTML = `
    <div class="bcw-brand">
      <img
        src="${chrome.runtime.getURL("workspace-icon.svg")}"
        alt=""
        aria-hidden="true"
      />
      <div>
        <strong>BC Workspace</strong>
        <span>העוזר החכם של Bitcoin Change</span>
      </div>
    </div>

    <div class="bcw-controls">
      <button
        type="button"
        class="bcw-minimize"
        title="מזער"
        aria-label="מזער"
      >−</button>

      <button
        type="button"
        class="bcw-close"
        title="סגור"
        aria-label="סגור"
      >×</button>
    </div>
  `;

  const context = document.createElement("div");
  context.className = "bcw-context";

  const contextSite = document.createElement("strong");
  const contextTitle = document.createElement("span");

  contextSite.textContent =
    window.location.hostname || "העמוד הנוכחי";

  contextTitle.textContent =
    document.title || "עמוד אינטרנט";

  context.append(contextSite, contextTitle);

  const iframe = document.createElement("iframe");
  iframe.className = "bcw-frame";
  iframe.src =
    "http://localhost:3000/?bc_workspace=floating";
  iframe.title = "BC Workspace";
  iframe.allow =
    "clipboard-read; clipboard-write; microphone";
  iframe.referrerPolicy = "no-referrer";

  panel.append(header, context, iframe);
  wrapper.append(panel, bubble);

  const style = document.createElement("style");

  style.textContent = `
    :host {
      all: initial;
    }

    *,
    *::before,
    *::after {
      box-sizing: border-box;
    }

    .bcw-wrapper {
      position: fixed;
      right: 22px;
      bottom: 22px;
      z-index: 2147483647;
      direction: rtl;
      font-family:
        Arial,
        "Noto Sans Hebrew",
        sans-serif;
      pointer-events: none;
    }

    .bcw-bubble {
      all: unset;
      position: relative;
      width: 70px;
      height: 70px;
      display: flex;
      align-items: center;
      justify-content: center;
      border: 2px solid #f4c21d;
      border-radius: 50%;
      background: #111111;
      box-shadow:
        0 14px 38px rgba(0, 0, 0, 0.34),
        0 0 0 5px rgba(244, 194, 29, 0.14);
      cursor: pointer;
      pointer-events: auto;
      transition:
        transform 160ms ease,
        box-shadow 160ms ease;
    }

    .bcw-bubble:hover {
      transform: translateY(-4px) scale(1.04);
      box-shadow:
        0 20px 50px rgba(0, 0, 0, 0.4),
        0 0 0 7px rgba(244, 194, 29, 0.19);
    }

    .bcw-bubble:active {
      transform: scale(0.96);
    }

    .bcw-bubble img {
      width: 52px;
      height: 52px;
      pointer-events: none;
    }

    .bcw-online {
      position: absolute;
      top: 3px;
      right: 3px;
      width: 14px;
      height: 14px;
      border: 2px solid #111111;
      border-radius: 50%;
      background: #22c55e;
    }

    .bcw-panel {
      width: clamp(560px, 42vw, 820px);
      height: calc(100vh - 44px);
      min-height: 600px;
      max-height: 960px;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      border: 1px solid rgba(244, 194, 29, 0.82);
      border-radius: 18px;
      background: #ffffff;
      box-shadow:
        0 28px 90px rgba(0, 0, 0, 0.38),
        0 0 0 5px rgba(244, 194, 29, 0.1);
      pointer-events: auto;
      animation: bcwOpen 180ms ease-out;
    }

    .bcw-panel[hidden] {
      display: none;
    }

    .bcw-header {
      min-height: 78px;
      padding: 12px 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      color: #ffffff;
      background:
        linear-gradient(
          135deg,
          #090909,
          #202020
        );
      border-bottom: 3px solid #f4c21d;
    }

    .bcw-brand {
      min-width: 0;
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .bcw-brand img {
      width: 52px;
      height: 52px;
      flex: 0 0 auto;
    }

    .bcw-brand div {
      min-width: 0;
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .bcw-brand strong {
      color: #ffffff;
      font-size: 24px;
      line-height: 1.1;
      white-space: nowrap;
    }

    .bcw-brand span {
      color: #d4d4d4;
      font-size: 14px;
      white-space: nowrap;
    }

    .bcw-controls {
      display: flex;
      align-items: center;
      gap: 4px;
      direction: ltr;
    }

    .bcw-controls button {
      all: unset;
      width: 42px;
      height: 42px;
      border-radius: 10px;
      color: #ffffff;
      font-family: Arial, sans-serif;
      font-size: 31px;
      line-height: 38px;
      text-align: center;
      cursor: pointer;
    }

    .bcw-controls button:hover {
      background: rgba(255, 255, 255, 0.13);
    }

    .bcw-context {
      min-height: 58px;
      padding: 10px 18px;
      display: flex;
      align-items: center;
      gap: 12px;
      overflow: hidden;
      color: #554500;
      background: #fff8dc;
      border-bottom: 1px solid #ecd97d;
    }

    .bcw-context strong {
      flex: 0 0 auto;
      font-size: 14px;
    }

    .bcw-context span {
      min-width: 0;
      overflow: hidden;
      color: #6b5d1b;
      font-size: 14px;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .bcw-frame {
      display: block;
      width: 100%;
      min-height: 0;
      flex: 1 1 auto;
      border: 0;
      background: #ffffff;
    }

    .bcw-panel:not([hidden]) + .bcw-bubble {
      display: none;
    }

    @keyframes bcwOpen {
      from {
        opacity: 0;
        transform:
          translateY(22px)
          scale(0.96);
      }

      to {
        opacity: 1;
        transform:
          translateY(0)
          scale(1);
      }
    }

    @media (max-width: 950px) {
      .bcw-wrapper {
        right: 0;
        bottom: 0;
      }

      .bcw-panel {
        width: 100vw;
        height: 100vh;
        min-height: 0;
        max-height: none;
        border: 0;
        border-radius: 0;
      }

      .bcw-bubble {
        position: fixed;
        right: 15px;
        bottom: 15px;
      }
    }
  `;

  function openPanel() {
    contextSite.textContent =
      window.location.hostname || "העמוד הנוכחי";

    contextTitle.textContent =
      document.title || "עמוד אינטרנט";

    panel.hidden = false;
    bubble.hidden = true;
  }

  function closePanel() {
    panel.hidden = true;
    bubble.hidden = false;
  }

  bubble.addEventListener("click", openPanel);

  header
    .querySelector(".bcw-minimize")
    .addEventListener("click", closePanel);

  header
    .querySelector(".bcw-close")
    .addEventListener("click", closePanel);

  document.addEventListener("keydown", (event) => {
    if (
      event.key === "Escape"
      && !panel.hidden
    ) {
      closePanel();
    }
  });

  shadow.append(style, wrapper);
  document.documentElement.appendChild(root);
})();
