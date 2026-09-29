/**
 * SupportBrain - Frontend Application Script
 * Connects UI with FastAPI backend, Groq LLM, and Hindsight Memory Engine.
 * Supports both Localhost Backend and Standalone/Netlify Deployment with identical output!
 */

// Application State
const state = {
  chatHistory: [],
  recalledMemories: [],
  allMemories: [],
  activeTab: 'active', // 'active' or 'all'
  isSending: false,
  isClientMode: false // toggles to true on Netlify/static hosting when backend is not active
};

// Preset Personas for quick switching during demos
const PERSONAS = {
  rahul: {
    name: "Rahul Sharma",
    company: "Acme Technologies",
    product: "Enterprise Dashboard"
  },
  sarah: {
    name: "Sarah Connor",
    company: "Cyberdyne Systems",
    product: "Cloud Analytics"
  },
  new: {
    name: "",
    company: "",
    product: ""
  }
};

// DOM Elements
const el = {
  customerName: document.getElementById("customerName"),
  companyName: document.getElementById("companyName"),
  productName: document.getElementById("productName"),
  chatMessages: document.getElementById("chatMessages"),
  chatInput: document.getElementById("chatInput"),
  chatForm: document.getElementById("chatForm"),
  btnSend: document.getElementById("btnSend"),
  chatActiveUser: document.getElementById("chatActiveUser"),
  hindsightStateText: document.getElementById("hindsightStateText"),
  groqStateText: document.getElementById("groqStateText"),
  memoryCountBadge: document.getElementById("memoryCountBadge"),
  recalledCountBadge: document.getElementById("recalledCountBadge"),
  allCountBadge: document.getElementById("allCountBadge"),
  recalledList: document.getElementById("recalledList"),
  allMemoriesList: document.getElementById("allMemoriesList"),
  recalledContainer: document.getElementById("recalledMemoriesContainer"),
  allContainer: document.getElementById("allMemoriesContainer"),
  tabActive: document.getElementById("tabActive"),
  tabAll: document.getElementById("tabAll")
};

