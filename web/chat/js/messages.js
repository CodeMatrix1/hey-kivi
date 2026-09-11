/** Chat message list: append bubbles and clear. */

export function createMessages(messagesEl) {
  function addMsg(role, text) {
    const div = document.createElement("div");
    div.className = "msg " + (role === "user" ? "user" : "bot");
    const label = document.createElement("div");
    label.className = "label";
    label.textContent = role === "user" ? "You" : "Kivi";
    const body = document.createElement("div");
    body.textContent = text;
    div.appendChild(label);
    div.appendChild(body);
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function clear() {
    messagesEl.innerHTML = "";
  }

  return { addMsg, clear };
}
