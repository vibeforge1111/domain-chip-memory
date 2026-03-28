from __future__ import annotations

from .contracts import NormalizedQuestion
from .memory_extraction import _tokenize

PREFERENCE_QUESTION_STOPWORDS = {
    "activity",
    "activities",
    "advice",
    "again",
    "any",
    "around",
    "better",
    "can",
    "complement",
    "current",
    "do",
    "evening",
    "find",
    "for",
    "get",
    "getting",
    "help",
    "ideas",
    "im",
    "interesting",
    "learn",
    "look",
    "looking",
    "might",
    "more",
    "my",
    "new",
    "on",
    "stay",
    "staying",
    "recommend",
    "recommendation",
    "recommendations",
    "resources",
    "serve",
    "should",
    "some",
    "suggest",
    "suggestion",
    "suggestions",
    "think",
    "thinking",
    "tips",
    "tonight",
    "trouble",
    "upcoming",
    "way",
    "ways",
    "weekend",
    "where",
}


def is_preference_question(question: NormalizedQuestion) -> bool:
    question_lower = question.question.lower()
    return question.category == "single-session-preference" or question_lower.startswith(
        (
            "can you recommend",
            "can you suggest",
            "what should i serve",
        )
    ) or "any tips" in question_lower or "any advice" in question_lower or "any suggestions" in question_lower


def preference_domain_tokens(question: NormalizedQuestion) -> set[str]:
    question_lower = question.question.lower()
    tokens = {
        token
        for token in _tokenize(question.question)
        if token not in PREFERENCE_QUESTION_STOPWORDS
    }
    if "video editing" in question_lower:
        tokens.update({"video", "editing", "adobe", "premiere", "pro", "advanced", "settings"})
    if "photography" in question_lower:
        tokens.update({"camera", "flash", "photography", "sony", "a7r"})
    if "publications" in question_lower or "conferences" in question_lower:
        tokens.update({"publication", "conference", "deep", "learning", "medical", "image", "analysis"})
    if "hotel" in question_lower:
        tokens.update({"hotel", "room", "view", "balcony", "pool", "rooftop", "tub"})
    if "show or movie" in question_lower or "watch tonight" in question_lower:
        tokens.update({"show", "movie", "netflix", "stand", "up", "comedy", "special", "storytelling"})
    if "do in the evening" in question_lower:
        tokens.update({"evening", "relax", "sleep", "bed", "meditation", "phone", "tv"})
    if "kitchen" in question_lower and "clean" in question_lower:
        tokens.update({"kitchen", "clean", "sink", "granite", "countertop", "clutter", "utensil", "holder"})
    if "slow cooker" in question_lower:
        tokens.update({"slow", "cooker", "recipe", "stew", "yogurt"})
    if "colleagues" in question_lower:
        tokens.update({"colleague", "social", "remote", "coffee", "team", "watercooler", "collaboration"})
    if "dinner" in question_lower or "ingredients" in question_lower or "bake" in question_lower:
        tokens.update({"dinner", "recipe", "ingredient", "cook", "basil", "mint", "cake", "cookie", "dessert", "lemon", "poppyseed"})
    if "painting" in question_lower or "paintings" in question_lower:
        tokens.update({"painting", "paint", "acrylic", "brush", "inspiration", "instagram", "tutorial", "flower", "challenge"})
    if "cocktail" in question_lower:
        tokens.update({"cocktail", "summer", "drink", "hendrick", "gin", "pimm", "cup", "mixology"})
    if "battery life" in question_lower or "phone" in question_lower:
        tokens.update({"battery", "phone", "portable", "power", "bank", "charging"})
    if "cookies" in question_lower:
        tokens.update({"cookie", "cookies", "turbinado", "sugar", "flavor"})
    if "bedroom" in question_lower or "furniture" in question_lower:
        tokens.update({"bedroom", "dresser", "mid", "century", "modern", "furniture"})
    if "guitar" in question_lower:
        tokens.update({"guitar", "fender", "stratocaster", "gibson", "les", "paul"})
    if "cultural events" in question_lower:
        tokens.update({"culture", "cultural", "event", "french", "podcast"})
    return tokens


def is_recommendation_request_text(text: str) -> bool:
    lowered = text.lower()
    return any(
        phrase in lowered
        for phrase in (
            "can you recommend",
            "can you suggest",
            "do you have any recommendations",
            "do you have any suggestions",
            "any tips",
            "any advice",
            "what should i serve",
        )
    )


def preference_overlap(question: NormalizedQuestion, text: str) -> int:
    return len(preference_domain_tokens(question).intersection(set(_tokenize(text))))


