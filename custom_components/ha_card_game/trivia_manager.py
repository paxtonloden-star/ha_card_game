from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
import re


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


_CURATED_TRIVIA_LIBRARY: dict[str, list[dict[str, Any]]] = {
    "history": [
        {"question": "Which civilization built Machu Picchu?", "correct_answer": "Inca", "accepted_answers": ["Inca", "The Inca"], "choices": ["Romans", "Inca", "Mongols", "Aztecs"], "explanation": "Machu Picchu was built by the Inca civilization in Peru.", "difficulty": "easy"},
        {"question": "Who was the first president of the United States?", "correct_answer": "George Washington", "accepted_answers": ["George Washington", "Washington"], "choices": ["George Washington", "Thomas Jefferson", "Abraham Lincoln", "John Adams"], "explanation": "George Washington served as the first U.S. president.", "difficulty": "easy"},
        {"question": "What wall fell in 1989, symbolizing the end of the Cold War in Europe?", "correct_answer": "Berlin Wall", "accepted_answers": ["Berlin Wall", "The Berlin Wall"], "choices": ["Great Wall", "Berlin Wall", "Hadrian's Wall", "Iron Curtain"], "explanation": "The Berlin Wall fell in 1989.", "difficulty": "medium"},
        {"question": "Which ship carried the Pilgrims to North America in 1620?", "correct_answer": "Mayflower", "accepted_answers": ["Mayflower", "The Mayflower"], "choices": ["Mayflower", "Santa Maria", "Titanic", "Endeavour"], "explanation": "The Pilgrims crossed the Atlantic on the Mayflower.", "difficulty": "easy"},
    ],
    "fun_facts": [
        {"question": "What animal can sleep standing up?", "correct_answer": "Horse", "accepted_answers": ["Horse", "Horses"], "choices": ["Horse", "Dolphin", "Bat", "Cat"], "explanation": "Horses can doze while standing by locking their legs.", "difficulty": "easy"},
        {"question": "What is the only food that never really spoils?", "correct_answer": "Honey", "accepted_answers": ["Honey"], "choices": ["Milk", "Honey", "Bread", "Rice"], "explanation": "Honey can remain edible for extremely long periods when sealed.", "difficulty": "easy"},
        {"question": "Which planet has a day longer than its year?", "correct_answer": "Venus", "accepted_answers": ["Venus"], "choices": ["Mars", "Venus", "Mercury", "Neptune"], "explanation": "Venus rotates very slowly, so a Venus day is longer than its year.", "difficulty": "medium"},
        {"question": "Which bird is known for mimicking human speech especially well?", "correct_answer": "Parrot", "accepted_answers": ["Parrot", "Parrots"], "choices": ["Parrot", "Robin", "Owl", "Penguin"], "explanation": "Many parrots can imitate human speech and sounds.", "difficulty": "easy"},
    ],
    "geography": [
        {"question": "Which continent is the Sahara Desert located on?", "correct_answer": "Africa", "accepted_answers": ["Africa"], "choices": ["Asia", "Africa", "Australia", "South America"], "explanation": "The Sahara Desert covers much of North Africa.", "difficulty": "easy"},
        {"question": "What is the capital city of Canada?", "correct_answer": "Ottawa", "accepted_answers": ["Ottawa"], "choices": ["Toronto", "Ottawa", "Vancouver", "Montreal"], "explanation": "Ottawa is Canada's capital city.", "difficulty": "easy"},
        {"question": "Mount Kilimanjaro is found in which country?", "correct_answer": "Tanzania", "accepted_answers": ["Tanzania"], "choices": ["Kenya", "Tanzania", "Ethiopia", "Uganda"], "explanation": "Kilimanjaro is in northeastern Tanzania.", "difficulty": "medium"},
        {"question": "Which U.S. state is made up of islands in the Pacific Ocean?", "correct_answer": "Hawaii", "accepted_answers": ["Hawaii"], "choices": ["Alaska", "California", "Hawaii", "Florida"], "explanation": "Hawaii is an island state in the Pacific.", "difficulty": "easy"},
    ],
    "movies": [
        {"question": "Which movie features a toy cowboy named Woody?", "correct_answer": "Toy Story", "accepted_answers": ["Toy Story"], "choices": ["Cars", "Frozen", "Toy Story", "Shrek"], "explanation": "Woody is one of the main characters in Toy Story.", "difficulty": "easy"},
        {"question": "Which movie series includes the wizard school Hogwarts?", "correct_answer": "Harry Potter", "accepted_answers": ["Harry Potter", "Harry Potter series"], "choices": ["Star Wars", "Harry Potter", "The Matrix", "Indiana Jones"], "explanation": "Hogwarts is the school in the Harry Potter series.", "difficulty": "easy"},
        {"question": "Who directed the movie Jaws?", "correct_answer": "Steven Spielberg", "accepted_answers": ["Steven Spielberg", "Spielberg"], "choices": ["James Cameron", "Steven Spielberg", "George Lucas", "Ridley Scott"], "explanation": "Jaws was directed by Steven Spielberg.", "difficulty": "medium"},
        {"question": "Which 1999 science fiction film asked whether reality itself was simulated?", "correct_answer": "The Matrix", "accepted_answers": ["The Matrix", "Matrix"], "choices": ["The Matrix", "Blade Runner", "Avatar", "Interstellar"], "explanation": "The Matrix centers on a simulated reality.", "difficulty": "medium"},
    ],
    "1990s": [
        {"question": "Which Nintendo console launched in 1996 in North America?", "correct_answer": "Nintendo 64", "accepted_answers": ["Nintendo 64", "N64"], "choices": ["SNES", "Nintendo 64", "GameCube", "Wii"], "explanation": "The Nintendo 64 launched in 1996 in North America.", "difficulty": "easy"},
        {"question": "Which girl group sang 'Wannabe' in the 1990s?", "correct_answer": "Spice Girls", "accepted_answers": ["Spice Girls", "The Spice Girls"], "choices": ["Destiny's Child", "TLC", "Spice Girls", "ABBA"], "explanation": "Wannabe was the breakout hit of the Spice Girls.", "difficulty": "easy"},
        {"question": "What device became famous for digital pets in the late 1990s?", "correct_answer": "Tamagotchi", "accepted_answers": ["Tamagotchi", "Tamagotchis"], "choices": ["Walkman", "Tamagotchi", "PalmPilot", "Game Boy Camera"], "explanation": "Tamagotchi virtual pets were a late-1990s craze.", "difficulty": "easy"},
        {"question": "Which 1990s sitcom followed six friends living in New York City?", "correct_answer": "Friends", "accepted_answers": ["Friends"], "choices": ["Seinfeld", "Frasier", "Friends", "Full House"], "explanation": "Friends premiered in 1994 and followed six friends in NYC.", "difficulty": "medium"},
    ],
    "2000s": [
        {"question": "Which video-sharing website launched in 2005?", "correct_answer": "YouTube", "accepted_answers": ["YouTube", "Youtube"], "choices": ["Netflix", "YouTube", "Instagram", "Reddit"], "explanation": "YouTube launched in 2005.", "difficulty": "easy"},
        {"question": "Which wizarding film series ended its run in the 2000s and early 2010s?", "correct_answer": "Harry Potter", "accepted_answers": ["Harry Potter", "Harry Potter series"], "choices": ["Harry Potter", "Twilight", "Pirates of the Caribbean", "The Hunger Games"], "explanation": "The Harry Potter film series dominated the 2000s.", "difficulty": "easy"},
        {"question": "Which handheld music player became iconic in the 2000s for carrying '1,000 songs in your pocket'?", "correct_answer": "iPod", "accepted_answers": ["iPod", "The iPod"], "choices": ["Zune", "Discman", "iPod", "Walkman"], "explanation": "Apple's iPod was one of the signature gadgets of the 2000s.", "difficulty": "easy"},
        {"question": "Which fantasy movie trilogy concluded with The Return of the King in 2003?", "correct_answer": "The Lord of the Rings", "accepted_answers": ["The Lord of the Rings", "Lord of the Rings"], "choices": ["The Hobbit", "Narnia", "The Lord of the Rings", "Harry Potter"], "explanation": "The Lord of the Rings trilogy concluded in 2003.", "difficulty": "medium"},
    ],
    "2010s": [
        {"question": "Which Marvel team-up movie released in 2012 launched a huge wave of crossover films?", "correct_answer": "The Avengers", "accepted_answers": ["The Avengers", "Avengers"], "choices": ["Iron Man 3", "The Avengers", "Guardians of the Galaxy", "Captain America"], "explanation": "The Avengers was a major crossover hit in 2012.", "difficulty": "easy"},
        {"question": "Which streaming service became famous in the 2010s for shows like Stranger Things?", "correct_answer": "Netflix", "accepted_answers": ["Netflix"], "choices": ["Hulu", "Prime Video", "Netflix", "Disney+"], "explanation": "Netflix drove much of the streaming boom in the 2010s.", "difficulty": "easy"},
        {"question": "Which social app centered on disappearing photo messages became very popular in the 2010s?", "correct_answer": "Snapchat", "accepted_answers": ["Snapchat"], "choices": ["Snapchat", "WhatsApp", "Telegram", "Skype"], "explanation": "Snapchat became known for disappearing messages and stories.", "difficulty": "easy"},
        {"question": "Which game became a worldwide sensation in 2017 after dropping players onto an island to battle until one remained?", "correct_answer": "Fortnite", "accepted_answers": ["Fortnite"], "choices": ["Minecraft", "Fortnite", "Overwatch", "Roblox"], "explanation": "Fortnite exploded in popularity in 2017.", "difficulty": "medium"},
    ],
    "computer_games": [
        {"question": "Which company created the Mario franchise?", "correct_answer": "Nintendo", "accepted_answers": ["Nintendo"], "choices": ["Sega", "Nintendo", "Sony", "Atari"], "explanation": "Nintendo created Mario.", "difficulty": "easy"},
        {"question": "In Pac-Man, what do the ghosts chase?", "correct_answer": "Pac-Man", "accepted_answers": ["Pac-Man", "Pacman"], "choices": ["Pikachu", "Pac-Man", "Mario", "Sonic"], "explanation": "The ghosts chase Pac-Man through the maze.", "difficulty": "easy"},
        {"question": "Which block-building sandbox game includes Creepers?", "correct_answer": "Minecraft", "accepted_answers": ["Minecraft"], "choices": ["Terraria", "Minecraft", "Roblox", "Fortnite"], "explanation": "Creepers are iconic enemies from Minecraft.", "difficulty": "easy"},
        {"question": "What genre is a game like StarCraft usually placed in?", "correct_answer": "Real-time strategy", "accepted_answers": ["Real-time strategy", "RTS"], "choices": ["First-person shooter", "Real-time strategy", "Sports", "Racing"], "explanation": "StarCraft is one of the best-known RTS games.", "difficulty": "medium"},
    ],
}


