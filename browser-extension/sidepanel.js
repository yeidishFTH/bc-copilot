"use strict";

const FRONTEND_URL = "http://localhost:3000/";

const frame = document.getElementById("workspace-frame");
const loading = document.getElementById("workspace-loading");
const errorPanel = document.getElementById("workspace-error");
const retry = document.getElementById("workspace-retry");

let timeoutId = null;

function showLoading() {
  loading.hidden = false;
  errorPanel.hidden = true;
  frame.hidden = true;
}

function showWorkspace() {
  window.clearTimeout(timeoutId);
  loading.hidden = true;
  errorPanel.hidden = true;
  frame.hidden = false;
}

function showError() {
  window.clearTimeout(timeoutId);
  loading.hidden = true;
  errorPanel.hidden = false;
  frame.hidden = true;
}

async function loadWorkspace() {
  showLoading();

  try {
    const response = await fetch(FRONTEND_URL, {
      method: "GET",
      cache: "no-store"
    });

    if (!response.ok) {
      throw new Error(`Frontend returned ${response.status}`);
    }

    frame.src =
      `${FRONTEND_URL}?bc_workspace=${Date.now()}`;

    timeoutId = window.setTimeout(showError, 10000);
  } catch (error) {
    console.error("BC Workspace frontend check failed:", error);
    showError();
  }
}

frame.addEventListener("load", showWorkspace);
frame.addEventListener("error", showError);
retry.addEventListener("click", loadWorkspace);

loadWorkspace();