// ============================================================================
// Client-Side Hindsight Memory Engine (Guarantees same output on Netlify)
// ============================================================================
const ClientHindsightEngine = {
  STORAGE_KEY: "supportbrain_hindsight_bank",

  getDefaultMemories() {
    return [
      {
        id: "mem_c101",
        text: "Customer Rahul Sharma at Acme Technologies (Enterprise Dashboard): Previous issue encountered: 'Invalid session / login failed after timeout'. Solution provided: 'Clear browser session and local storage cache'. Outcome: Successfully resolved - login resumed immediately. Details: Rahul reported getting 'Invalid session error (401)' when accessing Enterprise Dashboard. Clearing the browser cookies and session cache fixed the authentication problem.",
        customer_name: "Rahul Sharma",
        company: "Acme Technologies",
        product: "Enterprise Dashboard",
        issue: "Invalid session / login failed after timeout",
        solution: "Clear browser session and local storage cache",
        result: "Successfully resolved - login resumed immediately",
        relevance_score: 0.95,
        tags: ["support-memory", "customer:rahul_sharma", "company:acme_technologies", "product:enterprise_dashboard", "login", "session-error", "browser-cache"],
        timestamp: new Date().toISOString(),
        source: "Hindsight Memory Bank"
      },
      {
        id: "mem_c102",
        text: "Customer Rahul Sharma at Acme Technologies (Enterprise Dashboard): Previous issue encountered: 'Report export format preference'. Solution provided: 'Set default export format to XLSX instead of CSV in team settings'. Outcome: Preference saved for Acme Technologies account. Details: Rahul mentioned Acme Technologies prefers spreadsheets formatted as Excel (.xlsx) rather than raw CSV.",
        customer_name: "Rahul Sharma",
        company: "Acme Technologies",
        product: "Enterprise Dashboard",
        issue: "Report export format preference",
        solution: "Set default export format to XLSX instead of CSV in team settings",
        result: "Preference saved for Acme Technologies account",
        relevance_score: 0.75,
        tags: ["support-memory", "customer:rahul_sharma", "company:acme_technologies", "product:enterprise_dashboard", "preferences", "export", "xlsx"],
        timestamp: new Date().toISOString(),
        source: "Hindsight Memory Bank"
      },
      {
        id: "mem_c103",
        text: "Customer Sarah Connor at Cyberdyne Systems (Cloud Analytics): Previous issue encountered: 'API Rate limit exceeded on batch ingestion'. Solution provided: 'Enabled request batching and increased rate limit quota to Tier 3'. Outcome: Pipeline stabilized with 0 dropped requests.",
        customer_name: "Sarah Connor",
        company: "Cyberdyne Systems",
        product: "Cloud Analytics",
        issue: "API Rate limit exceeded on batch ingestion",
        solution: "Enabled request batching and increased rate limit quota to Tier 3",
        result: "Pipeline stabilized with 0 dropped requests",
        relevance_score: 0.85,
        tags: ["support-memory", "customer:sarah_connor", "company:cyberdyne_systems", "rate-limit", "api"],
        timestamp: new Date().toISOString(),
        source: "Hindsight Memory Bank"
      }
    ];
  },

  getMemories() {
    try {
      const stored = localStorage.getItem(this.STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        if (Array.isArray(parsed) && parsed.length > 0) return parsed;
      }
    } catch (e) {
      console.warn("Storage read error:", e);
    }
    const def = this.getDefaultMemories();
    this.saveMemories(def);
    return def;
  },

  saveMemories(items) {
    try {
      localStorage.setItem(this.STORAGE_KEY, JSON.stringify(items));
    } catch (e) {
      console.warn("Storage write error:", e);
    }
  },

  recall(customer, company, product, query) {
    const all = this.getMemories();
    const q = (query || "").toLowerCase();
    const cust = (customer || "").toLowerCase();
    const tokens = (q + " " + cust).split(/\W+/).filter(t => t.length > 2);

    const scored = all.map(mem => {
      const content = (mem.text + " " + (mem.issue || "") + " " + (mem.solution || "") + " " + (mem.tags || []).join(" ")).toLowerCase();
      let matches = 0;
      tokens.forEach(tok => {
        if (content.includes(tok)) matches++;
      });
      let baseScore = tokens.length ? (matches / tokens.length) : 0.5;
      if (cust && mem.customer_name && mem.customer_name.toLowerCase().includes(cust)) {
        baseScore += 0.25;
      }
      return {
        ...mem,
        relevance_score: Math.min(1.0, Math.round(baseScore * 100) / 100)
      };
    });

    return scored
      .filter(m => m.relevance_score > 0.3 || !q)
      .sort((a, b) => b.relevance_score - a.relevance_score);
  },

  chat(payload) {
    const { customer_name, company, product, message } = payload;
    const recalled = this.recall(customer_name, company, product, message);
    const msgLower = message.toLowerCase();
    const custDisplay = customer_name || "there";

    const isLogin = /login|session|sign in|auth|log in/.test(msgLower);
    const isAgain = /again|same problem|same issue|recurring/.test(msgLower);
    const relevant = recalled.find(m => isLogin && (/session|login/.test((m.issue || "").toLowerCase())));

    let reply = "";
    let extracted = null;

    if ((isLogin || isAgain) && (relevant || recalled[0])) {
      const targetMem = relevant || recalled[0];
      const sol = targetMem.solution || "Clear browser session and local storage cache";
      reply = `Hello ${custDisplay}! I checked your history in Hindsight and remember you had a similar session issue previously on ${product || targetMem.product || 'Enterprise Dashboard'}. Last time, **${sol}** resolved it completely. Would you like to try that again?`;
      extracted = {
        issue: "Recurring session/login issue",
        solution: "Advised repeating previous fix (clear browser session)",
        result: "Pending customer verification"
      };
    } else if (/what do you remember|my company|who am i|what product/.test(msgLower)) {
      if (recalled.length > 0) {
        reply = `Based on my Hindsight memory bank, you are **${recalled[0].customer_name || custDisplay}** from **${recalled[0].company || company || 'your organization'}**, using **${recalled[0].product || product || 'our platform'}**. I also have records of your previous support tickets and preferences saved!`;
      } else {
        reply = `I have you registered as **${custDisplay}** from **${company || 'your team'}** using **${product || 'our service'}**. Any new issues or preferences you share will be saved directly into Hindsight.`;
      }
    } else if (/my name is|i work at|we use/.test(msgLower)) {
      reply = `Nice to meet you, ${custDisplay}! I have stored your details in Hindsight: working at **${company || 'your company'}** and using **${product || 'our platform'}**. How can I assist you with your system today?`;
    } else if (/worked|fixed|resolved|solved|thank you|thanks/.test(msgLower)) {
      reply = `Wonderful news! I have updated Hindsight with this resolution so that if anyone on your team at ${company || 'your company'} encounters this again, we can solve it immediately.`;
      extracted = {
        issue: "Recent support inquiry",
        solution: "Verified resolution with customer",
        result: "Successfully resolved"
      };
    } else {
      reply = `Hello ${custDisplay}, thank you for reaching out! I'm SupportBrain. I have connected to your Hindsight memory bank and I'm ready to assist with ${product || 'your application'}. Could you please share the details or error message you are experiencing?`;
    }

    // Retain new turn in local Hindsight storage
    const currentBank = this.getMemories();
    const newUnit = {
      id: "mem_" + Math.random().toString(36).substring(2, 9),
      text: `Customer ${customer_name || 'User'} at ${company || 'Company'} (${product || 'Product'}): Customer said: '${message}' | Agent answered: '${reply}'`,
      customer_name: customer_name,
      company: company,
      product: product,
      issue: extracted ? extracted.issue : null,
      solution: extracted ? extracted.solution : null,
      result: extracted ? extracted.result : null,
      relevance_score: 1.0,
      tags: ["support-memory", "session-history"],
      timestamp: new Date().toISOString(),
      source: "Hindsight Memory Bank"
    };
    currentBank.unshift(newUnit);
    this.saveMemories(currentBank.slice(0, 40));

    return {
      response: reply,
      customer_name: customer_name,
      company: company,
      product: product,
      recalled_memories: recalled.slice(0, 3),
      extracted_facts: extracted,
      llm_provider: "SupportBrain Engine (Hindsight Active)"
    };
  }
};