def get_curated_trivia_questions(*, category: str, age_range: str, difficulty: str, question_count: int = 10) -> list[dict[str, Any]]:
    category = category if category in _CURATED_TRIVIA_LIBRARY else "fun_facts"
    wanted_levels = {difficulty}
    if difficulty in {"easy_medium", "medium_hard"}:
        wanted_levels = set(difficulty.split("_"))
    source = [item for item in _CURATED_TRIVIA_LIBRARY[category] if item.get("difficulty", "easy") in wanted_levels]
    if not source:
        source = list(_CURATED_TRIVIA_LIBRARY[category])
    age_label = age_range
    results: list[dict[str, Any]] = []
    while len(results) < max(1, question_count):
        for item in source:
            correct_answer = str(item.get("correct_answer") or "").strip()
            accepted_answers = [str(x).strip() for x in item.get("accepted_answers", []) if str(x).strip()]
            if correct_answer and correct_answer not in accepted_answers:
                accepted_answers.insert(0, correct_answer)
            results.append({
                "question": str(item.get("question") or "").strip(),
                "correct_answer": correct_answer,
                "accepted_answers": accepted_answers,
                "choices": [str(x).strip() for x in item.get("choices", []) if str(x).strip()],
                "explanation": str(item.get("explanation") or "").strip(),
                "category": category,
                "age_range": age_label,
                "difficulty": str(item.get("difficulty") or difficulty),
                "source": "curated_offline",
            })
            if len(results) >= question_count:
                break
    return results[:question_count]


