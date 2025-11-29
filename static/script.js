const messagesEl = document.getElementById("messages");
const skillsListEl = document.getElementById("skills-list");
const formEl = document.getElementById("chat-form");
const inputEl = document.getElementById("message-input");


const profileRolesEl = document.getElementById("profile-roles");
const profileSkillsEl = document.getElementById("profile-skills");
const llmToggleEl = document.getElementById("llm-toggle");

let sessionId = localStorage.getItem("skillbot_session_id") || null;
let isSending = false;

function appendMessage(role, text) {
  const row = document.createElement("div");
  row.className = `message-row ${role}`;

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;

  row.appendChild(bubble);
  messagesEl.appendChild(row);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function updateSkills(skills) {
  if (!skills) return;

  skillsListEl.innerHTML = "";
  if (skills.length === 0) {
    const span = document.createElement("span");
    span.className = "skill-meta";
    span.textContent = "No explicit skills detected for this message.";
    skillsListEl.appendChild(span);
    return;
  }

  skills.forEach((s) => {
    const chip = document.createElement("div");
    chip.className = "skill-chip";

    const title = document.createElement("strong");
    title.textContent = s.name || "Unknown";

    const meta = document.createElement("span");
    meta.className = "skill-meta";

    const category = s.category ? s.category : "Skill";
    const confidence =
      typeof s.confidence === "number"
        ? `${Math.round(s.confidence * 100)}%`
        : "N/A";

    meta.textContent = `${category} • confidence: ${confidence}`;
    chip.appendChild(title);
    chip.appendChild(meta);

    if (s.evidence) {
      const ev = document.createElement("span");
      ev.className = "skill-meta";
      ev.textContent = `evidence: ${s.evidence}`;
      chip.appendChild(ev);
    }

    skillsListEl.appendChild(chip);
  });
}

async function refreshProfile() {
  if (!sessionId) return;

  try {
    const res = await fetch(`/api/profile/${sessionId}`);
    if (!res.ok) {
      // profile may not exist yet if no turns saved
      return;
    }
    const data = await res.json();

    const roles = data.suggested_roles || [];
    if (roles.length) {
      profileRolesEl.textContent = `Suggested roles so far: ${roles.join(", ")}`;
    } else {
      profileRolesEl.textContent =
        "Keep chatting and I’ll build your skill profile and suggest roles.";
    }

    profileSkillsEl.innerHTML = "";
    const skills = data.skills || [];
    skills.forEach((s) => {
      const row = document.createElement("div");
      row.className = "profile-skill-row";
      row.textContent = `${s.name} (${s.category}) • ${s.count} mention(s) • avg confidence ${Math.round(
        s.avg_confidence * 100
      )}%`;
      profileSkillsEl.appendChild(row);
    });
  } catch (err) {
    console.error("Failed to refresh profile", err);
  }
}

async function sendMessage(message) {
  if (isSending) return;
  isSending = true;
  formEl.querySelector("button").disabled = true;

  appendMessage("user", message);
  appendMessage("bot", "Analyzing your skills...");

  try {
        const res = await fetch("/api/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        session_id: sessionId,
        message,
        use_llm: llmToggleEl ? llmToggleEl.checked : false,
      }),
    });


    if (!res.ok) {
      throw new Error(`HTTP error: ${res.status}`);
    }

    const data = await res.json();

    // update session id
    if (!sessionId) {
      sessionId = data.session_id;
      localStorage.setItem("skillbot_session_id", sessionId);
    }

    // Replace "Analyzing..." bubble with real reply
    messagesEl.lastChild.remove();
    appendMessage("bot", data.reply);
    updateSkills(data.skills || []);

    // Refresh aggregated profile
    await refreshProfile();
  } catch (err) {
    console.error(err);
    messagesEl.lastChild.remove();
    appendMessage(
      "bot",
      "Oops, something went wrong while talking to the skill engine."
    );
  } finally {
    isSending = false;
    formEl.querySelector("button").disabled = false;
  }
}

formEl.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = inputEl.value.trim();
  if (!text) return;
  inputEl.value = "";
  sendMessage(text);
});

// On load, if we already have a session, try to load its profile
if (sessionId) {
  refreshProfile();
}
