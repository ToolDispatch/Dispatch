import json
import os
import anthropic

SYSTEM_PROMPT = """You are a task classifier for a developer assistant tool.
Given the last few messages in a conversation and the current working directory,
determine:
1. Whether the developer has shifted to a meaningfully different task or topic
2. What type of task it now is
3. Your confidence level

Respond with ONLY valid JSON in this exact format:
{"shift": true/false, "task_type": "<type>", "confidence": 0.0-1.0}

For task_type, return the most specific, descriptive label you can — it will be used to search
a skills registry, so precision matters. Use the technology, framework, or domain name directly.
Examples: flutter, react, nextjs, python, docker, aws, langchain, supabase, prisma, graphql,
postgres, redis, stripe, github-actions, debugging, testing, planning, security, devops, or
any other relevant technology. Use lowercase-hyphenated format. Prefer specific over generic.

A "shift" means the developer is starting something clearly different from their last task.
Continuing, refining, or asking follow-up questions about the same task is NOT a shift.
"""


def extract_recent_messages(transcript: list, n: int = 3) -> list:
    """Extract the last n user messages from a transcript."""
    user_messages = []
    for entry in transcript:
        if entry.get("role") != "user":
            continue
        content = entry.get("content", "")
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
    return word_count < 6


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

        return json.loads(response.content[0].text)

    except Exception:
        return {"shift": False, "task_type": last_task_type or "general", "confidence": 0.0}


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

    if not messages or should_skip(messages[-1]):
        print(json.dumps({"shift": False, "task_type": args.last_task_type or "general", "confidence": 0.0}))
        sys.exit(0)

    result = classify_topic_shift(messages, args.cwd, args.last_task_type, api_key=api_key)
    print(json.dumps(result))
