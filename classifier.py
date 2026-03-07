import json
import os
import anthropic

VALID_MODES = {
    "discovering", "designing", "building", "fixing",
    "validating", "shipping", "maintaining"
}

SYSTEM_PROMPT = """You are an action-mode classifier for a developer tool that surfaces the right tools at the right time.

Given the last few messages in a conversation and the current working directory, determine:
1. Whether the developer has shifted to a meaningfully different action mode OR domain
2. What domain they are working in (the technology/framework/subject)
3. What action mode they are now in
4. Your confidence level

ACTION MODES (pick exactly one):
- discovering  — researching, learning, exploring options, asking "what is" or "how does"
- designing    — planning, architecting, deciding approach, brainstorming before building
- building     — writing new code, creating, implementing, adding features
- fixing       — debugging, diagnosing errors, tracing failures, something is broken
- validating   — testing, reviewing, verifying correctness, checking work
- shipping     — deploying, releasing, publishing, going live, CI/CD
- maintaining  — refactoring, improving, cleaning up, restructuring existing code

A "shift" means the developer has moved to a different action mode OR a different domain
compared to their last task. Both count as shifts. Continuing, refining, or asking
follow-up questions about the same task in the same mode is NOT a shift.

Use natural developer language to infer mode — not just keywords.
Examples:
- "this blows up with a null" → fixing
- "let me sanity check this" → validating
- "it works but feels gross" → maintaining
- "how should I structure this?" → designing
- "write the auth middleware" → building

Respond with ONLY valid JSON:
{"shift": true/false, "domain": "<technology>", "mode": "<mode>", "task_type": "<domain>-<mode>", "confidence": 0.0-1.0}

For domain, use the most specific label: flutter, react, supabase, dispatch, postgres, stripe, etc.
Use lowercase-hyphenated format. If no clear domain, use "general"."""


def extract_recent_messages(transcript: list, n: int = 3) -> list:
    """Extract the last n user messages from a transcript."""
    user_messages = []
    for entry in transcript:
        if entry.get("isMeta"):  # skip CC system messages (skill content, tool responses)
            continue
        msg = entry.get("message", entry)  # CC transcript wraps content inside 'message'
        if msg.get("role") != "user":
            continue
        content = msg.get("content", "")
        if isinstance(content, str) and content.startswith("["):  # skip serialized tool results
            continue
        if isinstance(content, list):
            # Extract text from content blocks
            text_parts = [block.get("text", "") for block in content if isinstance(block, dict) and block.get("type") == "text"]
            content = " ".join(text_parts)
        if content:
            user_messages.append(content)
    return user_messages[-n:]


def should_skip(message: str) -> bool:
    """Return True if we should skip classification (short follow-up)."""
    word_count = len(message.strip().split())
    return word_count < 4


def classify_topic_shift(messages: list, cwd: str, last_task_type: str = None, api_key: str = None) -> dict:
    """
    Call Haiku to classify whether a topic shift has occurred.
    Returns: {"shift": bool, "task_type": str, "confidence": float}
    """
    try:
        client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))

        user_content = f"""Current directory: {cwd}
Last task type: {last_task_type or 'unknown'}

Recent messages:
{chr(10).join(f'- {m}' for m in messages)}

Has the developer shifted to a new task?"""

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}]
        )

        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text.strip())

    except Exception:
        return {"shift": False, "domain": "general", "mode": "building", "task_type": "general", "confidence": 0.0}


if __name__ == "__main__":
    import argparse
    import sys

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print(json.dumps({"error": "ANTHROPIC_API_KEY not set", "shift": False, "task_type": "general", "confidence": 0.0}))
        sys.exit(0)  # exit 0 so hook doesn't block Claude

    parser = argparse.ArgumentParser()
    parser.add_argument("--transcript", default="")
    parser.add_argument("--cwd", default="")
    parser.add_argument("--last-task-type", default=None)
    parser.add_argument("--prompt", default="")  # current message from hook stdin
    args = parser.parse_args()

    transcript = []
    if args.transcript and os.path.exists(args.transcript):
        try:
            with open(args.transcript) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            transcript.append(json.loads(line))
                        except Exception:
                            pass
        except Exception:
            pass

    messages = extract_recent_messages(transcript, n=3)

    # Append the current prompt — transcript doesn't contain it yet
    # (CC writes the current message to transcript AFTER the hook fires)
    if args.prompt:
        messages.append(args.prompt)
        messages = messages[-3:]

    if not messages or should_skip(messages[-1]):
        print(json.dumps({"shift": False, "task_type": args.last_task_type or "general", "confidence": 0.0}))
        sys.exit(0)

    result = classify_topic_shift(messages, args.cwd, args.last_task_type, api_key=api_key)
    print(json.dumps(result))
