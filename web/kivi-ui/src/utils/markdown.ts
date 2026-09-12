function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function renderMarkdown(text: string): string {
  const escaped = escapeHtml(text || "");
  const withBold = escaped.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  const lines = withBold.split("\n");
  const parts: string[] = [];
  let inList = false;

  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith("- ")) {
      if (!inList) {
        parts.push("<ul>");
        inList = true;
      }
      parts.push(`<li>${trimmed.slice(2)}</li>`);
    } else {
      if (inList) {
        parts.push("</ul>");
        inList = false;
      }
      if (trimmed) parts.push(`<p>${trimmed}</p>`);
    }
  }
  if (inList) parts.push("</ul>");
  return parts.join("") || "<p></p>";
}
