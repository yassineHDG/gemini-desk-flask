const appRoot = document.querySelector("#app");
const form = document.querySelector("#chat-form");
const input = document.querySelector("#message-input");
const fileInput = document.querySelector("#file-input");
const filePreview = document.querySelector("#file-preview");
const fileName = document.querySelector("#file-name");
const removeFileButton = document.querySelector("#remove-file");
const messages = document.querySelector("#messages");
const messagePanel = document.querySelector("#message-panel");
const statusText = document.querySelector("#status");
const sendButton = document.querySelector("#send-button");
const categorySelect = document.querySelector("#category-select");
const clearButton = document.querySelector("#clear-conversation");
const exportLink = document.querySelector("#export-link");
const pageTitle = document.querySelector("#page-title");
const sidebar = document.querySelector("#sidebar");
const sidebarBackdrop = document.querySelector("#sidebar-backdrop");
const responseModeInputs = [...document.querySelectorAll('input[name="response_modes"]')];

let conversationId = window.GEMINI_DESK.conversationId;

async function api(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `Erreur HTTP ${response.status}`);
  return data;
}

function setBusy(isBusy, text = "Gemini analyse votre demande…") {
  sendButton.disabled = isBusy;
  input.disabled = isBusy;
  fileInput.disabled = isBusy;
  responseModeInputs.forEach((modeInput) => {
    modeInput.disabled = isBusy;
  });
  statusText.textContent = isBusy ? text : "PDF, image, SQL, Excel, Word · 15 Mo max.";
}

function scrollToBottom() {
  requestAnimationFrame(() => {
    messagePanel.scrollTop = messagePanel.scrollHeight;
  });
}

function removeEmptyState() {
  document.querySelector("#empty-state")?.remove();
}

function createEmptyState() {
  messages.innerHTML = `
    <div id="empty-state" class="mx-auto flex max-w-xl flex-col items-center py-16 text-center sm:py-24">
      <div class="grid size-12 place-items-center rounded-2xl border border-blue-200 bg-blue-50 text-blue-700">GD</div>
      <h2 class="mt-5 text-2xl font-semibold tracking-tight">Conversation effacée</h2>
      <p class="mt-3 text-sm leading-6 text-slate-600">Vous pouvez recommencer avec une nouvelle demande.</p>
    </div>`;
}

function appendMessage(message) {
  removeEmptyState();
  const article = document.createElement("article");
  article.className = `message-block ${message.role === "user" ? "message-user" : "message-assistant"}`;
  if (message.id) article.dataset.messageId = message.id;

  const role = document.createElement("div");
  role.className = "message-role";
  role.textContent = message.role === "user" ? "Vous" : "Gemini";
  article.appendChild(role);

  if (message.attachment_name) {
    const attachment = document.createElement("div");
    attachment.className = "attachment-badge";
    attachment.textContent = message.attachment_name;
    article.appendChild(attachment);
  }

  const content = document.createElement("div");
  content.className = "message-content";
  if (message.role === "assistant") content.classList.add("markdown-body");
  if (message.role === "assistant" && Array.isArray(message.confidence_segments) && message.confidence_segments.length) {
    content.classList.add("confidence-content");
    content.setAttribute("aria-label", "Réponse avec niveaux de confiance");
    message.confidence_segments.forEach((segment) => {
      const confidence = segment.confidence === "sure" ? "sure" : "uncertain";
      const block = document.createElement("div");
      block.className = `confidence-segment confidence-${confidence}`;
      block.dataset.confidence = confidence;
      if (segment.html) block.innerHTML = segment.html;
      else block.textContent = segment.text || "";
      content.appendChild(block);
    });
  } else if (message.role === "assistant" && message.content_html) {
    content.innerHTML = message.content_html;
  } else {
    content.textContent = message.content || "";
  }
  article.appendChild(content);

  if (message.role === "assistant" && Array.isArray(message.confidence_segments) && message.confidence_segments.length) {
    const caption = document.createElement("p");
    caption.className = "confidence-caption";
    caption.textContent = "Confiance auto-évaluée par Gemini — ce marquage ne garantit pas l’exactitude.";
    article.appendChild(caption);
  }

  if (message.sql_report) appendSqlReport(article, message.sql_report);

  if (message.role === "assistant" && message.total_tokens !== null && message.total_tokens !== undefined) {
    const metrics = document.createElement("div");
    metrics.className = "message-metrics";
    const values = [
      `${message.total_tokens} tokens`,
      `${message.input_tokens || 0} entrée`,
      `${message.output_tokens || 0} sortie`,
      `${((message.response_time_ms || 0) / 1000).toFixed(2)} s`,
    ];
    values.forEach((value) => {
      const span = document.createElement("span");
      span.textContent = value;
      metrics.appendChild(span);
    });
    article.appendChild(metrics);
  }

  messages.appendChild(article);
  scrollToBottom();
  return article;
}

