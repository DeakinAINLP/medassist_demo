const chatEl = document.getElementById("chat");
const structuredEl = document.getElementById("structured");
const formEl = document.getElementById("chatForm");
const userInput = document.getElementById("userInput");
const clearBtn = document.getElementById("clearBtn");
const pwdEl = document.getElementById("password");

let messages = [
  { role: "assistant", content: "Hi — I’m a demo medical conversation assistant. I can help summarize symptoms and suggest possible explanations and next steps, but I’m not a doctor and I can’t diagnose. What’s going on today?" }
];

function render() {
  chatEl.innerHTML = "";
  for (const m of messages) {
    const div = document.createElement("div");
    div.className = "msg " + (m.role === "user" ? "user" : "assistant");
    div.innerText = m.content;
    chatEl.appendChild(div);
  }
  chatEl.scrollTop = chatEl.scrollHeight;
}

function escapeHtml(str) {
  return (str || "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#039;"
  }[c]));
}

function renderStructured(payload) {
  if (!payload) {
    structuredEl.innerHTML = "<div class='muted'>No structured output yet.</div>";
    return;
  }

  const triage = escapeHtml(payload.triage_level || "");
  const summary = escapeHtml(payload.summary || "");
  const disclaimer = escapeHtml(payload.disclaimer || "");

  const questions = (payload.clarifying_questions || []).map(q => `<li>${escapeHtml(q)}</li>`).join("");
  const nextSteps = (payload.recommended_next_steps || []).map(x => `<li>${escapeHtml(x)}</li>`).join("");
  const seekCare = (payload.when_to_seek_care || []).map(x => `<li>${escapeHtml(x)}</li>`).join("");
  const possible = (payload.possible_conditions || []).map(c =>
    `<li><b>${escapeHtml(c.name || "")}</b> (${escapeHtml(c.confidence || "")}): ${escapeHtml(c.why || "")}</li>`
  ).join("");

  structuredEl.innerHTML = `
    <div class="pill">Triage: ${triage}</div>
    <h3>Summary</h3>
    <p>${summary}</p>

    <h3>Clarifying questions</h3>
    <ul>${questions || "<li class='muted'>None</li>"}</ul>

    <h3>Possible explanations (not diagnosis)</h3>
    <ul>${possible || "<li class='muted'>None</li>"}</ul>

    <h3>Recommended next steps</h3>
    <ul>${nextSteps || "<li class='muted'>None</li>"}</ul>

    <h3>When to seek care</h3>
    <ul>${seekCare || "<li class='muted'>None</li>"}</ul>

    <div class="disclaimer">${disclaimer}</div>
  `;
}

async function sendMessage(text) {
  messages.push({ role: "user", content: text });
  render();

  const body = {
    messages: messages.filter(m => m.role !== "system"),
  };

  if (window.__REQUIRE_PASSWORD__) {
    body.password = (pwdEl && pwdEl.value) ? pwdEl.value : null;
  }

  const res = await fetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });

  if (res.status === 401) {
    messages.push({ role: "assistant", content: "This demo is password protected. Please enter the password above." });
    render();
    return;
  }

  if (!res.ok) {
    const errText = await res.text();
    messages.push({ role: "assistant", content: "Error from server: " + errText });
    render();
    return;
  }

  const data = await res.json();
  const assistant = data.assistant || {};
  const triage = assistant.triage_level ? ` (triage: ${assistant.triage_level})` : "";
  const reply = assistant.summary
    ? assistant.summary + triage + "\n\n" +
      (assistant.recommended_next_steps ? "Next steps:\n- " + assistant.recommended_next_steps.join("\n- ") : "")
    : "Received a response.";

  messages.push({ role: "assistant", content: reply });
  render();
  renderStructured(assistant);
}

formEl.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = (userInput.value || "").trim();
  if (!text) return;
  userInput.value = "";
  sendMessage(text);
});

clearBtn.addEventListener("click", () => {
  messages = [
    { role: "assistant", content: "Hi — I’m a demo medical conversation assistant. I can help summarize symptoms and suggest possible explanations and next steps, but I’m not a doctor and I can’t diagnose. What’s going on today?" }
  ];
  render();
  renderStructured(null);
});

render();
renderStructured(null);
