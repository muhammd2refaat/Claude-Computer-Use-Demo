"""Gemini API wrapper that translates between Anthropic's tool format and Google's native API.

When GEMINI_API_KEY is detected, the session manager routes through this module
instead of the Anthropic SDK.  We translate:
  - Anthropic messages → Gemini contents
  - Anthropic tool_result blocks → Gemini functionResponse parts
  - Gemini functionCall responses → Anthropic-style tool_use blocks
"""

import json
import logging
import httpx

logger = logging.getLogger(__name__)

# ─── Tool definitions (mirroring Anthropic's computer_use tools) ────────────

GEMINI_TOOLS = [
    {
        "name": "computer",
        "description": (
            "Use a mouse and keyboard to interact with a computer screen. "
            "Actions: key, type, mouse_move, left_click, left_click_drag, "
            "right_click, middle_click, double_click, screenshot, cursor_position, "
            "triple_click, scroll. "
            "For screenshot, call with action='screenshot' and no other params."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "The action to perform.",
                },
                "coordinate": {
                    "type": "ARRAY",
                    "items": {"type": "INTEGER"},
                    "description": "[x, y] pixel coordinates for mouse actions.",
                },
                "text": {
                    "type": "STRING",
                    "description": "Text to type or key combo to press.",
                },
            },
            "required": ["action"],
        },
    },
    {
        "name": "bash",
        "description": (
            "Run commands in a bash shell. Use this for file operations, "
            "launching GUI apps (with DISPLAY variable), installing packages, etc."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "command": {
                    "type": "STRING",
                    "description": "The bash command to run.",
                },
                "restart": {
                    "type": "BOOLEAN",
                    "description": "Whether to restart the shell.",
                },
            },
            "required": ["command"],
        },
    },
    {
        "name": "str_replace_editor",
        "description": "Create and edit files.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "command": {"type": "STRING"},
                "path": {"type": "STRING"},
                "file_text": {"type": "STRING"},
                "insert_line": {"type": "INTEGER"},
                "old_str": {"type": "STRING"},
                "new_str": {"type": "STRING"},
                "view_range": {
                    "type": "ARRAY",
                    "items": {"type": "INTEGER"},
                },
            },
            "required": ["command", "path"],
        },
    },
]


# ─── Helpers ────────────────────────────────────────────────────────────────

def _extract_tool_name_from_id(tool_use_id: str) -> str:
    """Extract tool name from our synthetic IDs like 'call_bash'."""
    if tool_use_id.startswith("call_"):
        return tool_use_id[5:]
    return "computer"  # safe fallback


def _extract_text_from_content(content) -> str:
    """Safely extract a text summary from Anthropic tool_result content."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    texts.append(item.get("text", ""))
                elif item.get("type") == "image":
                    texts.append("[screenshot taken]")
            elif isinstance(item, str):
                texts.append(item)
        return "\n".join(texts) if texts else "Tool completed successfully."
    return "Tool completed successfully."


def _convert_messages_to_gemini(messages: list) -> list:
    """Convert Anthropic message list to Gemini contents format."""
    contents = []

    for msg in messages:
        role = "user" if msg["role"] == "user" else "model"
        parts = []
        msg_content = msg.get("content", [])

        # Handle string content directly
        if isinstance(msg_content, str):
            parts.append({"text": msg_content})
        elif isinstance(msg_content, list):
            for block in msg_content:
                if isinstance(block, str):
                    parts.append({"text": block})
                elif isinstance(block, dict):
                    btype = block.get("type", "")

                    if btype == "text":
                        text = block.get("text", "")
                        if text:
                            parts.append({"text": text})

                    elif btype == "image":
                        source = block.get("source", {})
                        parts.append({
                            "inlineData": {
                                "mimeType": source.get("media_type", "image/png"),
                                "data": source.get("data", ""),
                            }
                        })

                    elif btype == "tool_use":
                        parts.append({
                            "functionCall": {
                                "name": block["name"],
                                "args": block.get("input", {}),
                            }
                        })

                    elif btype == "tool_result":
                        tool_name = _extract_tool_name_from_id(
                            block.get("tool_use_id", "call_computer")
                        )
                        result_text = _extract_text_from_content(
                            block.get("content", [])
                        )
                        parts.append({
                            "functionResponse": {
                                "name": tool_name,
                                "response": {"result": result_text},
                            }
                        })

        if not parts:
            parts.append({"text": "(empty)"})

        # Gemini requires alternating user/model roles; merge consecutive same-role
        if contents and contents[-1]["role"] == role:
            contents[-1]["parts"].extend(parts)
        else:
            contents.append({"role": role, "parts": parts})

    return contents


# ─── Main entry point ───────────────────────────────────────────────────────

async def run_gemini_sampling(
    messages: list,
    tool_collection,
    api_key: str,
    system=None,
) -> list:
    """Make a single Gemini API call and return Anthropic-style response blocks."""

    contents = _convert_messages_to_gemini(messages)

    payload: dict = {
        "contents": contents,
        "tools": [{"functionDeclarations": GEMINI_TOOLS}],
        "generationConfig": {
            "temperature": 0.2,
        },
    }

    # Inject system instruction
    if system:
        sys_text = system.get("text", "") if isinstance(system, dict) else str(system)
        gemini_nudge = (
            "\n\nCRITICAL INSTRUCTIONS: You are an autonomous computer-use agent. "
            "You MUST use the provided tools to complete the user's task. "
            "After launching a GUI app with bash, ALWAYS call the 'computer' tool "
            "with action='screenshot' to see the screen. Then interact with what you see "
            "using mouse clicks and keyboard. "
            "NEVER say you cannot do something - you have full access to a Linux desktop. "
            "NEVER stop until the task is truly complete and you have visually confirmed the result. "
            "Chain multiple tool calls: bash → screenshot → click → type → screenshot → verify."
        )
        payload["systemInstruction"] = {
            "parts": [{"text": sys_text + gemini_nudge}]
        }

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.5-flash:generateContent?key={api_key}"
    )

    logger.info("Calling Gemini API...")

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
        )

    if response.status_code != 200:
        error_text = response.text
        logger.error(f"Gemini API error {response.status_code}: {error_text}")
        return [{"type": "text", "text": f"Error: Gemini API returned {response.status_code}: {error_text}"}]

    res = response.json()

    # Parse candidates
    candidates = res.get("candidates", [])
    if not candidates:
        logger.warning(f"Gemini returned no candidates: {res}")
        return [{"type": "text", "text": "Error: Gemini returned no candidates."}]

    cand_content = candidates[0].get("content", {})
    response_blocks = []

    for part in cand_content.get("parts", []):
        if "text" in part:
            response_blocks.append({"type": "text", "text": part["text"]})

        if "functionCall" in part:
            call = part["functionCall"]
            name = call.get("name", "computer")
            response_blocks.append({
                "type": "tool_use",
                "id": f"call_{name}",
                "name": name,
                "input": call.get("args", {}),
            })

    if not response_blocks:
        logger.warning("Gemini returned empty parts, adding fallback text")
        response_blocks.append({"type": "text", "text": "I'll take a screenshot to see the current state."})
        response_blocks.append({
            "type": "tool_use",
            "id": "call_computer",
            "name": "computer",
            "input": {"action": "screenshot"},
        })

    logger.info(f"Gemini returned {len(response_blocks)} blocks: {[b.get('type') for b in response_blocks]}")
    return response_blocks
