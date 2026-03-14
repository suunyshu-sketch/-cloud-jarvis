from backend.services import memory_service

async def evaluate(user_text: str, reply: str, person: str, intent: str) -> float:
    """Non-blocking auto-evaluator. Runs after response is sent."""
    try:
        score = 0.5  # baseline

        # Length appropriateness
        words = len(reply.split())
        if intent == "casual_chat" and words <= 60:
            score += 0.2
        elif intent == "information_query" and words >= 50:
            score += 0.2
        elif intent == "code_request" and "```" in reply:
            score += 0.3

        # Language consistency
        from backend.utils.language import detect_language
        user_lang = detect_language(user_text)
        reply_lang = detect_language(reply)
        if user_lang == reply_lang:
            score += 0.1

        # Did not contain error markers
        error_markers = ["i cannot", "i'm unable", "i don't know", "as an ai", "i apologize"]
        if not any(m in reply.lower() for m in error_markers):
            score += 0.1

        # Emotional support quality
        if intent == "emotional_support":
            support_words = ["understand","here for you","must be","that sounds","tough","difficult"]
            if any(w in reply.lower() for w in support_words):
                score += 0.2

        score = min(1.0, score)

        # Save auto-feedback if score is notably high or low
        if score >= 0.8:
            await memory_service.save_feedback(person, user_text, reply, "positive", "auto")
        elif score <= 0.3:
            await memory_service.save_feedback(person, user_text, reply, "negative", "auto")

        return score
    except Exception as e:
        print(f"evaluator error: {e}")
        return 0.5
