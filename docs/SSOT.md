# Single Source of Truth (SSOT)
## Architecture Status: Locked & Verified (v1.0.0)
## Project: "Who's That Animal?" – Heavy DSA & Automata Desktop Game

### 1. System Overview & Module Boundaries
The system is strictly partitioned into three independent, cohesive Python modules:
- `dsa_engine.py`: [Level 1 Agent] Foundational Data Structures, Taxonomy DAG, Prefix Trie + Levenshtein NFA, Max-Heap Leaderboard, and AVL Tree (MMR).
- `game_logic.py`: [Level 2 Agent] Deterministic Finite Automaton (DFA) State Machine, Single Player Survival rules, and Local Multiplayer Competitive rules with race-condition locking.
- `gui_main.py`: [Level 3 Agent] Dynamic Pillow (PIL) RGBA silhouette asset generator, procedural high-realism animal sprite generator (supersampled anatomical rendering with shading, fur/scale/feather textures, and crisp silhouettes), Tkinter Event-Driven GUI with `.after()` non-blocking timers, and **Multiplayer Room & Shareable Link Server** (built-in HTTP + JSON Room Server allowing the host to create a room, copy a shareable browser/app room link `http://<ip>:<port>/room/<ROOM_CODE>`, and play live 1v1 against any friend who opens the link or joins via the Tkinter app).

---

### 2. Data Contracts & Class Interfaces

#### Module 1: `dsa_engine.py`
1. **`AnimalRecord` (Dataclass / Dict structure)**:
   - `name: str` (lowercase canonical name, e.g., `"african elephant"`)
   - `display_name: str` (e.g., `"African Elephant"`)
   - `kingdom: str` (e.g., `"Animalia"`)
   - `animal_class: str` (Hint 1, e.g., `"Mammalia"`)
   - `order: str` (e.g., `"Proboscidea"`)
   - `region: str` (Hint 2: Region/Habitat, e.g., `"Sub-Saharan African Savannas & Forests"`)
   - `trait: str` (Hint 3: Specific Trait, e.g., `"Largest land animal with prehensile trunk and ivory tusks"`)
   - `image_path: str` (path to transparent PNG asset in `assets/animals/<slug>.png`)

2. **`TaxonomyDAG`**:
   - Stores nodes (`Kingdom -> Class -> Order -> Animal`) as a Directed Acyclic Graph using adjacency lists (`dict[str, list[str]]`) and metadata maps.
   - `add_edge(u: str, v: str) -> None`: Adds directed edge with cycle detection guard.
   - `add_animal(record: AnimalRecord) -> None`: Populates `Kingdom -> Class -> Order -> Animal` path in the DAG.
   - `bfs_generate_hints(animal_name: str) -> list[str]`: Performs Breadth-First Search (BFS) starting from `"Kingdom:Animalia"` down through `Class` and `Order` to locate the target animal and dynamically construct the ordered 3-hint tuple:
     - `Hint 1`: Taxonomic Class & Order (traversed via BFS path: `Kingdom -> Class -> Order`)
     - `Hint 2`: Region / Habitat (`record.region`)
     - `Hint 3`: Specific Diagnostic Trait (`record.trait`)
   - `get_all_animals() -> list[AnimalRecord]`

3. **`PrefixTrie` & `LevenshteinAutomaton`**:
   - `TrieNode`: `children: dict[str, TrieNode]`, `is_end: bool`, `word: Optional[str]`.
   - `PrefixTrie`:
     - `insert(word: str) -> None`
     - `search_exact(word: str) -> bool`
   - `LevenshteinAutomaton`:
     - Constructs a Levenshtein Non-Deterministic Finite Automaton (NFA) / vectorized dynamic NFA state simulator for a query pattern $P$ of length $m$ with maximum edit distance $k \in \{1, 2\}$.
     - `fuzzy_match(query: str, trie: PrefixTrie, max_dist: int = 2) -> tuple[bool, Optional[str], int]`: Simultaneously steps the Levenshtein NFA and traverses the `PrefixTrie` via DFS pruning branches where minimum edit distance $> k$. Achieves $O(m)$ state transitions per active trie node.
     - `matches_target(query: str, target: str, max_dist: int = 2) -> tuple[bool, int]`: Evaluates whether `query` matches `target` within `max_dist` typos using the Levenshtein NFA intersected with a mini-Trie/target path.

4. **`MaxHeapLeaderboard`**:
   - Array-backed binary Max-Heap storing `(score: int, timestamp: float, player_name: str)` entries.
   - `insert(player_name: str, score: int) -> None`: $O(\log n)$ bubble-up (`_sift_up`).
   - `get_top() -> Optional[tuple[str, int]]`: $O(1)$ retrieval of top player (`heap[0]`).
   - `extract_max() -> Optional[tuple[str, int]]`: $O(\log n)$ removal with `_sift_down`.
   - `get_top_k(k: int = 10) -> list[tuple[str, int]]`: Returns sorted top $k$ entries without mutating heap state.

5. **`AVLTreeMMR`**:
   - Self-balancing Binary Search Tree keyed by `(mmr_score: int, player_id: str)`.
   - `AVLNode`: `player_id: str`, `mmr: int`, `wins: int`, `games: int`, `height: int`, `left`, `right`.
   - Explicit rotations: `_rotate_left(z)` (RR case), `_rotate_right(z)` (LL case), plus LR (`left` then `right`) and RL (`right` then `left`) rebalance operations.
   - `upsert_player(player_id: str, mmr: int, wins: int = 0, games: int = 0) -> None`
   - `find_closest_match(target_mmr: int, exclude_player: Optional[str] = None) -> Optional[dict]`
   - `inorder_rankings() -> list[dict]`