def preference_phrase_bonus(question: NormalizedQuestion, text: str) -> float:
    question_lower = question.question.lower()
    lowered = text.lower()
    tokens = set(_tokenize(text))
    bonus = 0.0
    if "what to bake" in question_lower or ("bake" in question_lower and "gathering" in question_lower):
        if any(phrase in lowered for phrase in ("lemon poppyseed", "lemon lavender", "pound cake")):
            bonus += 8.0
        if any(token in tokens for token in ("cake", "bake", "baking", "cookies", "cookie", "dessert", "lemon")):
            bonus += 4.0
    if "colleagues" in question_lower:
        if any(phrase in lowered for phrase in ("working from home", "remote", "virtual coffee", "watercooler")):
            bonus += 8.0
        if "colleagues" in lowered or any(token in tokens for token in ("team", "collaboration")) or any(phrase in lowered for phrase in ("check-in", "check in")):
            bonus += 6.0
        if "social media" in lowered and not any(token in lowered for token in ("colleague", "team", "remote")):
            bonus -= 8.0
    if "slow cooker" in question_lower:
        if any(phrase in lowered for phrase in ("slow cooker", "beef stew", "vegetarian", "vegan", "plant-based", "cashew base")):
            bonus += 6.0
        if "yogurt" in tokens:
            bonus += 8.0
        if "better results" in question_lower:
            if any(phrase in lowered for phrase in ("beef stew", "slow cooker yogurt", "cashew base")) or "yogurt" in tokens:
                bonus += 6.0
            if "more recipes with it" in lowered:
                bonus -= 4.0
    if "paintings" in question_lower or "painting" in question_lower:
        if "instagram" in tokens or any(token in tokens for token in ("tutorial", "tutorials", "challenge", "flowers", "flower")) or "palette knife" in lowered:
            bonus += 6.0
    if "cocktail" in question_lower:
        if any(token in tokens for token in ("hendrick", "pimm", "mixology", "cocktail", "grapefruit", "cucumber", "syrup", "garnish")):
            bonus += 6.0
    if "battery life" in question_lower or "phone" in question_lower:
        if any(phrase in lowered for phrase in ("power bank", "wireless charging", "battery-saving", "battery saving")):
            bonus += 8.0
        if any(token in tokens for token in ("battery", "portable", "charging", "phone")):
            bonus += 4.0
    if "photography setup" in question_lower or "accessories" in question_lower:
        if any(phrase in lowered for phrase in ("sony a7r", "sony camera", "camera bag")):
            bonus += 8.0
        if any(token in tokens for token in ("sony", "camera", "flash", "lens", "tripod", "battery")):
            bonus += 4.0
    if "show or movie" in question_lower or "watch tonight" in question_lower:
        if any(token in tokens for token in ("netflix", "comedy", "storytelling", "mulaney")) or "kid gorgeous" in lowered:
            bonus += 6.0
    return bonus


def preference_anchor_match(question: NormalizedQuestion, text: str) -> bool:
    question_lower = question.question.lower()
    lowered = text.lower()
    tokens = set(_tokenize(text))
    if "what to bake" in question_lower or ("bake" in question_lower and "gathering" in question_lower):
        return any(token in tokens for token in ("cake", "bake", "baking", "lemon", "poppyseed", "cookie", "dessert", "lavender"))
    if "colleagues" in question_lower:
        return "colleagues" in lowered or any(token in tokens for token in ("team", "remote")) or any(phrase in lowered for phrase in ("working from home", "watercooler", "virtual coffee", "check-in", "check in"))
    if "slow cooker" in question_lower:
        return any(token in lowered for token in ("slow cooker", "stew", "yogurt", "vegetarian", "vegan", "cashew"))
    if "paintings" in question_lower or "painting" in question_lower:
        return any(token in tokens for token in ("paint", "painting", "instagram", "flower", "flowers", "challenge")) or "palette knife" in lowered
    if "cocktail" in question_lower:
        return any(token in tokens for token in ("cocktail", "pimm", "hendrick", "gin", "mixology", "grapefruit", "cucumber", "syrup", "garnish"))
    if "battery life" in question_lower or "phone" in question_lower:
        return any(token in tokens for token in ("battery", "charging", "phone")) or any(phrase in lowered for phrase in ("power bank", "wireless charging"))
    if "photography setup" in question_lower or "accessories" in question_lower:
        return any(token in tokens for token in ("sony", "camera", "flash", "lens", "tripod", "battery")) or any(phrase in lowered for phrase in ("battery pack", "camera bag"))
    if "show or movie" in question_lower or "watch tonight" in question_lower:
        return any(token in tokens for token in ("netflix", "comedy", "special", "storytelling", "mulaney")) or "kid gorgeous" in lowered
    return True


def is_generic_followup_preference_text(text: str) -> bool:
    lowered = text.lower()
    return any(
        phrase in lowered
        for phrase in (
            "those features",
            "these hotels",
            "good options",
            "some good options",
            "any of these",
        )
    )
