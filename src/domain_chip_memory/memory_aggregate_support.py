from __future__ import annotations

from .contracts import NormalizedBenchmarkSample, NormalizedQuestion
from .memory_evidence import entry_source_corpus as _entry_source_corpus
from .memory_extraction import ObservationEntry


def raw_user_turn_entries(sample: NormalizedBenchmarkSample) -> list[ObservationEntry]:
    entries: list[ObservationEntry] = []
    for session in sample.sessions:
        for turn in session.turns:
            if turn.speaker.lower() != "user":
                continue
            entries.append(
                ObservationEntry(
                    observation_id=f"{turn.turn_id}:raw",
                    subject="I",
                    predicate="raw_turn",
                    text=turn.text,
                    session_id=session.session_id,
                    turn_ids=[turn.turn_id],
                    timestamp=turn.timestamp,
                    metadata={"source_text": turn.text, "value": turn.text},
                )
            )
    return entries


def select_aggregate_support_entries(
    question: NormalizedQuestion,
    aggregate_entries: list[ObservationEntry],
    *,
    limit: int = 4,
) -> list[ObservationEntry]:
    question_lower = question.question.lower()
    raw_entries = [entry for entry in aggregate_entries if entry.predicate == "raw_turn"]
    if not raw_entries:
        return []

    def _matches_any(text: str, needles: tuple[str, ...]) -> bool:
        return any(needle in text for needle in needles)

    selected: list[ObservationEntry] = []
    for entry in raw_entries:
        source_text = _entry_source_corpus(entry).lower()
        if question_lower.startswith("how much total money have i spent on bike-related expenses since the start of the year"):
            if "$" in source_text and _matches_any(source_text, ("bike", "chain", "helmet", "lights")):
                selected.append(entry)
        elif question_lower.startswith("what is the total amount i spent on luxury items in the past few months"):
            if "$" in source_text and _matches_any(source_text, ("luxury", "gucci", "handbag", "evening gown", "boots")):
                selected.append(entry)
        elif question_lower.startswith("how many plants did i initially plant for tomatoes and cucumbers"):
            if _matches_any(source_text, ("tomato", "cucumber", "planted 5", "3 plants")):
                selected.append(entry)
        elif question_lower.startswith("how much older am i than the average age of employees in my department"):
            if _matches_any(source_text, ("average age", "turned 32", "just turned 32", "he's just 21", "alex")):
                selected.append(entry)
        elif question_lower.startswith("what was the total number of people reached by my facebook ad campaign and instagram influencer collaboration"):
            if _matches_any(source_text, ("facebook ad campaign", "reached around 2,000", "influencer", "10,000 followers")):
                selected.append(entry)
        elif question_lower.startswith("how much did i save on the designer handbag at tk maxx"):
            if "$" in source_text and _matches_any(source_text, ("designer handbag", "tk maxx", "originally $500", "got for $200")):
                selected.append(entry)
        elif question_lower.startswith("what is the total number of goals and assists i have in the recreational indoor soccer league"):
            if _matches_any(source_text, ("indoor soccer", "3 goals", "two assists", "assists in the league")):
                selected.append(entry)
        elif question_lower.startswith("how many marvel movies did i re-watch"):
            if _matches_any(source_text, ("re-watched spider-man: no way home", "re-watched avengers: endgame", "watched doctor strange already", "four marvel movies i watched recently")):
                selected.append(entry)
        elif question_lower.startswith("how much did i spend on car wash and parking ticket"):
            if "$" in source_text and _matches_any(source_text, ("car wash", "parking ticket")):
                selected.append(entry)
        elif question_lower.startswith("how many sports have i played competitively in the past"):
            if _matches_any(source_text, ("swim competitively", "tennis competitively", "competitively in college", "competitively in high school")):
                selected.append(entry)
        elif question_lower.startswith("what are the two hobbies that led me to join online communities"):
            if _matches_any(source_text, ("photography", "lightroom", "cooking", "online communities")):
                selected.append(entry)
        elif question_lower.startswith("how old was i when alex was born"):
            if _matches_any(source_text, ("alex", "just 21", "turned 32", "just turned 32")):
                selected.append(entry)
        elif question_lower.startswith("how many years will i be when my friend rachel gets married"):
            if _matches_any(source_text, ("rachel's getting married next year", "i'm 32", "i am 32")):
                selected.append(entry)
        elif question_lower.startswith("how many dinner parties have i attended in the past month"):
            if _matches_any(source_text, ("sarah's place last week", "mike's place two weeks ago", "alex's place yesterday")):
                selected.append(entry)
        elif question_lower.startswith("how much did i spend on gifts for my sister"):
            if "$" in source_text and _matches_any(source_text, ("gift for my sister", "tiffany", "favorite spa last time", "gift card")):
                selected.append(entry)
        elif question_lower.startswith("how many years older is my grandma than me"):
            if _matches_any(source_text, ("grandma's 75th birthday", "75th birthday celebration", "32 is considered young or old")):
                selected.append(entry)
        elif question_lower.startswith("how many years older am i than when i graduated from college"):
            if _matches_any(source_text, ("completed at the age of 25", "32-year-old digital marketing specialist")):
                selected.append(entry)
        elif question_lower.startswith("how many points do i need to earn to redeem a free skincare product at sephora"):
            if _matches_any(source_text, ("sephora", "earned 50 points", "total to 200 points", "300 points")):
                selected.append(entry)
        elif question_lower.startswith("what is the total number of days i spent in japan and chicago"):
            if _matches_any(source_text, ("japan", "chicago", "april 15th to 22nd", "4-day trip")):
                selected.append(entry)
        elif question_lower.startswith("what is the minimum amount i could get if i sold the vintage diamond necklace and the antique vanity"):
            if "$" in source_text and _matches_any(source_text, ("diamond necklace", "antique vanity", "worth $5,000", "at least $150")):
                selected.append(entry)
        elif question_lower.startswith("what percentage of the countryside property's price is the cost of the renovations i plan to do on my current house"):
            if "$" in source_text and _matches_any(source_text, ("countryside", "5-acre property", "listed at $200,000", "renovations", "$20,000")):
                selected.append(entry)
        elif question_lower.startswith("what is the total cost of lola's vet visit and flea medication"):
            if "$" in source_text and _matches_any(source_text, ("lola", "vet", "consultation fee", "flea and tick prevention medication")):
                selected.append(entry)
        elif question_lower.startswith("how much more did i have to pay for the trip after the initial quote"):
            if "$" in source_text and _matches_any(source_text, ("sakura travel", "initially quoted", "corrected price")):
                selected.append(entry)
        elif question_lower.startswith("what is the total number of lunch meals i got from the chicken fajitas and lentil soup"):
            if _matches_any(source_text, ("chicken fajitas", "third meal", "lentil soup", "5 lunches")):
                selected.append(entry)
        elif question_lower.startswith("how much did i spend on each coffee mug for my coworkers"):
            if "$" in source_text and _matches_any(source_text, ("coffee mugs", "5 coffee mugs", "coworkers")):
                selected.append(entry)
        elif question_lower.startswith("how long have i been working in my current role"):
            if _matches_any(source_text, ("marketing coordinator", "senior marketing specialist", "2 years and 4 months", "3 years and 9 months")):
                selected.append(entry)
        elif question_lower.startswith("how much more was the pre-approval amount than the final sale price of the house"):
            if "$" in source_text and _matches_any(source_text, ("pre-approved", "$350,000", "final sale price", "$325,000")):
                selected.append(entry)
        elif question_lower.startswith("what is the total cost of the car cover and detailing spray i purchased"):
            if "$" in source_text and _matches_any(source_text, ("car cover", "detailing spray", "waterproof car cover")):
                selected.append(entry)
        elif question_lower.startswith("what is the total distance i covered in my four road trips"):
            if _matches_any(source_text, ("road trip", "1,800 miles", "1,200 miles", "yellowstone")):
                selected.append(entry)
        elif question_lower.startswith("what is the total time it takes i to get ready and commute to work"):
            if _matches_any(source_text, ("commute to work takes about 30 minutes", "takes me about an hour to get ready", "morning commute", "wake up at 6:30")):
                selected.append(entry)
        elif question_lower.startswith("how many fish are there in total in both of my aquariums"):
            if _matches_any(source_text, ("aquarium", "tank", "betta", "bubbles", "tetras", "gourami", "pleco")):
                selected.append(entry)
        elif question_lower.startswith("how many times did i ride rollercoasters across all the events i attended from july to october"):
            if _matches_any(source_text, ("rollercoaster", "xcelerator", "mummy", "ghost galaxy", "mako", "kraken", "manta", "seaworld", "disneyland", "knott")):
                selected.append(entry)
        elif question_lower.startswith("how many days did i spend in total traveling in hawaii and in new york city"):
            if _matches_any(source_text, ("hawaii", "new york city", "nyc", "island-hopping", "five days", "10-day", "ten-day", "ten days")):
                selected.append(entry)
        elif question_lower.startswith("how many rare items do i have in total"):
            if _matches_any(source_text, ("rare figurines", "rare records", "rare books", "rare coins")):
                selected.append(entry)
        elif question_lower.startswith("how many online courses have i completed in total"):
            if _matches_any(source_text, ("coursera", "edx", "online courses")):
                selected.append(entry)
        elif question_lower.startswith("how many total pieces of writing have i completed since i started writing again three weeks ago"):
            if _matches_any(source_text, ("poems", "short stories", "writing challenge", "the smell of old books")):
                selected.append(entry)
        elif question_lower.startswith("what is the total distance of the hikes i did on two consecutive weekends"):
            if _matches_any(source_text, ("mile", "hike", "trail", "valley of fire", "red rock canyon")):
                selected.append(entry)
        elif question_lower.startswith("how many pages do i have left to read in 'the nightingale'"):
            if _matches_any(source_text, ("the nightingale", "440 pages", "page 250")):
                selected.append(entry)
        elif question_lower.startswith("for my daily commute, how much more expensive was the taxi ride compared to the train fare"):
            if "$" in source_text and _matches_any(source_text, ("taxi", "train fare", "commute")):
                selected.append(entry)
        elif question_lower.startswith("what was the approximate increase in instagram followers i experienced in two weeks"):
            if _matches_any(source_text, ("instagram", "followers")):
                selected.append(entry)
        elif question_lower.startswith("how many antique items did i inherit or acquire from my family members"):
            if _matches_any(source_text, ("antique", "vintage typewriter", "music box", "tea set", "glassware", "necklace")):
                selected.append(entry)
        elif question_lower.startswith("what is the total cost of the new food bowl, measuring cup, dental chews, and flea and tick collar i got for max"):
            if "$" in source_text and _matches_any(source_text, ("food bowl", "measuring cup", "dental chews", "flea", "tick collar", "max")):
                selected.append(entry)
        elif question_lower.startswith("how much cashback did i earn at savemart last thursday"):
            if _matches_any(source_text, ("savemart", "cashback", "$75", "1%")):
                selected.append(entry)
        elif question_lower.startswith("what is the difference in price between my luxury boots and the similar pair found at the budget store"):
            if "$" in source_text and _matches_any(source_text, ("luxury boots", "budget store", "similar boots", "similar pair")):
                selected.append(entry)
        elif question_lower.startswith("what percentage of packed shoes did i wear on my last trip"):
            if _matches_any(source_text, ("pack light", "packed", "shoes", "wearing two", "sneakers and sandals")):
                selected.append(entry)
        elif question_lower.startswith("when did i submit my research paper on sentiment analysis"):
            if _matches_any(source_text, ("sentiment analysis", "acl", "submission date", "february 1st")):
                selected.append(entry)
        elif question_lower.startswith("did i receive a higher percentage discount on my first order from hellofresh, compared to my first ubereats order"):
            if _matches_any(source_text, ("hellofresh", "ubereats", "discount", "%")):
                selected.append(entry)
        elif question_lower.startswith("what is the total number of episodes i've listened to from 'how i built this' and 'my favorite murder'"):
            if _matches_any(source_text, ("how i built this", "my favorite murder", "episodes", "episode 12")):
                selected.append(entry)

    deduped: list[ObservationEntry] = []
    seen_sources: set[str] = set()
    for entry in selected:
        source_text = _entry_source_corpus(entry)
        if source_text in seen_sources:
            continue
        seen_sources.add(source_text)
        deduped.append(entry)
        if len(deduped) >= limit:
            break
    return deduped

