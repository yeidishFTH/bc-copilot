"use strict";

chrome.runtime.onInstalled.addListener(async () => {
  await chrome.sidePanel.setPanelBehavior({
    openPanelOnActionClick: true
  });
});

chrome.runtime.onMessage.addListener(
  (message, sender, sendResponse) => {
    if (message?.type !== "BC_WORKSPACE_OPEN") {
      return false;
    }

    const tabId = sender.tab?.id;

    if (typeof tabId !== "number") {
      sendResponse({
        ok: false,
        error: "Missing browser tab"
      });
      return false;
    }

    chrome.sidePanel
      .open({ tabId })
      .then(() => {
        sendResponse({ ok: true });
      })
      .catch((error) => {
        sendResponse({
          ok: false,
          error: String(error)
        });
      });

    return true;
  }
);