@dataclass
class TriviaSession:
    questions: list[dict[str, Any]] = field(default_factory=list)
    current_index: int = -1
    category: str = "fun_facts"
    age_range: str = "18_plus"
    difficulty: str = "medium"
    source: str = "ai"

    @property
    def current_question(self) -> dict[str, Any] | None:
        if 0 <= self.current_index < len(self.questions):
            return self.questions[self.current_index]
        return None

    def as_dict(self) -> dict[str, Any]:
        q = self.current_question or {}
        return {
            "category": self.category,
            "age_range": self.age_range,
            "difficulty": self.difficulty,
            "source": self.source,
            "remaining": max(0, len(self.questions) - max(self.current_index + 1, 0)),
            "current_question": {
                "question": q.get("question"),
                "choices": list(q.get("choices", [])),
                "category": q.get("category", self.category),
                "difficulty": q.get("difficulty", self.difficulty),
                "age_range": q.get("age_range", self.age_range),
                "source": q.get("source", self.source),
            } if q else None,
        }

    def load_questions(self, questions: list[dict[str, Any]], *, category: str, age_range: str, difficulty: str, source: str = "ai") -> None:
        self.questions = list(questions)
        self.current_index = -1
        self.category = category
        self.age_range = age_range
        self.difficulty = difficulty
        self.source = source

    def next_question(self) -> dict[str, Any]:
        if not self.questions:
            raise ValueError("No trivia questions loaded")
        self.current_index += 1
        if self.current_index >= len(self.questions):
            raise ValueError("No trivia questions remaining")
        return self.questions[self.current_index]

    def grade(self, answer: str) -> bool:
        q = self.current_question or {}
        norm_answer = _norm(answer)
        correct_answer = _norm(q.get("correct_answer", ""))
        accepted = {_norm(x) for x in q.get("accepted_answers", []) if _norm(x)}
        if correct_answer:
            accepted.add(correct_answer)
        if norm_answer in accepted:
            return True
        choices = [str(x).strip() for x in q.get("choices", []) if str(x).strip()]
        if len(answer.strip()) == 1 and choices:
            idx = ord(answer.strip().upper()) - 65
            if 0 <= idx < len(choices):
                return _norm(choices[idx]) in accepted
        return False