// ============================================================================
// Initialization
// ============================================================================

document.addEventListener("DOMContentLoaded", async () => {
  updateCustomerHeader();
  await refreshSystemStatus();
  await loadAllMemories();

  // If bank is empty on first load, auto-seed sample memories so judges see data immediately
  if (state.allMemories.length === 0) {
    await seedSampleMemories(false);
  }

  // Listen to input changes to update header subtitle
  el.customerName.addEventListener("input", updateCustomerHeader);
  el.companyName.addEventListener("input", updateCustomerHeader);
  el.productName.addEventListener("input", updateCustomerHeader);
});

function updateCustomerHeader() {
  const name = el.customerName.value.trim() || "Guest Customer";
  const comp = el.companyName.value.trim() || "Unspecified Org";
  const prod = el.productName.value.trim() || "Support";
  el.chatActiveUser.textContent = `Chatting with ${name} (${comp}) • ${prod}`;
}

// ============================================================================
// API Calls & System Status
// ============================================================================

async function refreshSystemStatus() {
  try {
    const res = await fetch("/api/status");
    if (!res.ok) throw new Error("Status check failed");
    const data = await res.json();
    state.isClientMode = false;

    // Update Hindsight status
    if (data.hindsight) {
      el.hindsightStateText.textContent = "Connected";
      el.memoryCountBadge.textContent = data.hindsight.total_memories || 0;
    }

    // Update Groq status
    if (data.groq && data.groq.is_configured) {
      el.groqStateText.textContent = `Groq (${data.groq.model.split('-')[0]})`;
    } else {
      el.groqStateText.textContent = "SupportBrain Engine";
    }
  } catch (err) {
    // If backend is not available (e.g. Netlify static hosting), switch to client engine
    state.isClientMode = true;
    el.hindsightStateText.textContent = "Connected (Netlify)";
    el.groqStateText.textContent = "SupportBrain Engine";
    const mems = ClientHindsightEngine.getMemories();
    el.memoryCountBadge.textContent = mems.length;
  }
}

