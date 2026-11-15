"""
game_logic.py - Deterministic Finite Automaton (DFA) State Machine & Game Rules Engine.

Project: "Who's That Animal?" – Heavy DSA & Automata Desktop Game
Architecture Layer: [Level 2 Agent] State Manager & Game Logic (Automata & Rules)

This module implements:
1. Formal Deterministic Finite Automaton (GameDFA) defined as the 5-tuple (Q, Sigma, delta, q0, F)
   for strict, mathematically verified game state transitions.
2. SinglePlayerController: Survival mode engine (3 Lives, 30s per animal, BFS taxonomic hint reveal
   reward decay 100 -> 75 -> 50 -> 0 pts, 3-wrong-guess life penalty, Levenshtein NFA fuzzy matching).
3. MultiplayerController: Local Split-Screen Competitive mode engine (10 continuous rounds, 60s timer,
   thread-safe mutex lockout for simultaneous guess race conditions, Max-Heap & AVL MMR updates).
"""

from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

# Import core data structures and algorithms from Level 1 DSA Engine
import dsa_engine
from dsa_engine import (
    AVLTreeMMR,
    AnimalRecord,
    LevenshteinAutomaton,
    MaxHeapLeaderboard,
    PrefixTrie,
    TaxonomyDAG,
)


# ============================================================================
# 1. FORMAL AUTOMATA DEFINITIONS: STATES (Q), ALPHABET (Sigma), ERRORS
# ============================================================================


class GameState(str, Enum):
    """
    Finite set of states Q in the Game Deterministic Finite Automaton (DFA).
    Inherits from `str` so `GameState.MAIN_MENU == "MAIN_MENU"` evaluates to True.
    """

    MAIN_MENU = "MAIN_MENU"
    INIT_MODE = "INIT_MODE"
    GUESSING = "GUESSING"
    HINT_REVEAL = "HINT_REVEAL"
    GAME_OVER = "GAME_OVER"

    def __str__(self) -> str:
        return self.value


class GameEvent(str, Enum):
    """
    Input alphabet Sigma (Σ) of events that trigger state transitions in the GameDFA.
    Inherits from `str` so `GameEvent.SELECT_MODE == "SELECT_MODE"` evaluates to True.
    """

    SELECT_MODE = "SELECT_MODE"
    ROUND_READY = "ROUND_READY"
    REQUEST_HINT = "REQUEST_HINT"
    RESUME_GUESS = "RESUME_GUESS"
    NEXT_ROUND = "NEXT_ROUND"
    END_GAME = "END_GAME"
    RESTART = "RESTART"

    def __str__(self) -> str:
        return self.value


class InvalidStateTransitionError(Exception):
    """
    Raised when the GameDFA receives an input symbol σ ∈ Σ that has no valid
    transition from the current state q ∈ Q under δ(q, σ).
    """

    def __init__(self, current_state: str, event: str, message: Optional[str] = None) -> None:
        self.current_state = str(current_state)
        self.event = str(event)
        default_msg = (
            f"Illegal DFA State Transition: δ({self.current_state}, {self.event}) is undefined."
        )
        super().__init__(message or default_msg)


# ============================================================================
# 2. DETERMINISTIC FINITE AUTOMATON (GameDFA)
# ============================================================================


class GameDFA:
    """
    Formal Deterministic Finite Automaton (DFA) governing game state flow.

    Mathematical 5-Tuple Definition: M = (Q, Σ, δ, q_0, F)
    - Q (States): {MAIN_MENU, INIT_MODE, GUESSING, HINT_REVEAL, GAME_OVER}
    - Σ (Alphabet): {SELECT_MODE, ROUND_READY, REQUEST_HINT, RESUME_GUESS,
                     NEXT_ROUND, END_GAME, RESTART}
    - δ (Transition Function): Q × Σ -> Q implemented as an O(1) hash table lookup.
    - q_0 (Initial State): MAIN_MENU
    - F (Accepting / Final States): {GAME_OVER}
    """

    STATES: Set[str] = {s.value for s in GameState}
    ALPHABET: Set[str] = {e.value for e in GameEvent}
    INITIAL_STATE: str = GameState.MAIN_MENU.value
    FINAL_STATES: Set[str] = {GameState.GAME_OVER.value}

    # Explicit transition function δ: (state, event) -> next_state
    TRANSITION_TABLE: Dict[Tuple[str, str], str] = {
        # Mode Initialization
        (GameState.MAIN_MENU.value, GameEvent.SELECT_MODE.value): GameState.INIT_MODE.value,
        (GameState.INIT_MODE.value, GameEvent.ROUND_READY.value): GameState.GUESSING.value,
        # Hint Reveal Sub-Cycle (GUESSING -> HINT_REVEAL -> GUESSING)
        (GameState.GUESSING.value, GameEvent.REQUEST_HINT.value): GameState.HINT_REVEAL.value,
        (GameState.HINT_REVEAL.value, GameEvent.RESUME_GUESS.value): GameState.GUESSING.value,
        (GameState.HINT_REVEAL.value, GameEvent.REQUEST_HINT.value): GameState.HINT_REVEAL.value,
        # Round Progression
        (GameState.GUESSING.value, GameEvent.NEXT_ROUND.value): GameState.INIT_MODE.value,
        (GameState.HINT_REVEAL.value, GameEvent.NEXT_ROUND.value): GameState.INIT_MODE.value,
        # Game Termination
        (GameState.GUESSING.value, GameEvent.END_GAME.value): GameState.GAME_OVER.value,
        (GameState.HINT_REVEAL.value, GameEvent.END_GAME.value): GameState.GAME_OVER.value,
        (GameState.INIT_MODE.value, GameEvent.END_GAME.value): GameState.GAME_OVER.value,
        # Post-Game Replay or Return to Menu
        (GameState.GAME_OVER.value, GameEvent.SELECT_MODE.value): GameState.INIT_MODE.value,
        # Safe Abort / Restart from any state back to MAIN_MENU
        (GameState.MAIN_MENU.value, GameEvent.RESTART.value): GameState.MAIN_MENU.value,
        (GameState.INIT_MODE.value, GameEvent.RESTART.value): GameState.MAIN_MENU.value,
        (GameState.GUESSING.value, GameEvent.RESTART.value): GameState.MAIN_MENU.value,
        (GameState.HINT_REVEAL.value, GameEvent.RESTART.value): GameState.MAIN_MENU.value,
        (GameState.GAME_OVER.value, GameEvent.RESTART.value): GameState.MAIN_MENU.value,
    }

    def __init__(
        self,
        initial_state: str = GameState.MAIN_MENU.value,
        on_transition: Optional[Callable[[str, str, str], None]] = None,
    ) -> None:
        state_val = initial_state.value if isinstance(initial_state, Enum) else str(initial_state)
        if state_val not in self.STATES:
            raise ValueError(f"Unknown initial state: {state_val}")

        self.Q: Set[str] = set(self.STATES)
        self.Sigma: Set[str] = set(self.ALPHABET)
        self.delta: Dict[Tuple[str, str], str] = dict(self.TRANSITION_TABLE)
        self.q0: str = state_val
        self.F: Set[str] = set(self.FINAL_STATES)

        self._current_state: str = self.q0
        self._history: List[Tuple[str, str, str]] = []
        self._callbacks: List[Callable[[str, str, str], None]] = []
        if on_transition is not None:
            self._callbacks.append(on_transition)

    @property
    def current_state(self) -> str:
        """Returns the active state q ∈ Q."""
        return self._current_state

    @property
    def state(self) -> str:
        """Alias for current_state."""
        return self._current_state

    @property
    def history(self) -> List[Tuple[str, str, str]]:
        """Returns a chronological list of (old_state, event, new_state) transitions."""
        return list(self._history)

    def register_callback(self, callback: Callable[[str, str, str], None]) -> None:
        """Registers an observer function `callback(old_state, event, new_state)`."""
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def can_transition(self, event: str) -> bool:
        """Returns True if δ(current_state, event) is defined."""
        ev = event.value if isinstance(event, Enum) else str(event)
        return (self._current_state, ev) in self.delta

    def get_allowed_events(self) -> List[str]:
        """Returns all events σ ∈ Σ valid from the current state."""
        return [ev for (st, ev) in self.delta.keys() if st == self._current_state]

    def trigger(self, event: str) -> str:
        """
        Executes the transition δ(current_state, event) -> next_state in O(1) time.
        Raises InvalidStateTransitionError if the transition is not permitted.
        """
        ev = event.value if isinstance(event, Enum) else str(event)
        key = (self._current_state, ev)
        if key not in self.delta:
            raise InvalidStateTransitionError(self._current_state, ev)

        old_state = self._current_state
        new_state = self.delta[key]
        self._current_state = new_state
        self._history.append((old_state, ev, new_state))

        for cb in self._callbacks:
            try:
                cb(old_state, ev, new_state)
            except Exception:
                # Prevent observer UI exceptions from corrupting formal automaton state
                pass

        return self._current_state

    def transition(self, event: str) -> str:
        """Alias for trigger(event)."""
        return self.trigger(event)

    def is_accepting(self) -> bool:
        """Returns True if the DFA is currently in a final state q ∈ F (GAME_OVER)."""
        return self._current_state in self.F

    def reset(self) -> str:
        """Resets the automaton to q_0 (MAIN_MENU) via the RESTART transition."""
        return self.trigger(GameEvent.RESTART.value)

    def get_formal_definition(self) -> Dict[str, Any]:
        """Returns a dictionary summarizing the 5-tuple (Q, Σ, δ, q0, F) and live status."""
        return {
            "Q": sorted(self.Q),
            "Sigma": sorted(self.Sigma),
            "q0": self.q0,
            "F": sorted(self.F),
            "current_state": self._current_state,
            "is_accepting": self.is_accepting(),
            "transition_count": len(self._history),
        }