function appendSqlReport(article, report) {
  const details = document.createElement("details");
  details.className = "sql-report mt-4";
  const summary = document.createElement("summary");
  summary.textContent = `Rapport SQL — ${report.score}/100 · ${report.status}`;
  const list = document.createElement("ul");
  report.recommendations.forEach((recommendation) => {
    const item = document.createElement("li");
    item.textContent = recommendation;
    list.appendChild(item);
  });
  details.append(summary, list);
  article.appendChild(details);
}

function updateConversationUi(conversation) {
  conversationId = conversation.id;
  appRoot.dataset.conversationId = conversation.id;
  pageTitle.textContent = conversation.title;
  clearButton.disabled = false;
  exportLink.classList.remove("pointer-events-none", "opacity-50");
  exportLink.href = `/conversations/${conversation.id}/export.txt`;
  window.history.replaceState({}, "", `/?conversation_id=${conversation.id}`);

  let row = document.querySelector(`[data-conversation-row="${conversation.id}"]`);
  document.querySelectorAll(".conversation-row").forEach((item) => item.classList.remove("is-active"));
  if (!row) {
    document.querySelector("#history-empty")?.remove();
    row = document.createElement("div");
    row.className = "conversation-row group is-active";
    row.dataset.conversationRow = conversation.id;
    row.innerHTML = `
      <a href="/?conversation_id=${conversation.id}" class="min-w-0 flex-1 py-2.5 pl-3">
        <span class="block truncate text-sm font-medium" data-conversation-title></span>
        <span class="mt-0.5 block truncate text-[11px] text-slate-500"></span>
      </a>
      <button type="button" class="conversation-delete icon-button mr-1 opacity-0 group-hover:opacity-100 focus:opacity-100" data-delete-conversation="${conversation.id}" aria-label="Supprimer cette conversation">×</button>`;
    document.querySelector("#conversation-list").prepend(row);
  } else {
    row.classList.add("is-active");
  }
  row.querySelector("[data-conversation-title]").textContent = conversation.title;
  row.querySelector("a span:last-child").textContent = categorySelect.options[categorySelect.selectedIndex].text;
  document.querySelector("#conversation-count").textContent = document.querySelectorAll(".conversation-row").length;
}

async function ensureConversation() {
  if (conversationId) return conversationId;
  const data = await api("/api/conversations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ category: categorySelect.value }),
  });
  updateConversationUi(data.conversation);
  return conversationId;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = input.value.trim();
  const selectedFile = fileInput.files[0];
  if (!text && !selectedFile) {
    statusText.textContent = "Écrivez un message ou choisissez un fichier.";
    return;
  }

  try {
    setBusy(true);
    const id = await ensureConversation();
    const formData = new FormData();
    formData.append("message", text);
    if (selectedFile) formData.append("file", selectedFile);
    responseModeInputs.forEach((modeInput) => {
      if (modeInput.checked) formData.append("response_modes", modeInput.value);
    });

    const optimisticText = text || "Analyse ce fichier et réponds à la demande qu'il contient.";
    const userArticle = appendMessage({
      role: "user",
      content: optimisticText,
      attachment_name: selectedFile?.name || null,
    });
    input.value = "";
    input.style.height = "auto";

    const data = await api(`/api/conversations/${id}/messages`, { method: "POST", body: formData });
    if (data.sql_report) appendSqlReport(userArticle, data.sql_report);
    appendMessage(data.assistant_message);
    updateConversationUi(data.conversation);
    fileInput.value = "";
    filePreview.classList.add("hidden");
  } catch (error) {
    appendMessage({ role: "assistant", content: `Erreur : ${error.message}` });
    statusText.textContent = error.message;
  } finally {
    setBusy(false);
    input.focus();
  }
});