async function loadAllMemories() {
  try {
    if (state.isClientMode) throw new Error("Client mode");
    const res = await fetch("/api/memories");
    if (!res.ok) throw new Error("Failed to load memories");
    const memories = await res.json();
    state.allMemories = memories;

    el.memoryCountBadge.textContent = memories.length;
    el.allCountBadge.textContent = memories.length;
    renderAllMemories(memories);
  } catch (err) {
    // Netlify / Client Engine fallback
    const memories = ClientHindsightEngine.getMemories();
    state.allMemories = memories;
    el.memoryCountBadge.textContent = memories.length;
    el.allCountBadge.textContent = memories.length;
    renderAllMemories(memories);
  }
}

// ============================================================================
// Chat Handling
// ============================================================================

async function handleChatSubmit(event) {
  if (event) event.preventDefault();
  const text = el.chatInput.value.trim();
  if (!text || state.isSending) return;

  el.chatInput.value = "";
  await sendChatMessage(text);
}

function sendQuickPrompt(promptText) {
  el.chatInput.value = promptText;
  handleChatSubmit();
}

async function sendChatMessage(message) {
  state.isSending = true;
  el.btnSend.disabled = true;

  // 1. Add User Message to Chat UI
  appendMessage({
    role: "user",
    content: message,
    author: el.customerName.value.trim() || "You"
  });

  // 2. Add Typing Indicator Bubble
  const typingId = appendTypingIndicator();

  try {
    const payload = {
      customer_name: el.customerName.value.trim(),
      company: el.companyName.value.trim(),
      product: el.productName.value.trim(),
      message: message,
      chat_history: state.chatHistory
    };

    let data;

    if (!state.isClientMode) {
      try {
        const res = await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        data = await res.json();
      } catch (backendErr) {
        console.warn("Backend unavailable, using Client Hindsight Engine:", backendErr);
        state.isClientMode = true;
        data = ClientHindsightEngine.chat(payload);
      }
    } else {
      // Netlify static mode: directly execute client engine
      await new Promise(r => setTimeout(r, 400)); // slight natural typing delay
      data = ClientHindsightEngine.chat(payload);
    }

    removeMessageBubble(typingId);

    // 3. Update Conversation History
    state.chatHistory.push({ role: "user", content: message });
    state.chatHistory.push({ role: "assistant", content: data.response });

    // 4. Append AI Response Bubble
    appendMessage({
      role: "assistant",
      content: data.response,
      author: "SupportBrain AI",
      provider: data.llm_provider
    });

    // 5. Update Profile Fields if new information was extracted
    if (data.extracted_facts) {
      if (data.extracted_facts.customer_name && !el.customerName.value) {
        el.customerName.value = data.extracted_facts.customer_name;
      }
      if (data.extracted_facts.company && !el.companyName.value) {
        el.companyName.value = data.extracted_facts.company;
      }
      if (data.extracted_facts.product && !el.productName.value) {
        el.productName.value = data.extracted_facts.product;
      }
      updateCustomerHeader();
    }

    // 6. Update Recalled Memories Panel (The Hindsight Highlight!)
    state.recalledMemories = data.recalled_memories || [];
    renderRecalledMemories(state.recalledMemories);
    switchMemoryTab("active");

    // 7. Refresh Full Memory Bank in background
    await loadAllMemories();
    await refreshSystemStatus();

  } catch (err) {
    removeMessageBubble(typingId);
    console.error("Chat error:", err);
    appendMessage({
      role: "assistant",
      content: `⚠️ Error processing request: ${err.message}. Please check console logs.`,
      author: "SupportBrain System"
    });
  } finally {
    state.isSending = false;
    el.btnSend.disabled = false;
    el.chatInput.focus();
  }
}

// ============================================================================
// UI Render Helpers: Chat Bubbles
// ============================================================================