# ============================================================================
# 3. DSA ENGINE BUNDLE & SHARED HELPERS
# ============================================================================


@dataclass
class DSAEngineBundle:
    """
    Container holding initialized instances of all Level 1 Data Structures:
    - TaxonomyDAG (directed acyclic graph for BFS hint generation)
    - PrefixTrie (dictionary of valid animal names)
    - LevenshteinAutomaton (NFA typo-tolerant string matcher)
    - MaxHeapLeaderboard (binary max-heap for top scores)
    - AVLTreeMMR (height-balanced BST for player skill ratings)
    """

    dag: TaxonomyDAG
    trie: PrefixTrie
    levenshtein: LevenshteinAutomaton
    leaderboard: MaxHeapLeaderboard
    mmr_tree: AVLTreeMMR
    animals: List[AnimalRecord] = field(default_factory=list)


def create_default_dsa_bundle(assets_dir: str = "assets/animals") -> DSAEngineBundle:
    """
    Constructs and populates the complete DSAEngineBundle from `dsa_engine`.
    Supports multiple builder function names in `dsa_engine` for seamless integration.
    """
    # Check if dsa_engine provides a turnkey factory
    for factory_name in ("build_default_engine", "create_default_engine", "initialize_dsa_engine"):
        factory_fn = getattr(dsa_engine, factory_name, None)
        if callable(factory_fn):
            result = factory_fn()
            if isinstance(result, dict):
                dag = result["dag"]
                trie = result["trie"]
                lev = result.get("levenshtein") or LevenshteinAutomaton()
                lb = result.get("leaderboard") or MaxHeapLeaderboard()
                mmr = result.get("mmr_tree") or AVLTreeMMR()
                animals = result.get("animals") or dag.get_all_animals()
                return DSAEngineBundle(
                    dag=dag,
                    trie=trie,
                    levenshtein=lev,
                    leaderboard=lb,
                    mmr_tree=mmr,
                    animals=list(animals),
                )

    dag = TaxonomyDAG(preload_defaults=True)
    trie = PrefixTrie()
    if hasattr(trie, "populate_from_dag"):
        trie.populate_from_dag(dag)
    else:
        for rec in dag.get_all_animals():
            trie.insert(rec.name)

    levenshtein = LevenshteinAutomaton()
    leaderboard = MaxHeapLeaderboard(seed_defaults=True)
    mmr_tree = AVLTreeMMR(seed_defaults=True)

    all_animals = dag.get_all_animals()

    return DSAEngineBundle(
        dag=dag,
        trie=trie,
        levenshtein=levenshtein,
        leaderboard=leaderboard,
        mmr_tree=mmr_tree,
        animals=list(all_animals),
    )


def _normalize_guess(raw_guess: str) -> str:
    """Normalizes player input by stripping whitespace and converting to lowercase."""
    return " ".join(raw_guess.strip().lower().split())


def _evaluate_animal_guess(
    raw_guess: str,
    target_animal: AnimalRecord,
    trie: PrefixTrie,
    levenshtein: LevenshteinAutomaton,
    max_dist: int = 2,
) -> Tuple[bool, Optional[str], int]:
    """
    Evaluates a player's raw guess against the target animal using the PrefixTrie
    and LevenshteinAutomaton (NFA) with 1-to-2 character typo tolerance:
    - Exact match on target animal canonical name or alias -> (True, target.name, 0)
    - Levenshtein NFA + PrefixTrie intersection (`fuzzy_match`) -> (True, target.name, dist)
    - Levenshtein NFA target evaluation (`matches_animal` / `matches_target`) -> (True, target.name, dist)
    """
    cleaned = _normalize_guess(raw_guess)
    if not cleaned:
        return False, None, -1

    target_name = _normalize_guess(target_animal.name)
    accepted_names = (
        [_normalize_guess(n) for n in target_animal.all_accepted_names()]
        if hasattr(target_animal, "all_accepted_names")
        else [target_name]
    )

    # 1. Fast exact check in PrefixTrie & target comparison
    if cleaned in accepted_names:
        trie.search_exact(cleaned)  # Exercise PrefixTrie exact lookup
        return True, target_animal.name, 0

    # 2. Intersect Levenshtein NFA with the full PrefixTrie via DFS branch pruning
    if hasattr(levenshtein, "fuzzy_match"):
        matched_in_trie, matched_word, trie_dist = levenshtein.fuzzy_match(
            cleaned, trie, max_dist=max_dist
        )
        if matched_in_trie and matched_word and _normalize_guess(matched_word) == target_name:
            return True, target_animal.name, trie_dist

    # 3. Direct Levenshtein NFA evaluation against target_animal (including aliases)
    if hasattr(levenshtein, "matches_animal"):
        is_match, dist = levenshtein.matches_animal(
            cleaned, target_animal, max_dist=max_dist
        )
        if is_match and dist <= max_dist:
            return True, target_animal.name, dist

    # 4. Direct Levenshtein NFA evaluation against target_name string
    if hasattr(levenshtein, "matches_target"):
        is_match, dist = levenshtein.matches_target(
            cleaned, target_name, max_dist=max_dist
        )
        if is_match and dist <= max_dist:
            return True, target_animal.name, dist

    return False, None, -1


# ============================================================================
# 4. SINGLE PLAYER SURVIVAL CONTROLLER
# ============================================================================


