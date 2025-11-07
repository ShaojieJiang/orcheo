const wrapParagraphs = (text: string): string => {
  if (!text.trim()) {
    return "";
  }

  return `<p>${text}</p>`;
};

export const parseChatMarkdown = (text: string): string => {
  let parsedText = text.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");

  parsedText = parsedText.replace(/\*(.*?)\*/g, "<em>$1</em>");

  parsedText = parsedText.replace(
    /```(.*?)```/gs,
    "<pre><code>$1</code></pre>",
  );

  parsedText = parsedText.replace(/`(.*?)`/g, "<code>$1</code>");

  parsedText = parsedText.replace(
    /\[(.*?)\]\((.*?)\)/g,
    '<a href="$2" target="_blank" rel="noopener noreferrer" class="text-primary underline">$1</a>',
  );

  parsedText = parsedText.replace(/^\d+\.\s+(.*?)$/gm, "<li>$1</li>");
  parsedText = parsedText.replace(/^-\s+(.*?)$/gm, "<li>$1</li>");

  parsedText = parsedText.replace(/\n\n/g, "</p><p>");
  parsedText = parsedText.replace(/\n/g, "<br/>");

  return wrapParagraphs(parsedText);
};