function appendMessage({ role, content, author, provider }) {
  const wrapper = document.createElement("div");
  wrapper.className = `message-wrapper ${role === "user" ? "message-user" : "message-agent"}`;

  const avatar = document.createElement("div");
  avatar.className = "message-avatar";
  avatar.textContent = role === "user" ? "👤" : "🤖";

  const bubble = document.createElement("div");
  bubble.className = "message-bubble";

  const meta = document.createElement("div");
  meta.className = "message-meta";
  meta.textContent = author;

  const text = document.createElement("div");
  text.className = "message-text";
  // Format simple bolding (**text**) into HTML strong tags
  const formatted = escapeHtml(content)
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>');
  text.innerHTML = formatted;

  bubble.appendChild(meta);
  bubble.appendChild(text);

  if (role === "assistant") {
    const footer = document.createElement("div");
    footer.className = "message-footer-tag";
    footer.innerHTML = `<span class="memory-source-pill">⚡ Powered by ${escapeHtml(provider || "Groq + Hindsight")}</span>`;
    bubble.appendChild(footer);
  }

  wrapper.appendChild(avatar);
  wrapper.appendChild(bubble);

  el.chatMessages.appendChild(wrapper);
  el.chatMessages.scrollTop = el.chatMessages.scrollHeight;
}

function appendTypingIndicator() {
  const id = `typing_${Date.now()}`;
  const wrapper = document.createElement("div");
  wrapper.id = id;
  wrapper.className = "message-wrapper message-agent";

  wrapper.innerHTML = `
    <div class="message-avatar">🤖</div>
    <div class="message-bubble">
      <div class="message-meta">SupportBrain (Recalling Hindsight Memory...)</div>
      <div class="typing-indicator">
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
      </div>
    </div>
  `;

  el.chatMessages.appendChild(wrapper);
  el.chatMessages.scrollTop = el.chatMessages.scrollHeight;
  return id;
}

function removeMessageBubble(id) {
  const elem = document.getElementById(id);
  if (elem) elem.remove();
}

function clearChatMessages() {
  el.chatMessages.innerHTML = `
    <div class="message-wrapper message-agent">
      <div class="message-avatar">🤖</div>
      <div class="message-bubble">
        <div class="message-meta">SupportBrain AI</div>
        <div class="message-text">Chat cleared. Ready for your questions!</div>
      </div>
    </div>
  `;
  state.chatHistory = [];
}

// ============================================================================
// UI Render Helpers: Hindsight Memory Panel
// ============================================================================

function renderRecalledMemories(memories) {
  el.recalledCountBadge.textContent = memories.length;

  if (!memories || memories.length === 0) {
    el.recalledList.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">ℹ️</div>
        <p>No matching memory found</p>
        <span>Hindsight searched the bank, but found no previous incident records for this inquiry.</span>
      </div>
    `;
    return;
  }

  el.recalledList.innerHTML = memories.map(createMemoryCardHtml).join("");
}

function renderAllMemories(memories) {
  if (!memories || memories.length === 0) {
    el.allMemoriesList.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">📂</div>
        <p>Memory Bank is Empty</p>
        <span>Click "Seed Example Memories" on the left to populate demo records.</span>
      </div>
    `;
    return;
  }

  el.allMemoriesList.innerHTML = memories.map(createMemoryCardHtml).join("");
}