---

#### Module 2: `game_logic.py`
1. **`GameState` (Enum / Constants)**:
   - `MAIN_MENU = "MAIN_MENU"`
   - `INIT_MODE = "INIT_MODE"`
   - `GUESSING = "GUESSING"`
   - `HINT_REVEAL = "HINT_REVEAL"`
   - `GAME_OVER = "GAME_OVER"`

2. **`GameDFA`**:
   - Formal DFA definition $(Q, \Sigma, \delta, q_0, F)$:
     - $Q = \{\text{MAIN\_MENU}, \text{INIT\_MODE}, \text{GUESSING}, \text{HINT\_REVEAL}, \text{GAME\_OVER}\}$
     - $\Sigma = \{\text{SELECT\_MODE}, \text{ROUND\_READY}, \text{REQUEST\_HINT}, \text{RESUME\_GUESS}, \text{NEXT\_ROUND}, \text{END\_GAME}, \text{RESTART}\}$
     - $\delta$: Strict transition table mapping $(q, \sigma) \mapsto q'$. Raises `InvalidStateTransitionError` on illegal transitions.
   - `trigger(event: str) -> str`: Executes transition and notifies registered callbacks.

3. **`SinglePlayerController`**:
   - Uses `GameDFA`, `TaxonomyDAG`, `PrefixTrie`, `LevenshteinAutomaton`, `MaxHeapLeaderboard`, `AVLTreeMMR`.
   - Initial state: `lives = 3`, `score = 0`, `round_timer = 30`, `hints_used = 0`, `wrong_guesses_on_current = 0`.
   - Reward schedule based on `hints_used`:
     - `0 hints`: `100` points
     - `1 hint` (Class/Order): `75` points
     - `2 hints` (Region): `50` points
     - `3 hints` (Strong Trait): `0` points (player advances or guesses for 0 pts)
   - Life penalty rules:
     - 3 incorrect guesses on one animal OR 30-second timer expiration $\implies -1$ Life.
     - Game transitions to `GAME_OVER` when `lives <= 0` or all animals are exhausted.

4. **`MultiplayerController`**:
   - Uses `GameDFA`, `TaxonomyDAG`, `PrefixTrie`, `LevenshteinAutomaton`, `AVLTreeMMR`.
   - 10 continuous rounds, `round_timer = 60` seconds per round.
   - Tracks `p1_score`, `p2_score`, `current_round` (1 to 10), `round_locked: bool` (mutex/lockout flag for race-condition protection).
   - `submit_guess(player_num: int, raw_guess: str) -> dict`:
     - Checks `round_locked` and DFA state `GUESSING` or `HINT_REVEAL`.
     - If unlocked and fuzzy-matched via `LevenshteinAutomaton` (1-2 typo tolerance), atomically sets `round_locked = True`, awards points to `player_num`, locks out the other player for the current animal, and signals round completion.

---

#### Module 3: `gui_main.py`
1. **`SilhouetteGenerator` (Pillow / PIL)**:
   - Ensures transparent PNG animal sprites exist in `assets/animals/` (auto-generates rich, recognizable multi-part RGBA vector-drawn PNG sprites for 15+ animals on first launch if missing, plus supports any custom PNG dropped into `assets/animals/`).
   - `create_silhouette(png_path: str, size: tuple[int, int]) -> Image.Image`:
     - Loads RGBA PNG via `Image.open(png_path).convert("RGBA")`.
     - Iterates through the alpha channel at runtime: converts every non-transparent pixel ($\alpha > 0$) to solid black `(0, 0, 0, alpha)` (`#000000`) while keeping transparent pixels `(0, 0, 0, 0)`. Never uses pre-made shadow files.
   - `load_revealed(png_path: str, size: tuple[int, int]) -> Image.Image`: Returns the full-color resized RGBA image for round reveal.

2. **`WhosThatAnimalApp` (Tkinter GUI)**:
   - Uses both `pack()` and `grid()` geometry managers cleanly.
   - **Main Menu Screen (`MAIN_MENU`)**: Mode selection (Single Player Survival, Multiplayer Competitive Split-Screen), High Score Leaderboard (from `MaxHeapLeaderboard`), and AVL MMR Matchmaking Rankings table.
   - **Single Player UI (`GUESSING` / `HINT_REVEAL`)**:
     - Header HUD (`grid`): Score, Lives (`❤ x 3`), 30s Countdown Timer, DFA State badge, Potential Points indicator.
     - Central Canvas: Renders the runtime-generated black silhouette (`#000000`), switching to the full-color animal sprite on reveal.
     - Hint Panel: Displays revealed hints (Hint 1: Class, Hint 2: Region, Hint 3: Specific Trait) and a `"Reveal Next Hint"` button (triggers DFA `GUESSING -> HINT_REVEAL -> GUESSING`).
     - Input Bar: Single `tk.Entry` bound to `<Return>` key for instant fuzzy-matched submission.
   - **Multiplayer Split-Screen UI (`GUESSING` / `HINT_REVEAL`)**:
     - Vertically split layout (`grid` with 3 columns: Left = Player 1 Station, Center = Shared Silhouette Canvas + 60s Timer + Shared Hints + Round `X/10`, Right = Player 2 Station).
     - Independent `tk.Entry` widgets: Player 1 Entry on the left (bound to `<Return>`) and Player 2 Entry on the right (bound to `<Return>`), with lockout visual feedback when the opponent wins the race condition.
   - **Non-Blocking Timers**:
     - Uses `root.after(1000, ...)` exclusively for the 30-second (Single Player) and 60-second (Multiplayer) countdowns, properly canceling scheduled timer IDs via `after_cancel` on round transitions.