class SinglePlayerController:
    """
    Single Player Survival Mode Controller.

    Rules & Mechanics (per SSOT):
    - Lives: Starts with 3 Lives (`lives = 3`).
    - Round Timer: 30 seconds per animal (`ROUND_TIME_LIMIT = 30`).
    - Wrong Guess Penalty: 3 wrong guesses on a single animal = -1 Life.
    - Timeout Penalty: 30-second countdown reaching 0 = -1 Life (and moves to next animal).
    - Progressive Hint System (via TaxonomyDAG BFS):
      * 0 hints revealed: 100 Points
      * 1 hint revealed (Hint 1: Class / Order): 75 Points
      * 2 hints revealed (Hint 2: Region / Habitat): 50 Points
      * 3 hints revealed (Hint 3: Specific Diagnostic Trait): 0 Points
        (Player can either guess for 0 points or skip/advance to the next animal).
    - Game Over: Triggered when `lives <= 0` or the animal deck is completed.
      Pushes final score to `MaxHeapLeaderboard` and updates `AVLTreeMMR`.
    """

    INITIAL_LIVES: int = 3
    ROUND_TIME_LIMIT: int = 30
    MAX_WRONG_GUESSES: int = 3
    MAX_HINTS: int = 3

    # Reward table indexed by number of hints revealed (0, 1, 2, 3)
    HINT_POINT_SCHEDULE: Dict[int, int] = {
        0: 100,
        1: 75,
        2: 50,
        3: 0,
    }

    # Difficulty Presets: (lives, round_time_limit, max_typo_dist, auto_reveal_hint_1)
    DIFFICULTY_CONFIG: Dict[str, Dict[str, Any]] = {
        "EASY": {"lives": 4, "time_limit": 45, "max_dist": 2, "auto_hint_1": True},
        "MEDIUM": {"lives": 3, "time_limit": 30, "max_dist": 2, "auto_hint_1": False},
        "HARD": {"lives": 2, "time_limit": 20, "max_dist": 1, "auto_hint_1": False},
    }

    def __init__(
        self,
        bundle: Optional[DSAEngineBundle] = None,
        dfa: Optional[GameDFA] = None,
        player_name: str = "Player 1",
    ) -> None:
        self.bundle: DSAEngineBundle = bundle or create_default_dsa_bundle()
        self.dfa: GameDFA = dfa or GameDFA()

        self.player_name: str = player_name
        self.difficulty: str = "MEDIUM"
        self.lives: int = self.INITIAL_LIVES
        self.max_lives: int = self.INITIAL_LIVES
        self.round_time_limit: int = self.ROUND_TIME_LIMIT
        self.max_typo_dist: int = 2
        self.score: int = 0
        self.round_timer: int = self.ROUND_TIME_LIMIT
        self.time_remaining: int = self.ROUND_TIME_LIMIT
        self.hints_used: int = 0
        self.hints_revealed: int = 0
        self.free_hints_granted: int = 0
        self.wrong_guesses_on_current: int = 0
        self.wrong_guesses: int = 0
        self.animals_solved: int = 0
        self.round_number: int = 0

        self._deck: List[AnimalRecord] = []
        self._deck_index: int = -1
        self.current_animal: Optional[AnimalRecord] = None
        self.current_hints: List[str] = []
        self.round_active: bool = False
        self._score_recorded: bool = False

    @property
    def current_potential_points(self) -> int:
        """Returns the point reward (100, 75, 50, or 0) for the current hint tier."""
        paid_hints = max(0, self.hints_revealed - self.free_hints_granted)
        if self.hints_revealed >= self.MAX_HINTS:
            return 0
        return self.HINT_POINT_SCHEDULE.get(min(paid_hints, self.MAX_HINTS), 0)

    def _sync_counters(self) -> None:
        """Keeps aliased counter attributes synchronized for UI compatibility."""
        self.hints_used = self.hints_revealed
        self.wrong_guesses_on_current = self.wrong_guesses
        self.round_timer = self.time_remaining

    def start_game(
        self,
        player_name: Optional[str] = None,
        difficulty: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Initializes a new Single Player Survival session.
        Transitions DFA: MAIN_MENU -> INIT_MODE -> GUESSING.
        """
        if player_name and player_name.strip():
            self.player_name = player_name.strip()

        if difficulty and difficulty.strip().upper() in self.DIFFICULTY_CONFIG:
            self.difficulty = difficulty.strip().upper()
        elif not getattr(self, "difficulty", None):
            self.difficulty = "MEDIUM"

        cfg = self.DIFFICULTY_CONFIG.get(self.difficulty, self.DIFFICULTY_CONFIG["MEDIUM"])
        self.max_lives = cfg["lives"] if difficulty is not None else self.INITIAL_LIVES
        self.round_time_limit = cfg["time_limit"] if difficulty is not None else self.ROUND_TIME_LIMIT
        self.max_typo_dist = cfg["max_dist"] if difficulty is not None else 2
        self._auto_hint_1 = bool(cfg["auto_hint_1"]) if difficulty is not None else False

        # Ensure DFA transitions cleanly into INIT_MODE
        if self.dfa.current_state != GameState.MAIN_MENU.value:
            self.dfa.trigger(GameEvent.RESTART.value)
        self.dfa.trigger(GameEvent.SELECT_MODE.value)

        # Reset survival metrics
        self.lives = self.max_lives
        self.score = 0
        self.animals_solved = 0
        self.round_number = 0
        self._score_recorded = False

        # Shuffle animal deck from TaxonomyDAG ordered by selected difficulty
        all_animals = self.bundle.dag.get_all_animals()
        if not all_animals:
            all_animals = list(self.bundle.animals)

        easy_pool = [a for a in all_animals if getattr(a, "difficulty", "EASY") == "EASY"]
        med_pool = [a for a in all_animals if getattr(a, "difficulty", "EASY") == "MEDIUM"]
        hard_pool = [a for a in all_animals if getattr(a, "difficulty", "EASY") == "HARD"]
        random.shuffle(easy_pool)
        random.shuffle(med_pool)
        random.shuffle(hard_pool)

        if difficulty is not None and self.difficulty == "EASY":
            self._deck = easy_pool + med_pool + hard_pool
        elif difficulty is not None and self.difficulty == "HARD":
            self._deck = hard_pool + med_pool + easy_pool
        elif difficulty is not None and self.difficulty == "MEDIUM":
            self._deck = med_pool + easy_pool + hard_pool
        else:
            self._deck = list(all_animals)
            random.shuffle(self._deck)
        self._deck_index = -1

        animal = self.start_next_animal()
        return {
            "status": "started",
            "mode": "SINGLE_PLAYER",
            "difficulty": self.difficulty,
            "player_name": self.player_name,
            "dfa_state": self.dfa.current_state,
            "lives": self.lives,
            "max_lives": self.max_lives,
            "score": self.score,
            "round_number": self.round_number,
            "time_remaining": self.time_remaining,
            "potential_points": self.current_potential_points,
            "animal": animal,
        }

    def start_next_animal(self) -> Optional[AnimalRecord]:
        """
        Loads the next animal in the shuffled survival deck, generates its 3 hints
        via TaxonomyDAG Breadth-First Search (BFS), and transitions DFA to GUESSING.
        Returns None and ends the game if no animals remain or lives <= 0.
        """
        if self.lives <= 0:
            self._finalize_game_over(reason="out_of_lives")
            return None

        # Transition to INIT_MODE if coming from GUESSING or HINT_REVEAL
        if self.dfa.current_state in (GameState.GUESSING.value, GameState.HINT_REVEAL.value):
            self.dfa.trigger(GameEvent.NEXT_ROUND.value)

        self._deck_index += 1
        if self._deck_index >= len(self._deck):
            # Re-shuffle deck if player survives through all available animals, or end game
            # Per SSOT line 88: "Game transitions to GAME_OVER when lives <= 0 or all animals are exhausted."
            self._finalize_game_over(reason="deck_completed")
            return None

        self.round_number += 1
        self.current_animal = self._deck[self._deck_index]
        # Generate the 3 ordered hints dynamically using BFS on the TaxonomyDAG
        self.current_hints = self.bundle.dag.bfs_generate_hints(self.current_animal.name)

        if getattr(self, "_auto_hint_1", False):
            self.hints_revealed = 1
            self.free_hints_granted = 1
        else:
            self.hints_revealed = 0
            self.free_hints_granted = 0

        self.wrong_guesses = 0
        self.time_remaining = getattr(self, "round_time_limit", self.ROUND_TIME_LIMIT)
        self._sync_counters()

        self.round_active = True

        # Transition INIT_MODE -> GUESSING
        if self.dfa.current_state == GameState.INIT_MODE.value:
            self.dfa.trigger(GameEvent.ROUND_READY.value)

        return self.current_animal

    def reveal_hint(self) -> Dict[str, Any]:
        """
        Reveals the next progressive hint (up to 3 hints).
        Executes formal DFA transition: GUESSING -> HINT_REVEAL -> GUESSING.

        Point Decay Schedule:
        - 0 hints: 100 pts
        - 1 hint (Class/Order): 75 pts
        - 2 hints (Region/Habitat): 50 pts
        - 3 hints (Strong Diagnostic Trait): 0 pts
        """
        if self.dfa.current_state not in (GameState.GUESSING.value, GameState.HINT_REVEAL.value):
            raise InvalidStateTransitionError(
                self.dfa.current_state, GameEvent.REQUEST_HINT.value
            )

        # Step into HINT_REVEAL state
        self.dfa.trigger(GameEvent.REQUEST_HINT.value)

        if self.hints_revealed >= self.MAX_HINTS:
            # Already at maximum hints; return to GUESSING state
            self.dfa.trigger(GameEvent.RESUME_GUESS.value)
            return {
                "hint_revealed": False,
                "message": "All 3 hints have already been revealed (0 points remaining).",
                "hints_revealed_count": self.hints_revealed,
                "revealed_hints": list(self.current_hints[: self.hints_revealed]),
                "latest_hint": self.current_hints[-1] if self.current_hints else "",
                "potential_points": self.current_potential_points,
                "can_advance_zero_points": True,
                "dfa_state": self.dfa.current_state,
            }

        self.hints_revealed += 1
        self._sync_counters()
        latest_hint = (
            self.current_hints[self.hints_revealed - 1]
            if self.hints_revealed <= len(self.current_hints)
            else ""
        )

        # Resume active GUESSING state after revealing the hint
        self.dfa.trigger(GameEvent.RESUME_GUESS.value)

        is_strong_trait = self.hints_revealed == self.MAX_HINTS
        msg = (
            f"Hint {self.hints_revealed} revealed! Potential reward is now {self.current_potential_points} pts."
            if not is_strong_trait
            else "Hint 3 (Strong Trait) revealed! Reward is now 0 pts — guess to practice or advance to next animal."
        )

        return {
            "hint_revealed": True,
            "hint_index": self.hints_revealed,
            "latest_hint": latest_hint,
            "revealed_hints": list(self.current_hints[: self.hints_revealed]),
            "hints_revealed_count": self.hints_revealed,
            "potential_points": self.current_potential_points,
            "can_advance_zero_points": is_strong_trait,
            "message": msg,
            "dfa_state": self.dfa.current_state,
        }

    def skip_after_all_hints(self) -> Dict[str, Any]:
        """
        Allows the player to immediately advance to the next animal for 0 points
        without losing a life once all 3 hints (including the 0-point Strong Trait)
        have been revealed.
        """
        prev_animal = self.current_animal
        self.round_active = False
        return {
            "skipped": True,
            "points_awarded": 0,
            "animal": prev_animal,
            "score": self.score,
            "lives": self.lives,
            "dfa_state": self.dfa.current_state,
            "message": (
                f"Revealed: {prev_animal.display_name if prev_animal else 'Unknown'} (+0 pts)."
            ),
        }

    def submit_guess(self, raw_guess: str) -> Dict[str, Any]:
        """
        Validates a player's guess using the LevenshteinAutomaton + PrefixTrie.
        - On Correct Match:
          Awards `current_potential_points` (100, 75, 50, or 0), marks round resolved.
        - On Wrong Guess:
          Increments `wrong_guesses`. If `wrong_guesses >= 3`, deducts 1 Life (`lives -= 1`)
          and ends the current animal round (or transitions to `GAME_OVER` if `lives <= 0`).
        """
        if self.dfa.current_state not in (GameState.GUESSING.value, GameState.HINT_REVEAL.value):
            return {
                "valid_submission": False,
                "correct": False,
                "message": f"Cannot submit guess in state {self.dfa.current_state}.",
                "dfa_state": self.dfa.current_state,
            }

        if self.dfa.current_state == GameState.HINT_REVEAL.value:
            self.dfa.trigger(GameEvent.RESUME_GUESS.value)

        cleaned = _normalize_guess(raw_guess)
        if not cleaned or self.current_animal is None:
            return {
                "valid_submission": False,
                "correct": False,
                "message": "Please enter an animal name.",
                "dfa_state": self.dfa.current_state,
            }

        is_correct, matched_name, edit_dist = _evaluate_animal_guess(
            raw_guess=cleaned,
            target_animal=self.current_animal,
            trie=self.bundle.trie,
            levenshtein=self.bundle.levenshtein,
            max_dist=getattr(self, "max_typo_dist", 2),
        )

        if is_correct:
            pts = self.current_potential_points
            self.score += pts
            self.animals_solved += 1
            self.round_active = False

            typo_note = (
                " (Exact Match!)"
                if edit_dist == 0
                else f" (Fuzzy Match via Levenshtein NFA: edit distance {edit_dist})"
            )
            return {
                "valid_submission": True,
                "correct": True,
                "points_awarded": pts,
                "score": self.score,
                "lives": self.lives,
                "matched_name": matched_name or self.current_animal.name,
                "display_name": self.current_animal.display_name,
                "edit_distance": edit_dist,
                "animal": self.current_animal,
                "hints_used": self.hints_revealed,
                "wrong_guesses": self.wrong_guesses,
                "round_over": True,
                "game_over": False,
                "dfa_state": self.dfa.current_state,
                "message": f"Correct! It's {self.current_animal.display_name}! +{pts} pts{typo_note}",
            }

        # Wrong Guess Handling
        self.wrong_guesses += 1
        self._sync_counters()
        strikes_left = max(0, self.MAX_WRONG_GUESSES - self.wrong_guesses)

        life_lost = False
        game_over = False

        if self.wrong_guesses >= self.MAX_WRONG_GUESSES:
            self.lives -= 1
            life_lost = True
            self.round_active = False
            if self.lives <= 0:
                self.lives = 0
                game_over = True
                self._finalize_game_over(reason="out_of_lives")

        if game_over:
            msg = (
                f"3 wrong guesses! The animal was {self.current_animal.display_name}. "
                f"Out of lives — GAME OVER!"
            )
        elif life_lost:
            msg = (
                f"3 wrong guesses! -1 Life ({self.lives} remaining). "
                f"The animal was {self.current_animal.display_name}."
            )
        else:
            msg = (
                f"Incorrect guess ('{raw_guess.strip()}'). "
                f"Strike {self.wrong_guesses}/{self.MAX_WRONG_GUESSES} "
                f"({strikes_left} attempt{'s' if strikes_left != 1 else ''} left before losing a life)."
            )

        return {
            "valid_submission": True,
            "correct": False,
            "points_awarded": 0,
            "score": self.score,
            "lives": self.lives,
            "wrong_guesses": self.wrong_guesses,
            "strikes_remaining": strikes_left,
            "life_lost": life_lost,
            "round_over": life_lost or game_over,
            "game_over": game_over,
            "animal": self.current_animal,
            "display_name": self.current_animal.display_name,
            "dfa_state": self.dfa.current_state,
            "message": msg,
        }

    def tick_timer(self, seconds: int = 1) -> Dict[str, Any]:
        """
        Decrements the 30-second countdown timer by `seconds`.
        Automatically invokes `handle_timeout()` if `time_remaining <= 0`.
        """
        if not self.round_active or self.dfa.current_state == GameState.GAME_OVER.value:
            return {
                "time_remaining": self.time_remaining,
                "timed_out": False,
                "game_over": self.dfa.current_state == GameState.GAME_OVER.value,
                "dfa_state": self.dfa.current_state,
            }

        self.time_remaining = max(0, self.time_remaining - seconds)
        self._sync_counters()

        if self.time_remaining <= 0:
            return self.handle_timeout()

        return {
            "time_remaining": self.time_remaining,
            "timed_out": False,
            "game_over": False,
            "dfa_state": self.dfa.current_state,
        }

    def handle_timeout(self) -> Dict[str, Any]:
        """
        Handles expiration of the 30-second animal timer.
        Deducts 1 Life (`lives -= 1`). Transitions to `GAME_OVER` if `lives <= 0`.
        """
        self.time_remaining = 0
        self.round_active = False
        self.lives = max(0, self.lives - 1)
        self._sync_counters()

        game_over = False
        if self.lives <= 0:
            game_over = True
            self._finalize_game_over(reason="timeout_out_of_lives")

        animal_name = self.current_animal.display_name if self.current_animal else "Unknown"
        msg = (
            f"Time's up! -1 Life. Out of lives — GAME OVER! (Animal was {animal_name})"
            if game_over
            else f"Time's up (30s)! -1 Life ({self.lives} remaining). The animal was {animal_name}."
        )

        return {
            "timed_out": True,
            "life_lost": True,
            "lives": self.lives,
            "score": self.score,
            "round_over": True,
            "game_over": game_over,
            "animal": self.current_animal,
            "display_name": animal_name,
            "dfa_state": self.dfa.current_state,
            "message": msg,
        }

    def end_session(self) -> Dict[str, Any]:
        """Allows the player or UI to end the current survival run early and record score."""
        self._finalize_game_over(reason="manual_end")
        return {
            "game_over": True,
            "score": self.score,
            "lives": self.lives,
            "animals_solved": self.animals_solved,
            "dfa_state": self.dfa.current_state,
            "top_scores": self.bundle.leaderboard.get_top_k(10),
        }

    def _finalize_game_over(self, reason: str = "out_of_lives") -> None:
        """
        Transitions the DFA to `GAME_OVER` and persists the player's score
        into the Binary Max-Heap Leaderboard (`MaxHeapLeaderboard`) and updates
        their skill rating in the self-balancing `AVLTreeMMR`.
        """
        self.round_active = False
        if self.dfa.current_state != GameState.GAME_OVER.value:
            if self.dfa.can_transition(GameEvent.END_GAME.value):
                self.dfa.trigger(GameEvent.END_GAME.value)

        if not self._score_recorded:
            self._score_recorded = True
            self.bundle.leaderboard.insert(self.player_name, self.score)
            self._update_player_mmr()

    def _update_player_mmr(self) -> None:
        """Updates the player's MMR node in the AVL Tree based on survival performance."""
        existing = self._find_existing_mmr_record(self.player_name)
        base_mmr = existing["mmr"] if existing else 1000
        prev_wins = existing.get("wins", 0) if existing else 0
        prev_games = existing.get("games", 0) if existing else 0

        # Calculate MMR delta from survival score and animals solved
        mmr_delta = (self.score // 10) - 15 if self.score > 0 else -15
        new_mmr = max(100, base_mmr + mmr_delta)
        won_run = 1 if self.animals_solved >= 3 else 0

        self.bundle.mmr_tree.upsert_player(
            self.player_name,
            new_mmr,
            wins=prev_wins + won_run,
            games=prev_games + 1,
        )

    def _find_existing_mmr_record(self, player_id: str) -> Optional[Dict[str, Any]]:
        """Looks up a player's current record in the AVL Tree rankings."""
        for entry in self.bundle.mmr_tree.inorder_rankings():
            if entry.get("player_id") == player_id:
                return entry
        return None

    def get_status_snapshot(self) -> Dict[str, Any]:
        """Returns a complete snapshot of Single Player state for the Tkinter HUD."""
        return {
            "mode": "SINGLE_PLAYER",
            "player_name": self.player_name,
            "dfa_state": self.dfa.current_state,
            "score": self.score,
            "lives": self.lives,
            "round_number": self.round_number,
            "time_remaining": self.time_remaining,
            "hints_revealed": self.hints_revealed,
            "revealed_hints": list(self.current_hints[: self.hints_revealed]),
            "potential_points": self.current_potential_points,
            "wrong_guesses": self.wrong_guesses,
            "strikes_remaining": max(0, self.MAX_WRONG_GUESSES - self.wrong_guesses),
            "animals_solved": self.animals_solved,
            "current_animal": self.current_animal,
        }


# ============================================================================
# 5. LOCAL MULTIPLAYER COMPETITIVE CONTROLLER (SPLIT-SCREEN + RACE LOCKOUT)
# ============================================================================


class MultiplayerController:
    """
    Local Split-Screen Multiplayer Competitive Mode Controller.

    Rules & Mechanics (per SSOT):
    - Continuous 10-round match (`TOTAL_ROUNDS = 10`).
    - Round Timer: 60 seconds per round (`ROUND_TIME_LIMIT = 60`).
    - Shared Mystery Animal Silhouette & Shared Hint progression per round.
    - Race-Condition Mutex Lockout (`threading.Lock` + `round_locked: bool`):
      * Both Player 1 (Left Station) and Player 2 (Right Station) have independent
        input entries and can submit guesses at any instant.
      * The first player whose guess is accepted by the Levenshtein NFA + PrefixTrie
        atomically acquires `_race_lock`, sets `round_locked = True`, records
        `round_winner = player_num`, earns the round's points, and immediately
        locks out the opponent for the remainder of that round.
    - Post-Match Rating Updates:
      * Pushes both players' scores to `MaxHeapLeaderboard`.
      * Updates both players' MMR in `AVLTreeMMR` (triggering self-balancing AVL rotations)
        and queries `find_closest_match` for matchmaking feedback.
    """

    TOTAL_ROUNDS: int = 10
    ROUND_TIME_LIMIT: int = 60
    MAX_HINTS: int = 3

    # Competitive point reward schedule by hints revealed
    HINT_POINT_SCHEDULE: Dict[int, int] = {
        0: 100,
        1: 75,
        2: 50,
        3: 25,
    }

    DIFFICULTY_CONFIG: Dict[str, Dict[str, Any]] = {
        "EASY": {"time_limit": 75, "max_dist": 2, "auto_hint_1": True},
        "MEDIUM": {"time_limit": 60, "max_dist": 2, "auto_hint_1": False},
        "HARD": {"time_limit": 40, "max_dist": 1, "auto_hint_1": False},
    }

    def __init__(
        self,
        bundle: Optional[DSAEngineBundle] = None,
        dfa: Optional[GameDFA] = None,
        p1_name: str = "Player 1",
        p2_name: str = "Player 2",
    ) -> None:
        self.bundle: DSAEngineBundle = bundle or create_default_dsa_bundle()
        self.dfa: GameDFA = dfa or GameDFA()

        self.p1_name: str = p1_name
        self.p2_name: str = p2_name
        self.difficulty: str = "MEDIUM"
        self.round_time_limit: int = self.ROUND_TIME_LIMIT
        self.max_typo_dist: int = 2
        self.free_hints_granted: int = 0
        self.p1_score: int = 0
        self.p2_score: int = 0
        self.p1_rounds_won: int = 0
        self.p2_rounds_won: int = 0
        self.p1_wrong_guesses: int = 0
        self.p2_wrong_guesses: int = 0

        self.current_round: int = 0
        self.round_timer: int = self.ROUND_TIME_LIMIT
        self.time_remaining: int = self.ROUND_TIME_LIMIT
        self.hints_revealed: int = 0

        # Concurrency & Race-Condition Lockout Primitives
        self._race_lock: threading.Lock = threading.Lock()
        self.round_locked: bool = False
        self.round_winner: Optional[int] = None
        self.round_history: List[Dict[str, Any]] = []

        self._deck: List[AnimalRecord] = []
        self.current_animal: Optional[AnimalRecord] = None
        self.current_hints: List[str] = []
        self._match_recorded: bool = False

    @property
    def current_potential_points(self) -> int:
        """Returns the point value available for winning the current round."""
        paid_hints = max(0, self.hints_revealed - self.free_hints_granted)
        if self.hints_revealed >= self.MAX_HINTS:
            return 25
        return self.HINT_POINT_SCHEDULE.get(min(paid_hints, self.MAX_HINTS), 25)

    def start_match(
        self,
        p1_name: Optional[str] = None,
        p2_name: Optional[str] = None,
        difficulty: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Starts a 10-round Local Multiplayer Competitive match.
        Transitions DFA: MAIN_MENU -> INIT_MODE -> GUESSING.
        """
        if p1_name and p1_name.strip():
            self.p1_name = p1_name.strip()
        if p2_name and p2_name.strip():
            self.p2_name = p2_name.strip()
        if self.p1_name == self.p2_name:
            self.p2_name = f"{self.p2_name} (P2)"

        if difficulty and difficulty.strip().upper() in self.DIFFICULTY_CONFIG:
            self.difficulty = difficulty.strip().upper()
        elif not getattr(self, "difficulty", None):
            self.difficulty = "MEDIUM"

        cfg = self.DIFFICULTY_CONFIG.get(self.difficulty, self.DIFFICULTY_CONFIG["MEDIUM"])
        self.round_time_limit = cfg["time_limit"] if difficulty is not None else self.ROUND_TIME_LIMIT
        self.max_typo_dist = cfg["max_dist"] if difficulty is not None else 2
        self._auto_hint_1 = bool(cfg["auto_hint_1"]) if difficulty is not None else False

        if self.dfa.current_state != GameState.MAIN_MENU.value:
            self.dfa.trigger(GameEvent.RESTART.value)
        self.dfa.trigger(GameEvent.SELECT_MODE.value)

        self.p1_score = 0
        self.p2_score = 0
        self.p1_rounds_won = 0
        self.p2_rounds_won = 0
        self.current_round = 0
        self.round_history.clear()
        self._match_recorded = False

        # Build a 10-animal deck from the TaxonomyDAG ordered by difficulty
        all_animals = self.bundle.dag.get_all_animals()
        if not all_animals:
            all_animals = list(self.bundle.animals)

        easy_pool = [a for a in all_animals if getattr(a, "difficulty", "EASY") == "EASY"]
        med_pool = [a for a in all_animals if getattr(a, "difficulty", "EASY") == "MEDIUM"]
        hard_pool = [a for a in all_animals if getattr(a, "difficulty", "EASY") == "HARD"]
        random.shuffle(easy_pool)
        random.shuffle(med_pool)
        random.shuffle(hard_pool)

        if difficulty is not None and self.difficulty == "EASY":
            pool = easy_pool + med_pool + hard_pool
        elif difficulty is not None and self.difficulty == "HARD":
            pool = hard_pool + med_pool + easy_pool
        elif difficulty is not None and self.difficulty == "MEDIUM":
            pool = med_pool + easy_pool + hard_pool
        else:
            pool = list(all_animals)
            random.shuffle(pool)

        # Ensure at least TOTAL_ROUNDS animals
        while len(pool) < self.TOTAL_ROUNDS and all_animals:
            extra = list(all_animals)
            random.shuffle(extra)
            pool.extend(extra)
        self._deck = pool[: self.TOTAL_ROUNDS]

        first_animal = self.start_next_round()
        return {
            "status": "started",
            "mode": "MULTIPLAYER",
            "difficulty": self.difficulty,
            "p1_name": self.p1_name,
            "p2_name": self.p2_name,
            "p1_score": self.p1_score,
            "p2_score": self.p2_score,
            "current_round": self.current_round,
            "total_rounds": self.TOTAL_ROUNDS,
            "time_remaining": self.time_remaining,
            "potential_points": self.current_potential_points,
            "round_locked": self.round_locked,
            "dfa_state": self.dfa.current_state,
            "animal": first_animal,
        }

    def start_next_round(self) -> Optional[AnimalRecord]:
        """
        Advances to the next round (1..10), unlocks the race-condition mutex,
        resets the timer, generates BFS hints, and transitions DFA to GUESSING.
        If round 10 has finished, transitions DFA to GAME_OVER.
        """
        if self.current_round >= self.TOTAL_ROUNDS:
            self._finalize_match()
            return None

        if self.dfa.current_state in (GameState.GUESSING.value, GameState.HINT_REVEAL.value):
            self.dfa.trigger(GameEvent.NEXT_ROUND.value)

        with self._race_lock:
            self.current_round += 1
            self.current_animal = self._deck[self.current_round - 1]
            self.current_hints = self.bundle.dag.bfs_generate_hints(self.current_animal.name)
            if getattr(self, "_auto_hint_1", False):
                self.hints_revealed = 1
                self.free_hints_granted = 1
            else:
                self.hints_revealed = 0
                self.free_hints_granted = 0
            self.p1_wrong_guesses = 0
            self.p2_wrong_guesses = 0
            t_limit = getattr(self, "round_time_limit", self.ROUND_TIME_LIMIT)
            self.time_remaining = t_limit
            self.round_timer = t_limit
            self.round_locked = False
            self.round_winner = None

        if self.dfa.current_state == GameState.INIT_MODE.value:
            self.dfa.trigger(GameEvent.ROUND_READY.value)

        return self.current_animal

    def reveal_shared_hint(self) -> Dict[str, Any]:
        """
        Reveals the next shared hint in Multiplayer mode.
        Transitions DFA: GUESSING -> HINT_REVEAL -> GUESSING.
        """
        if self.round_locked:
            return {
                "hint_revealed": False,
                "message": "Round is already locked and completed.",
                "dfa_state": self.dfa.current_state,
            }

        if self.dfa.current_state not in (GameState.GUESSING.value, GameState.HINT_REVEAL.value):
            raise InvalidStateTransitionError(
                self.dfa.current_state, GameEvent.REQUEST_HINT.value
            )

        self.dfa.trigger(GameEvent.REQUEST_HINT.value)

        if self.hints_revealed >= self.MAX_HINTS:
            self.dfa.trigger(GameEvent.RESUME_GUESS.value)
            return {
                "hint_revealed": False,
                "hints_revealed_count": self.hints_revealed,
                "revealed_hints": list(self.current_hints[: self.hints_revealed]),
                "latest_hint": self.current_hints[-1] if self.current_hints else "",
                "potential_points": self.current_potential_points,
                "dfa_state": self.dfa.current_state,
                "message": "All 3 hints are already visible!",
            }

        self.hints_revealed += 1
        latest_hint = (
            self.current_hints[self.hints_revealed - 1]
            if self.hints_revealed <= len(self.current_hints)
            else ""
        )
        self.dfa.trigger(GameEvent.RESUME_GUESS.value)

        return {
            "hint_revealed": True,
            "hint_index": self.hints_revealed,
            "latest_hint": latest_hint,
            "revealed_hints": list(self.current_hints[: self.hints_revealed]),
            "hints_revealed_count": self.hints_revealed,
            "potential_points": self.current_potential_points,
            "dfa_state": self.dfa.current_state,
            "message": f"Shared Hint {self.hints_revealed} revealed! Round value: {self.current_potential_points} pts.",
        }

    # Alias for controller uniformity
    reveal_hint = reveal_shared_hint

    def submit_guess(self, player_num: int, raw_guess: str) -> Dict[str, Any]:
        """
        Thread-safe competitive guess submission with atomic race-condition lockout.

        Parameters:
            player_num: 1 (Player 1 Left Station) or 2 (Player 2 Right Station)
            raw_guess: Raw string from that player's independentEntry widget.

        Behavior:
        - Acquires `self._race_lock`.
        - If `self.round_locked` is already True, immediately rejects the submission
          with `locked_out = True`.
        - Evaluates `raw_guess` via `LevenshteinAutomaton` + `PrefixTrie` (1-2 typo tolerance).
        - If matched:
          Atomically sets `self.round_locked = True`, assigns `self.round_winner = player_num`,
          increments the winning player's score, and locks out the other player.
        """
        if player_num not in (1, 2):
            raise ValueError("player_num must be 1 or 2.")

        player_label = self.p1_name if player_num == 1 else self.p2_name
        opponent_label = self.p2_name if player_num == 1 else self.p1_name

        with self._race_lock:
            # 1. Check Race-Condition Lockout first
            if self.round_locked:
                winner_name = (
                    self.p1_name
                    if self.round_winner == 1
                    else (self.p2_name if self.round_winner == 2 else "No one")
                )
                return {
                    "valid_submission": False,
                    "locked_out": True,
                    "correct": False,
                    "player_num": player_num,
                    "round_winner": self.round_winner,
                    "dfa_state": self.dfa.current_state,
                    "message": f"Locked out! {winner_name} already claimed Round {self.current_round}.",
                }

            # 2. Check DFA state validity
            if self.dfa.current_state not in (
                GameState.GUESSING.value,
                GameState.HINT_REVEAL.value,
            ):
                return {
                    "valid_submission": False,
                    "locked_out": False,
                    "correct": False,
                    "player_num": player_num,
                    "dfa_state": self.dfa.current_state,
                    "message": f"Guesses not active in state {self.dfa.current_state}.",
                }

            if self.dfa.current_state == GameState.HINT_REVEAL.value:
                self.dfa.trigger(GameEvent.RESUME_GUESS.value)

            cleaned = _normalize_guess(raw_guess)
            if not cleaned or self.current_animal is None:
                return {
                    "valid_submission": False,
                    "locked_out": False,
                    "correct": False,
                    "player_num": player_num,
                    "dfa_state": self.dfa.current_state,
                    "message": f"{player_label}: Enter an animal name!",
                }

            # 3. Evaluate guess via Levenshtein NFA + PrefixTrie
            is_correct, matched_name, edit_dist = _evaluate_animal_guess(
                raw_guess=cleaned,
                target_animal=self.current_animal,
                trie=self.bundle.trie,
                levenshtein=self.bundle.levenshtein,
                max_dist=getattr(self, "max_typo_dist", 2),
            )

            if is_correct:
                # ATOMIC LOCKOUT: This player wins the race for the current round
                self.round_locked = True
                self.round_winner = player_num
                pts = self.current_potential_points

                if player_num == 1:
                    self.p1_score += pts
                    self.p1_rounds_won += 1
                else:
                    self.p2_score += pts
                    self.p2_rounds_won += 1

                self.round_history.append(
                    {
                        "round": self.current_round,
                        "animal": self.current_animal.display_name,
                        "winner": player_num,
                        "winner_name": player_label,
                        "points": pts,
                        "edit_distance": edit_dist,
                        "time_remaining": self.time_remaining,
                    }
                )

                is_final_round = self.current_round >= self.TOTAL_ROUNDS
                if is_final_round:
                    self._finalize_match()

                typo_tag = (
                    "Exact Match"
                    if edit_dist == 0
                    else f"Fuzzy Match (edit dist {edit_dist})"
                )
                return {
                    "valid_submission": True,
                    "locked_out": False,
                    "opponent_locked_out": True,
                    "correct": True,
                    "player_num": player_num,
                    "player_name": player_label,
                    "round_winner": player_num,
                    "points_awarded": pts,
                    "p1_score": self.p1_score,
                    "p2_score": self.p2_score,
                    "matched_name": matched_name or self.current_animal.name,
                    "display_name": self.current_animal.display_name,
                    "edit_distance": edit_dist,
                    "animal": self.current_animal,
                    "current_round": self.current_round,
                    "total_rounds": self.TOTAL_ROUNDS,
                    "round_over": True,
                    "match_over": is_final_round,
                    "dfa_state": self.dfa.current_state,
                    "message": (
                        f"{player_label} wins Round {self.current_round} (+{pts} pts, {typo_tag})! "
                        f"{opponent_label} is locked out! Animal: {self.current_animal.display_name}."
                    ),
                }

            # 4. Incorrect guess by this player (round stays unlocked for both players!)
            if player_num == 1:
                self.p1_wrong_guesses += 1
                wrong_cnt = self.p1_wrong_guesses
            else:
                self.p2_wrong_guesses += 1
                wrong_cnt = self.p2_wrong_guesses

            return {
                "valid_submission": True,
                "locked_out": False,
                "correct": False,
                "player_num": player_num,
                "player_name": player_label,
                "wrong_guesses": wrong_cnt,
                "p1_score": self.p1_score,
                "p2_score": self.p2_score,
                "round_over": False,
                "match_over": False,
                "dfa_state": self.dfa.current_state,
                "message": f"{player_label}: '{raw_guess.strip()}' is incorrect! Keep trying!",
            }

    def tick_timer(self, seconds: int = 1) -> Dict[str, Any]:
        """
        Decrements the 60-second round timer by `seconds`.
        If the timer reaches 0 while unlocked, triggers `handle_timeout()`.
        """
        if self.round_locked or self.dfa.current_state == GameState.GAME_OVER.value:
            return {
                "time_remaining": self.time_remaining,
                "timed_out": False,
                "round_locked": self.round_locked,
                "match_over": self.dfa.current_state == GameState.GAME_OVER.value,
                "dfa_state": self.dfa.current_state,
            }

        self.time_remaining = max(0, self.time_remaining - seconds)
        self.round_timer = self.time_remaining

        if self.time_remaining <= 0:
            return self.handle_timeout()

        return {
            "time_remaining": self.time_remaining,
            "timed_out": False,
            "round_locked": self.round_locked,
            "match_over": False,
            "dfa_state": self.dfa.current_state,
        }

    def handle_timeout(self) -> Dict[str, Any]:
        """
        Handles expiration of the 60-second round timer when neither player
        guessed the animal. Locks the round and advances (or ends match after round 10).
        """
        with self._race_lock:
            self.time_remaining = 0
            self.round_timer = 0
            self.round_locked = True
            self.round_winner = None

            animal_name = self.current_animal.display_name if self.current_animal else "Unknown"
            self.round_history.append(
                {
                    "round": self.current_round,
                    "animal": animal_name,
                    "winner": None,
                    "winner_name": "Draw (Timeout)",
                    "points": 0,
                    "edit_distance": -1,
                    "time_remaining": 0,
                }
            )

            is_final_round = self.current_round >= self.TOTAL_ROUNDS
            if is_final_round:
                self._finalize_match()

            return {
                "timed_out": True,
                "round_locked": True,
                "round_winner": None,
                "p1_score": self.p1_score,
                "p2_score": self.p2_score,
                "animal": self.current_animal,
                "display_name": animal_name,
                "current_round": self.current_round,
                "total_rounds": self.TOTAL_ROUNDS,
                "round_over": True,
                "match_over": is_final_round,
                "dfa_state": self.dfa.current_state,
                "message": f"Round {self.current_round} timed out (60s)! The animal was {animal_name}.",
            }

    def _finalize_match(self) -> None:
        """
        Transitions the DFA to `GAME_OVER`, records both players' scores in
        `MaxHeapLeaderboard`, and updates both players' skill ratings in `AVLTreeMMR`.
        """
        if self.dfa.current_state != GameState.GAME_OVER.value:
            if self.dfa.can_transition(GameEvent.END_GAME.value):
                self.dfa.trigger(GameEvent.END_GAME.value)

        if not self._match_recorded:
            self._match_recorded = True
            self.bundle.leaderboard.insert(self.p1_name, self.p1_score)
            self.bundle.leaderboard.insert(self.p2_name, self.p2_score)
            self._update_multiplayer_mmr()

    def _update_multiplayer_mmr(self) -> None:
        """
        Computes competitive Elo/MMR adjustments for Player 1 and Player 2
        and upserts both into the self-balancing `AVLTreeMMR`.
        """
        if hasattr(self.bundle.mmr_tree, "update_match_result"):
            is_draw = self.p1_score == self.p2_score
            p1_won = True if self.p1_score > self.p2_score else (False if self.p2_score > self.p1_score else None)
            self.bundle.mmr_tree.update_match_result(
                p1_id=self.p1_name,
                p2_id=self.p2_name,
                p1_won=p1_won,
                is_draw=is_draw,
            )
            return

        rankings = {
            r["player_id"]: r for r in self.bundle.mmr_tree.inorder_rankings() if "player_id" in r
        }

        p1_rec = rankings.get(self.p1_name, {"mmr": 1200, "wins": 0, "games": 0})
        p2_rec = rankings.get(self.p2_name, {"mmr": 1200, "wins": 0, "games": 0})

        p1_mmr = int(p1_rec.get("mmr", 1200))
        p2_mmr = int(p2_rec.get("mmr", 1200))

        if self.p1_score > self.p2_score:
            p1_new_mmr = p1_mmr + 35
            p2_new_mmr = max(100, p2_mmr - 25)
            p1_win_inc, p2_win_inc = 1, 0
        elif self.p2_score > self.p1_score:
            p1_new_mmr = max(100, p1_mmr - 25)
            p2_new_mmr = p2_mmr + 35
            p1_win_inc, p2_win_inc = 0, 1
        else:
            p1_new_mmr = p1_mmr + 10
            p2_new_mmr = p2_mmr + 10
            p1_win_inc, p2_win_inc = 0, 0

        self.bundle.mmr_tree.upsert_player(
            self.p1_name,
            p1_new_mmr,
            wins=int(p1_rec.get("wins", 0)) + p1_win_inc,
            games=int(p1_rec.get("games", 0)) + 1,
        )
        self.bundle.mmr_tree.upsert_player(
            self.p2_name,
            p2_new_mmr,
            wins=int(p2_rec.get("wins", 0)) + p2_win_inc,
            games=int(p2_rec.get("games", 0)) + 1,
        )

    def get_match_summary(self) -> Dict[str, Any]:
        """
        Returns a comprehensive post-match summary including winner, final scores,
        round-by-round breakdown, top leaderboard entries, and AVL closest MMR matches.
        """
        if self.p1_score > self.p2_score:
            overall_winner = self.p1_name
            winner_num = 1
        elif self.p2_score > self.p1_score:
            overall_winner = self.p2_name
            winner_num = 2
        else:
            overall_winner = "Draw"
            winner_num = 0

        rankings = {
            r["player_id"]: r for r in self.bundle.mmr_tree.inorder_rankings() if "player_id" in r
        }
        p1_mmr = rankings.get(self.p1_name, {}).get("mmr", 1000)
        p2_mmr = rankings.get(self.p2_name, {}).get("mmr", 1000)

        p1_next_rival = self.bundle.mmr_tree.find_closest_match(
            p1_mmr, exclude_player=self.p1_name
        )
        p2_next_rival = self.bundle.mmr_tree.find_closest_match(
            p2_mmr, exclude_player=self.p2_name
        )

        return {
            "overall_winner": overall_winner,
            "winner_num": winner_num,
            "p1_name": self.p1_name,
            "p2_name": self.p2_name,
            "p1_score": self.p1_score,
            "p2_score": self.p2_score,
            "p1_rounds_won": self.p1_rounds_won,
            "p2_rounds_won": self.p2_rounds_won,
            "p1_mmr": p1_mmr,
            "p2_mmr": p2_mmr,
            "p1_Suggested_opponent": p1_next_rival,
            "p2_Suggested_opponent": p2_next_rival,
            "round_history": list(self.round_history),
            "leaderboard_top": self.bundle.leaderboard.get_top_k(10),
            "avl_rankings": self.bundle.mmr_tree.inorder_rankings(),
            "dfa_state": self.dfa.current_state,
        }

    def get_status_snapshot(self) -> Dict[str, Any]:
        """Returns a complete live snapshot of Multiplayer state for the Split-Screen UI."""
        return {
            "mode": "MULTIPLAYER",
            "dfa_state": self.dfa.current_state,
            "current_round": self.current_round,
            "total_rounds": self.TOTAL_ROUNDS,
            "time_remaining": self.time_remaining,
            "round_locked": self.round_locked,
            "round_winner": self.round_winner,
            "p1_name": self.p1_name,
            "p2_name": self.p2_name,
            "p1_score": self.p1_score,
            "p2_score": self.p2_score,
            "p1_rounds_won": self.p1_rounds_won,
            "p2_rounds_won": self.p2_rounds_won,
            "p1_wrong_guesses": self.p1_wrong_guesses,
            "p2_wrong_guesses": self.p2_wrong_guesses,
            "hints_revealed": self.hints_revealed,
            "revealed_hints": list(self.current_hints[: self.hints_revealed]),
            "potential_points": self.current_potential_points,
            "current_animal": self.current_animal,
        }


# ============================================================================
# 6. SELF-TEST & VERIFICATION SUITE
# ============================================================================


def _run_game_logic_tests() -> None:
    """Comprehensive verification suite for GameDFA, SinglePlayerController, and MultiplayerController."""
    print("=" * 72)
    print("Running game_logic.py Self-Verification Suite...")
    print("=" * 72)

    # 1. Verify GameDFA 5-tuple & Transitions
    dfa = GameDFA()
    assert dfa.current_state == GameState.MAIN_MENU
    assert not dfa.is_accepting()

    # Illegal transition check
    try:
        dfa.trigger(GameEvent.REQUEST_HINT)
        raise AssertionError("Expected InvalidStateTransitionError from MAIN_MENU on REQUEST_HINT")
    except InvalidStateTransitionError:
        pass

    dfa.trigger(GameEvent.SELECT_MODE)
    assert dfa.current_state == GameState.INIT_MODE
    dfa.trigger(GameEvent.ROUND_READY)
    assert dfa.current_state == GameState.GUESSING
    dfa.trigger(GameEvent.REQUEST_HINT)
    assert dfa.current_state == GameState.HINT_REVEAL
    dfa.trigger(GameEvent.RESUME_GUESS)
    assert dfa.current_state == GameState.GUESSING
    dfa.trigger(GameEvent.END_GAME)
    assert dfa.current_state == GameState.GAME_OVER
    assert dfa.is_accepting()
    dfa.reset()
    assert dfa.current_state == GameState.MAIN_MENU
    print("[PASS] GameDFA (Q, Sigma, delta, q0, F) transitions and error guards verified.")

    # 2. Verify SinglePlayerController (Survival rules, hint point decay, 3-strike & timeout life loss)
    sp = SinglePlayerController()
    info = sp.start_game("Survival_Tester")
    assert info["lives"] == 3 and info["score"] == 0
    assert sp.dfa.current_state == GameState.GUESSING
    assert sp.current_potential_points == 100

    # Hint 1 -> 75 pts, Hint 2 -> 50 pts, Hint 3 -> 0 pts
    h1 = sp.reveal_hint()
    assert h1["potential_points"] == 75 and h1["hint_index"] == 1
    h2 = sp.reveal_hint()
    assert h2["potential_points"] == 50 and h2["hint_index"] == 2
    h3 = sp.reveal_hint()
    assert h3["potential_points"] == 0 and h3["can_advance_zero_points"] is True

    # Correct guess at 0 points (3 hints revealed)
    assert sp.current_animal is not None
    res_zero = sp.submit_guess(sp.current_animal.name)
    assert res_zero["correct"] is True and res_zero["points_awarded"] == 0

    # Next animal: test fuzzy guess (1-2 character typo) for 100 points
    next_anim = sp.start_next_animal()
    assert next_anim is not None
    assert sp.current_potential_points == 100
    typo_guess = next_anim.name[:-1] + ("x" if next_anim.name[-1] != "x" else "z")
    res_fuzzy = sp.submit_guess(typo_guess)
    assert res_fuzzy["correct"] is True and res_fuzzy["points_awarded"] == 100
    assert res_fuzzy["edit_distance"] == 1 and sp.score == 100

    # Next animal: test 3 wrong guesses = -1 Life
    sp.start_next_animal()
    for strike in range(1, 4):
        w_res = sp.submit_guess("completely_wrong_species_xyz")
        assert w_res["correct"] is False
        if strike < 3:
            assert w_res["life_lost"] is False and sp.lives == 3
        else:
            assert w_res["life_lost"] is True and sp.lives == 2

    # Next animal: test 30-second timeout = -1 Life
    sp.start_next_animal()
    t_res = sp.tick_timer(30)
    assert t_res["timed_out"] is True and sp.lives == 1

    # Lose final life -> GAME_OVER & Leaderboard/AVL update
    sp.start_next_animal()
    t_over = sp.handle_timeout()
    assert t_over["game_over"] is True and sp.lives == 0
    assert sp.dfa.current_state == GameState.GAME_OVER
    print("[PASS] SinglePlayerController survival mechanics, BFS hints, & Levenshtein NFA verified.")

    # 3. Verify MultiplayerController (10 rounds, 60s timer, Race-Condition Lockout)
    mp = MultiplayerController()
    mp.start_match("Ranger_Alpha", "Ranger_Beta")
    assert mp.current_round == 1 and mp.round_locked is False

    for r in range(1, mp.TOTAL_ROUNDS + 1):
        if r > 1:
            mp.start_next_round()
        assert mp.current_round == r
        assert mp.current_animal is not None

        if r == 1:
            # Player 1 wins the race; Player 2 gets locked out
            target = mp.current_animal.name
            p1_res = mp.submit_guess(1, target)
            assert p1_res["correct"] is True and p1_res["round_winner"] == 1
            assert mp.round_locked is True

            # Player 2 submits right after -> must be locked out!
            p2_res = mp.submit_guess(2, target)
            assert p2_res["locked_out"] is True and p2_res["correct"] is False
        elif r % 2 == 0:
            # Player 2 wins after 1 shared hint (75 pts)
            mp.reveal_shared_hint()
            p2_res = mp.submit_guess(2, mp.current_animal.name)
            assert p2_res["correct"] is True and p2_res["points_awarded"] == 75
        else:
            # Player 1 wins at 100 pts
            p1_res = mp.submit_guess(1, mp.current_animal.name)
            assert p1_res["correct"] is True and p1_res["points_awarded"] == 100

    assert mp.dfa.current_state == GameState.GAME_OVER
    summary = mp.get_match_summary()
    assert summary["p1_score"] > 0 and summary["p2_score"] > 0
    assert mp.bundle.mmr_tree.verify_balance()
    print("[PASS] MultiplayerController 10-round race lockout & AVL/MaxHeap updates verified.")
    print("=" * 72)
    print("ALL GAME LOGIC & AUTOMATA TESTS PASSED SUCCESSFULLY.")
    print("=" * 72)


if __name__ == "__main__":
    _run_game_logic_tests()
