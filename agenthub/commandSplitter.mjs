/**
 * Smart shell command splitter.
 *
 * Replaces naive `commands.split("\n")` so that multi-line constructs
 * stay as single array elements. Handles:
 *
 *   - heredocs:               cat > file << "EOF" ... EOF
 *   - quoted strings:         python -c "code\ncode\ncode"
 *   - line continuations:     echo hello \
 *                             world
 */

/**
 * @param {string} text - Raw multi-line shell command string
 * @returns {string[]} - Commands array; multi-line blocks are single elements
 */
export function splitShellCommands(text) {
  if (!text || typeof text !== "string") return [];

  const lines = text.split("\n");
  const result = [];
  let currentCommand = [];
  const heredocStack = [];

  let inSingle = false;
  let inDouble = false;
  let escaping = false;

  for (let i = 0; i < lines.length; i++) {
    let line = lines[i];
    currentCommand.push(line);

    // Process the line to update state
    let iLine = 0;
    while (iLine < line.length) {
      const ch = line[iLine];
      
      if (escaping) {
        escaping = false;
        iLine++;
        continue;
      }
      
      if (ch === '\\' && (inSingle || inDouble)) {
        escaping = true;
        iLine++;
        continue;
      }
      
      // Toggle quote states (mutually exclusive)
      if (ch === "'" && !inDouble) {
        inSingle = !inSingle;
        iLine++;
        continue;
      }
      if (ch === '"' && !inSingle) {
        inDouble = !inDouble;
        iLine++;
        continue;
      }
      
      // Heredoc detection (only when not inside quotes and not already in heredoc)
      if (heredocStack.length === 0 && !inSingle && !inDouble && 
          ch === '<' && line[iLine + 1] === '<' && line[iLine + 2] !== '<') {
        
        const rest = line.substring(iLine + 2);
        const match = rest.match(/^-?\s*['"]?([a-zA-Z_][a-zA-Z0-9_]*)(?:['"]?)?/);
        
        if (match) {
          let delimiter = match[1];
          // Handle quoted delimiters
          const afterMatch = rest.substring(match[0].length);
          if (afterMatch.startsWith('"') || afterMatch.startsWith("'")) {
            // The delimiter was quoted, preserve the exact delimiter
            delimiter = afterMatch[0] === '"' ? `"${delimiter}"` : `'${delimiter}'`;
          }
          
          heredocStack.push({
            delimiter: delimiter,
            indentAware: rest.startsWith("-")
          });
          // Skip over the heredoc operator for state tracking
          iLine += 2 + match[0].length;
          continue;
        }
      }
      
      iLine++;
    }
    
    // Check for heredoc termination on this line (after processing content)
    const trimmed = line.trim();
    let terminatedHeredoc = false;
    
    while (heredocStack.length > 0 && !terminatedHeredoc) {
      const top = heredocStack[heredocStack.length - 1];
      let isTerminator = false;
      
      if (top.indentAware) {
        // For <<-, strip leading tabs
        const withoutLeadingTabs = line.replace(/^\t+/, "");
        if (withoutLeadingTabs === top.delimiter || 
            (top.delimiter.startsWith('"') || top.delimiter.startsWith("'")) && 
            withoutLeadingTabs === top.delimiter.slice(1, -1)) {
          isTerminator = true;
        }
      } else {
        if (trimmed === top.delimiter) {
          isTerminator = true;
        } else if ((top.delimiter.startsWith('"') || top.delimiter.startsWith("'")) && 
                   trimmed === top.delimiter.slice(1, -1)) {
          isTerminator = true;
        }
      }
      
      if (isTerminator) {
        heredocStack.pop();
        terminatedHeredoc = true;
        // When exiting a heredoc, reset quote state
        inSingle = false;
        inDouble = false;
      } else {
        break;
      }
    }
    
    // Check for line continuation (backslash at end of line, not escaped)
    const hasContinuation = /(?<!\\)\\$/.test(line);
    
    // Check if this command is complete
    const isComplete = heredocStack.length === 0 && !inSingle && !inDouble && !hasContinuation;
    
    if (isComplete && currentCommand.length > 0) {
      result.push(currentCommand.join("\n"));
      currentCommand = [];
      // Reset quote states (should already be reset, but just to be safe)
      inSingle = false;
      inDouble = false;
    }
  }

  // Handle any incomplete command at the end
  if (currentCommand.length > 0) {
    result.push(currentCommand.join("\n"));
  }

  return result;
}