/** API helpers for Hey Kivi chat UI. */

export async function getHealth() {
  const res = await fetch("/health");
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Health failed");
  return data;
}

export async function getStats(userId) {
  const res = await fetch(`/stats/${encodeURIComponent(userId)}`);
  const text = await res.text();
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    throw new Error(res.ok ? "Stats returned an invalid response" : `Stats failed (${res.status}): ${text.slice(0, 180)}`);
  }
  if (!res.ok) throw new Error(data.detail || "Stats failed");
  return data;
}

export async function postChat(userId, message) {
  const res = await fetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, user_id: userId }),
  });
  const text = await res.text();
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    throw new Error(res.ok ? "Chat returned an invalid response" : `Chat failed (${res.status}): ${text.slice(0, 180)}`);
  }
  if (!res.ok) throw new Error(data.detail || "Chat failed");
  return data;
}

export async function postSeed(userId) {
  const res = await fetch("/seed", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId }),
  });
  const text = await res.text();
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    throw new Error(res.ok ? "Seed returned an invalid response" : `Seed failed (${res.status}): ${text.slice(0, 180)}`);
  }
  if (!res.ok) throw new Error(data.detail || "Seed failed");
  return data;
}