document.querySelector("#new-conversation").addEventListener("click", async () => {
  try {
    const data = await api("/api/conversations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ category: categorySelect.value }),
    });
    window.location.href = `/?conversation_id=${data.conversation.id}`;
  } catch (error) {
    statusText.textContent = error.message;
  }
});

clearButton.addEventListener("click", async () => {
  if (!conversationId) return;
  if (!window.confirm("Effacer tous les messages de cette conversation ?")) return;
  try {
    const data = await api(`/api/conversations/${conversationId}/messages`, { method: "DELETE" });
    createEmptyState();
    updateConversationUi(data.conversation);
  } catch (error) {
    statusText.textContent = error.message;
  }
});

document.querySelector("#conversation-list").addEventListener("click", async (event) => {
  const button = event.target.closest("[data-delete-conversation]");
  if (!button) return;
  event.preventDefault();
  const id = Number(button.dataset.deleteConversation);
  if (!window.confirm("Supprimer définitivement cette conversation ?")) return;
  try {
    await api(`/api/conversations/${id}`, { method: "DELETE" });
    if (id === conversationId) window.location.href = "/";
    else button.closest(".conversation-row").remove();
  } catch (error) {
    statusText.textContent = error.message;
  }
});

categorySelect.addEventListener("change", async () => {
  window.GEMINI_DESK.category = categorySelect.value;
  if (!conversationId) return;
  try {
    const data = await api(`/api/conversations/${conversationId}/category`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ category: categorySelect.value }),
    });
    updateConversationUi(data.conversation);
    statusText.textContent = `Mode ${categorySelect.options[categorySelect.selectedIndex].text} activé.`;
  } catch (error) {
    statusText.textContent = error.message;
  }
});

document.querySelectorAll("[data-category-chip]").forEach((chip) => {
  chip.addEventListener("click", () => {
    categorySelect.value = chip.dataset.categoryChip;
    categorySelect.dispatchEvent(new Event("change"));
    input.focus();
  });
});

fileInput.addEventListener("change", () => {
  const file = fileInput.files[0];
  if (!file) return;
  fileName.textContent = `${file.name} · ${(file.size / 1024 / 1024).toFixed(2)} Mo`;
  filePreview.classList.remove("hidden");
  filePreview.classList.add("flex");
});

removeFileButton.addEventListener("click", () => {
  fileInput.value = "";
  filePreview.classList.add("hidden");
});

const savedResponseModes = (() => {
  try {
    return JSON.parse(window.localStorage.getItem("gemini-desk-response-modes") || "[]");
  } catch {
    return [];
  }
})();

responseModeInputs.forEach((modeInput) => {
  modeInput.checked = savedResponseModes.includes(modeInput.value);
  modeInput.addEventListener("change", () => {
    const selectedModes = responseModeInputs
      .filter((item) => item.checked)
      .map((item) => item.value);
    window.localStorage.setItem("gemini-desk-response-modes", JSON.stringify(selectedModes));
  });
});

input.addEventListener("input", () => {
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 160)}px`;
});

input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

function toggleSidebar(open) {
  sidebar.classList.toggle("-translate-x-full", !open);
  sidebarBackdrop.classList.toggle("hidden", !open);
}

document.querySelector("#open-sidebar").addEventListener("click", () => toggleSidebar(true));
document.querySelector("#close-sidebar").addEventListener("click", () => toggleSidebar(false));
sidebarBackdrop.addEventListener("click", () => toggleSidebar(false));
scrollToBottom();