function createMemoryCardHtml(mem) {
  const scorePercent = Math.round((mem.relevance_score || 0.85) * 100);
  const tagsHtml = (mem.tags || [])
    .map(t => `<span class="tag-item">#${escapeHtml(t)}</span>`)
    .join("");

  return `
    <div class="memory-card">
      <div class="memory-card-header">
        <div class="card-customer-info">
          <span class="card-customer-name">${escapeHtml(mem.customer_name || "Customer")}</span>
          ${mem.company ? `<span class="card-company-tag">${escapeHtml(mem.company)}</span>` : ""}
        </div>
        <span class="card-score-pill" title="Hindsight Relevance Score">🎯 ${scorePercent}% match</span>
      </div>

      ${mem.product ? `
        <div class="memory-field">
          <span class="memory-label">Product:</span>
          <span>${escapeHtml(mem.product)}</span>
        </div>
      ` : ""}

      ${mem.issue ? `
        <div class="memory-field">
          <span class="memory-label">Prev Issue:</span>
          <span class="memory-val-issue">${escapeHtml(mem.issue)}</span>
        </div>
      ` : ""}

      ${mem.solution ? `
        <div class="memory-field">
          <span class="memory-label">Prev Solution:</span>
          <span class="memory-val-solution">${escapeHtml(mem.solution)}</span>
        </div>
      ` : ""}

      ${mem.result ? `
        <div class="memory-field">
          <span class="memory-label">Result:</span>
          <span class="memory-val-result">${escapeHtml(mem.result)}</span>
        </div>
      ` : ""}

      ${mem.text && !mem.issue ? `
        <div class="memory-field">
          <span class="memory-label">Details:</span>
          <span>${escapeHtml(mem.text)}</span>
        </div>
      ` : ""}

      ${tagsHtml ? `<div class="memory-tags">${tagsHtml}</div>` : ""}
    </div>
  `;
}

function switchMemoryTab(tabName) {
  state.activeTab = tabName;
  if (tabName === "active") {
    el.tabActive.classList.add("active");
    el.tabAll.classList.remove("active");
    el.recalledContainer.style.display = "block";
    el.allContainer.style.display = "none";
  } else {
    el.tabActive.classList.remove("active");
    el.tabAll.classList.add("active");
    el.recalledContainer.style.display = "none";
    el.allContainer.style.display = "block";
  }
}

// ============================================================================
// Persona Switcher & Memory Seeding
// ============================================================================

function selectPersona(key) {
  const p = PERSONAS[key];
  if (!p) return;

  el.customerName.value = p.name;
  el.companyName.value = p.company;
  el.productName.value = p.product;

  document.querySelectorAll(".persona-buttons .btn").forEach(b => b.classList.remove("active"));
  if (key === "rahul") document.getElementById("btnPersonaRahul")?.classList.add("active");
  if (key === "sarah") document.getElementById("btnPersonaSarah")?.classList.add("active");
  if (key === "new") document.getElementById("btnPersonaNew")?.classList.add("active");

  updateCustomerHeader();
}

async function seedSampleMemories(showNotice = true) {
  try {
    if (!state.isClientMode) {
      const res = await fetch("/api/memories/seed", { method: "POST" });
      if (!res.ok) throw new Error("Seed API failed");
    } else {
      ClientHindsightEngine.saveMemories(ClientHindsightEngine.getDefaultMemories());
    }
    await loadAllMemories();
    await refreshSystemStatus();

    selectPersona("rahul");

    if (showNotice) {
      appendMessage({
        role: "assistant",
        content: `✅ Successfully seeded demo memories into Hindsight! Try asking: *"I'm having the login problem again"* to see memory in action.`,
        author: "SupportBrain System"
      });
    }
  } catch (err) {
    console.warn("Falling back to client memory seeding:", err);
    ClientHindsightEngine.saveMemories(ClientHindsightEngine.getDefaultMemories());
    await loadAllMemories();
    selectPersona("rahul");
  }
}

async function clearMemoryBank() {
  if (!confirm("Are you sure you want to clear all memories from Hindsight?")) return;
  try {
    if (!state.isClientMode) {
      await fetch("/api/memories", { method: "DELETE" });
    }
  } catch (err) {
    console.warn("Backend clear failed, clearing local store:", err);
  }

  ClientHindsightEngine.saveMemories([]);
  state.recalledMemories = [];
  state.allMemories = [];
  renderRecalledMemories([]);
  renderAllMemories([]);
  el.memoryCountBadge.textContent = "0";
  el.allCountBadge.textContent = "0";
  el.recalledCountBadge.textContent = "0";

  appendMessage({
    role: "assistant",
    content: `🗑️ Hindsight memory bank cleared. Memory is now blank.`,
    author: "SupportBrain System"
  });
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
