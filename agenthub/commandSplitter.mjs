/**
 * Smart shell command splitter.
 *
 * Replaces naive `commands.split("\n")` so that multi-line constructs
 * (heredocs, line continuations) stay as single array elements.
 *
 * Handles:
 *   - heredocs:        cat > file << "EOF" ... EOF
 *   - nested heredocs: outer << EOF containing inner << INNER
 *   - <<- (tab-indented delimiters)
 *   - line continuation: echo hello \
 *                        world
 */

/**
 * Find a heredoc delimiter on a line, ignoring << that appears inside quotes.
 * @returns {{delimiter: string, indentAware: boolean}|null}
 */
function findHeredocStart(line) {
  let inSingle = false;
  let inDouble = false;
  let escaping = false;

  for (let i = 0; i < line.length; i++) {
    const ch = line[i];

    if (escaping) {
      escaping = false;
      continue;
    }
    if (ch === "\\" && (inSingle || inDouble)) {
      escaping = true;
      continue;
    }

    // Toggle quote state
    if (ch === "'" && !inDouble) {
      inSingle = !inSingle;
      continue;
    }
    if (ch === '"' && !inSingle) {
      inDouble = !inDouble;
      continue;
    }

    // Only check for << when outside quotes
    if (!inSingle && !inDouble && ch === "<" && line[i + 1] === "<" && line[i + 2] !== "<") {
      const rest = line.substring(i + 2);
      const m = rest.match(/^-?\s*['"]?([a-zA-Z_]\w*)['"]?/);
      if (m) {
        return { delimiter: m[1], indentAware: rest.startsWith("-") };
      }
    }
  }
  return null;
}

/**
 * @param {string} text - Raw multi-line shell command string
 * @returns {string[]} - Commands array; multi-line blocks are single elements
 */
export function splitShellCommands(text) {
  if (!text || typeof text !== "string") return [];

  const lines = text.split("\n");
  const result = [];
  const block = [];
  const heredocStack = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    block.push(line);

    // Detect heredoc starts (including nested ones inside existing heredocs)
    const hd = findHeredocStart(line);
    if (hd) {
      heredocStack.push(hd);
    }

    // Check if this line terminates the innermost heredoc(s)
    const trimmed = line.trim();
    while (heredocStack.length > 0) {
      const top = heredocStack[heredocStack.length - 1];
      if (top.indentAware) {
        // <<- allows leading tabs before the delimiter
        const withoutTabs = line.replace(/^\t+/, "");
        if (withoutTabs === top.delimiter) {
          heredocStack.pop();
          continue;
        }
      }
      if (trimmed === top.delimiter) {
        heredocStack.pop();
        continue;
      }
      break;
    }

    // Check for line continuation (unescaped backslash at end of line)
    const hasContinuation = !!(line.match(/(^|[^\\])(\\\\)*\\$/));

    // Flush block when no active heredocs and no continuation pending
    if (heredocStack.length === 0 && !hasContinuation) {
      result.push(block.join("\n"));
      block.length = 0;
    }
  }

  // Flush any remaining block (best effort)
  if (block.length > 0) {
    result.push(block.join("\n"));
  }

  return result;
}
