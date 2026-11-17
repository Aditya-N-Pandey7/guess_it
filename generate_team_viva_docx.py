"""
Generates a complete, detailed Microsoft Word (.docx) document covering the
ENTIRE project divided equally among 3 Team Members:
  - Member 1: Core DSA & Data Architect (`dsa_engine.py`)
  - Member 2: Automata & Game Logic Engineer (`game_logic.py`)
  - Member 3: UI/UX, Pillow Graphics & Multiplayer Room Server Engineer (`gui_main.py`)
  - Plus Frontend-Only Sub-Division (`gui_main.py`) for when all 3 members are asked about UI.

Includes:
  1. Who did what work (detailed responsibilities)
  2. Exact File, Class, Function & Line Number Code References to open and show the teacher
  3. Word-for-Word Presentation Scripts (what each member should say to the teacher)
  4. Viva / Evaluation Questions & Answers for each member
"""

import os
import zipfile
from xml.sax.saxutils import escape


def _xml_text(text: str) -> str:
    return escape(text, {'"': "&quot;", "'": "&apos;"})


def make_heading(text: str, level: int = 1) -> str:
    sizes = {1: "36", 2: "28", 3: "23"}
    colors = {1: "0F172A", 2: "0284C7", 3: "0D9488"}
    space_before = {1: "280", 2: "240", 3: "180"}
    space_after = {1: "120", 2: "90", 3: "60"}
    sz = sizes.get(level, "24")
    col = colors.get(level, "0F172A")
    sb = space_before.get(level, "160")
    sa = space_after.get(level, "60")
    border_xml = ""
    if level in (1, 2):
        border_xml = (
            f'<w:pBdr><w:bottom w:val="single" w:sz="{8 if level == 1 else 4}" '
            f'w:space="4" w:color="{col}"/></w:pBdr>'
        )
    return f"""
    <w:p>
      <w:pPr>
        <w:spacing w:before="{sb}" w:after="{sa}"/>
        {border_xml}
      </w:pPr>
      <w:r>
        <w:rPr>
          <w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:cs="Calibri"/>
          <w:b/>
          <w:color w:val="{col}"/>
          <w:sz w:val="{sz}"/>
          <w:szCs w:val="{sz}"/>
        </w:rPr>
        <w:t>{_xml_text(text)}</w:t>
      </w:r>
    </w:p>"""


def make_paragraph(text: str, bold_prefix: str = "", italic: bool = False) -> str:
    runs = []
    if bold_prefix:
        runs.append(f"""
        <w:r>
          <w:rPr>
            <w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/>
            <w:b/>
            <w:color w:val="0F172A"/>
            <w:sz w:val="21"/>
          </w:rPr>
          <w:t xml:space="preserve">{_xml_text(bold_prefix)}</w:t>
        </w:r>""")
    i_tag = "<w:i/>" if italic else ""
    runs.append(f"""
    <w:r>
      <w:rPr>
        <w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/>
        {i_tag}
        <w:color w:val="1E293B"/>
        <w:sz w:val="21"/>
      </w:rPr>
      <w:t xml:space="preserve">{_xml_text(text)}</w:t>
    </w:r>""")
    return f"""
    <w:p>
      <w:pPr><w:spacing w:before="60" w:after="80" w:line="276" w:lineRule="auto"/></w:pPr>
      {''.join(runs)}
    </w:p>"""


def make_quote_box(title: str, script_text: str) -> str:
    return f"""
    <w:p>
      <w:pPr>
        <w:pBdr>
          <w:left w:val="single" w:sz="18" w:space="12" w:color="0284C7"/>
        </w:pBdr>
        <w:shd w:val="clear" w:color="auto" w:fill="F1F5F9"/>
        <w:ind w:left="360" w:right="240"/>
        <w:spacing w:before="100" w:after="120" w:line="276" w:lineRule="auto"/>
      </w:pPr>
      <w:r>
        <w:rPr>
          <w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/>
          <w:b/>
          <w:color w:val="0284C7"/>
          <w:sz w:val="21"/>
        </w:rPr>
        <w:t xml:space="preserve">{_xml_text(title + ": ")}</w:t>
      </w:r>
      <w:r>
        <w:rPr>
          <w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/>
          <w:i/>
          <w:color w:val="0F172A"/>
          <w:sz w:val="21"/>
        </w:rPr>
        <w:t xml:space="preserve">{_xml_text(script_text)}</w:t>
      </w:r>
    </w:p>"""


def make_bullet(bold_prefix: str, text: str) -> str:
    return f"""
    <w:p>
      <w:pPr>
        <w:ind w:left="420" w:hanging="240"/>
        <w:spacing w:before="40" w:after="50" w:line="260" w:lineRule="auto"/>
      </w:pPr>
      <w:r>
        <w:rPr>
          <w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/>
          <w:b/>
          <w:color w:val="0284C7"/>
          <w:sz w:val="21"/>
        </w:rPr>
        <w:t xml:space="preserve">• {_xml_text(bold_prefix)}</w:t>
      </w:r>
      <w:r>
        <w:rPr>
          <w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/>
          <w:color w:val="1E293B"/>
          <w:sz w:val="21"/>
        </w:rPr>
        <w:t xml:space="preserve">{_xml_text(text)}</w:t>
      </w:r>
    </w:p>"""


def make_qa(q_num: int, question: str, answer: str) -> str:
    return (
        make_paragraph(question, bold_prefix=f"Q{q_num}: ")
        + make_paragraph(answer, bold_prefix="Answer: ")
    )


def make_table(headers: list[str], rows: list[list[str]], col_widths: list[int]) -> str:
    grid_cols = "".join(f'<w:gridCol w:w="{w}"/>' for w in col_widths)
    header_cells = []
    for h_text, w in zip(headers, col_widths):
        header_cells.append(f"""
        <w:tc>
          <w:tcPr>
            <w:tcW w:w="{w}" w:type="dxa"/>
            <w:shd w:val="clear" w:color="auto" w:fill="0F172A"/>
            <w:tcMar>
              <w:top w:w="100" w:type="dxa"/>
              <w:bottom w:w="100" w:type="dxa"/>
              <w:left w:w="120" w:type="dxa"/>
              <w:right w:w="120" w:type="dxa"/>
            </w:tcMar>
          </w:tcPr>
          <w:p>
            <w:pPr><w:spacing w:before="20" w:after="20"/></w:pPr>
            <w:r>
              <w:rPr>
                <w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/>
                <w:b/>
                <w:color w:val="FFFFFF"/>
                <w:sz w:val="20"/>
              </w:rPr>
              <w:t>{_xml_text(h_text)}</w:t>
            </w:r>
          </w:p>
        </w:tc>""")

    body_rows = []
    for r_idx, row in enumerate(rows):
        bg_fill = "F8FAFC" if r_idx % 2 == 1 else "FFFFFF"
        cells = []
        for c_idx, (cell_text, w) in enumerate(zip(row, col_widths)):
            is_first_col = c_idx == 0
            b_tag = "<w:b/>" if is_first_col else ""
            col_val = "0F172A" if is_first_col else "1E293B"
            cells.append(f"""
            <w:tc>
              <w:tcPr>
                <w:tcW w:w="{w}" w:type="dxa"/>
                <w:shd w:val="clear" w:color="auto" w:fill="{bg_fill}"/>
                <w:tcMar>
                  <w:top w:w="85" w:type="dxa"/>
                  <w:bottom w:w="85" w:type="dxa"/>
                  <w:left w:w="120" w:type="dxa"/>
                  <w:right w:w="120" w:type="dxa"/>
                </w:tcMar>
              </w:tcPr>
              <w:p>
                <w:pPr><w:spacing w:before="20" w:after="20"/></w:pPr>
                <w:r>
                  <w:rPr>
                    <w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/>
                    {b_tag}
                    <w:color w:val="{col_val}"/>
                    <w:sz w:val="19"/>
                  </w:rPr>
                  <w:t xml:space="preserve">{_xml_text(cell_text)}</w:t>
                </w:r>
              </w:p>
            </w:tc>""")
        body_rows.append(f"<w:tr>{''.join(cells)}</w:tr>")

    return f"""
    <w:tbl>
      <w:tblPr>
        <w:tblW w:w="{sum(col_widths)}" w:type="dxa"/>
        <w:tblBorders>
          <w:top w:val="single" w:sz="6" w:space="0" w:color="CBD5E1"/>
          <w:left w:val="single" w:sz="6" w:space="0" w:color="CBD5E1"/>
          <w:bottom w:val="single" w:sz="6" w:space="0" w:color="CBD5E1"/>
          <w:right w:val="single" w:sz="6" w:space="0" w:color="CBD5E1"/>
          <w:insideH w:val="single" w:sz="4" w:space="0" w:color="E2E8F0"/>
          <w:insideV w:val="single" w:sz="4" w:space="0" w:color="E2E8F0"/>
        </w:tblBorders>
      </w:tblPr>
      <w:tblGrid>{grid_cols}</w:tblGrid>
      <w:tr>{''.join(header_cells)}</w:tr>
      {''.join(body_rows)}
    </w:tbl>
    <w:p><w:pPr><w:spacing w:before="40" w:after="60"/></w:pPr></w:p>"""


def build_team_division_docx(output_path: str) -> None:
    parts: list[str] = []

    # Main Title
    parts.append(
        make_heading(
            "WHO'S THAT ANIMAL? — Complete 3-Member Team Work Division, Code Reference Map, Teacher Presentation Scripts & Viva Q&A",
            1,
        )
    )
    parts.append(
        make_paragraph(
            "This master guide divides the entire project equally across 3 Team Members, specifies exact file names, "
            "classes, methods, and line numbers to show the teacher during code review, provides word-for-word speaking "
            "scripts for each member, and lists expected Viva questions & answers (including a bonus Frontend-Only split).",
            italic=True,
        )
    )

    # =========================================================================
    # OVERVIEW TABLE: WHOLE PROJECT 3-MEMBER DIVISION
    # =========================================================================
    parts.append(make_heading("1. MASTER OVERVIEW: WHOLE-PROJECT 3-MEMBER DIVISION", 2))
    parts.append(
        make_table(
            headers=["Team Member", "Role & Tier", "Primary File Owned", "Core Modules & Concepts Built"],
            rows=[
                [
                    "Member 1",
                    "Level 1: Core DSA & Data Architect",
                    "dsa_engine.py (Lines 1–1314)",
                    "1. AnimalRecord & 16-species Dataset\n2. TaxonomyDAG (DFS Cycle Guard + BFS Clue Generator)\n3. PrefixTrie + LevenshteinAutomaton (NFA Fuzzy Matching)\n4. MaxHeapLeaderboard (O(1) Top / O(log n) Sift)\n5. AVLTreeMMR (LL/RR/LR/RL Rotations & Matchmaking)",
                ],
                [
                    "Member 2",
                    "Level 2: Automata & Game Logic Engineer",
                    "game_logic.py (Lines 1–1689)",
                    "1. Formal 5-Tuple GameDFA State Machine (Q, Sigma, delta, q0, F)\n2. Difficulty Scaling Engine (Easy, Medium, Difficult)\n3. SinglePlayerController (Lives, 3-Strike Rule, Point Decay)\n4. MultiplayerController (10 Rounds, threading.Lock Race Lockout)",
                ],
                [
                    "Member 3",
                    "Level 3: UI/UX, PIL Graphics & Room Server Engineer",
                    "gui_main.py (Lines 1–4265)",
                    "1. SilhouetteGenerator (2x Supersampled PIL Sprites + Runtime RGBA->#000000 Alpha Iteration)\n2. WhosThatAnimalGUI (Event-Driven Tkinter pack/grid + Non-Blocking .after() Timers)\n3. MultiplayerRoomServer (Shareable Room Link HTTP/REST Server & HTML5/JS Web Client)",
                ],
            ],
            col_widths=[1300, 2100, 1900, 4300],
        )
    )

    # =========================================================================
    # MEMBER 1: CORE DSA & DATA ARCHITECT (`dsa_engine.py`)
    # =========================================================================
    parts.append(make_heading("2. MEMBER 1: CORE DSA & DATA ARCHITECT (dsa_engine.py)", 2))

    parts.append(make_heading("2.1 Detailed Work Done by Member 1", 3))
    parts.append(
        make_bullet(
            "Animal Database & Taxonomic Schema: ",
            "Created the AnimalRecord dataclass and populated 16 vertebrate species across Mammalia, Aves, Reptilia, Amphibia, Actinopterygii, and Chondrichthyes with difficulty levels (EASY, MEDIUM, HARD), short aliases, regions, and traits.",
        )
    )
    parts.append(
        make_bullet(
            "Taxonomy Directed Acyclic Graph (DAG) & Breadth-First Search (BFS): ",
            "Implemented TaxonomyDAG with adjacency lists (Kingdom -> Class -> Order -> Animal), DFS cycle detection (_creates_cycle), and BFS traversal (bfs_lineage_path & bfs_generate_hints) using collections.deque to dynamically generate the 3 clues.",
        )
    )
    parts.append(
        make_bullet(
            "Prefix Trie & Levenshtein NFA (Typo-Tolerant Fuzzy Search): ",
            "Implemented PrefixTrie and LevenshteinAutomaton (LevenshteinNFAInstance) to intersect the NFA state vector with the Trie via DFS branch pruning, accepting 1-to-2 character spelling mistakes in O(m) time per transition.",
        )
    )
    parts.append(
        make_bullet(
            "Binary Max-Heap Leaderboard: ",
            "Implemented MaxHeapLeaderboard from scratch over a Python list using _sift_up and _sift_down (without heapq) for O(1) top champion peek and O(log n) score insertion.",
        )
    )
    parts.append(
        make_bullet(
            "Self-Balancing AVL Tree for MMR Rankings: ",
            "Implemented AVLTreeMMR with explicit LL (_rotate_right), RR (_rotate_left), LR, and RL rotations to maintain |balance_factor| <= 1, Elo rating updates, and O(log n) closest-opponent search (find_closest_match).",
        )
    )

    parts.append(make_heading("2.2 Exact Code Reference Map for Member 1 (Open dsa_engine.py)", 3))
    parts.append(
        make_table(
            headers=["Concept to Show Teacher", "File Name", "Class / Function Name", "Exact Lines"],
            rows=[
                ["Animal Schema & 16-Animal Dataset", "dsa_engine.py", "AnimalRecord & get_default_animal_dataset()", "Lines 24 – 242"],
                ["Taxonomy DAG & DFS Cycle Detection", "dsa_engine.py", "TaxonomyDAG._creates_cycle() & add_edge()", "Lines 253 – 315"],
                ["BFS Lineage & Dynamic 3-Clue Generator", "dsa_engine.py", "TaxonomyDAG.bfs_lineage_path() & bfs_generate_hints()", "Lines 357 – 416"],
                ["Prefix Tree (Trie) Implementation", "dsa_engine.py", "TrieNode & PrefixTrie (insert, search_exact)", "Lines 423 – 492"],
                ["Levenshtein NFA + Trie DFS Intersection", "dsa_engine.py", "LevenshteinNFAInstance & LevenshteinAutomaton.fuzzy_search_trie()", "Lines 495 – 744"],
                ["Binary Max-Heap Priority Queue", "dsa_engine.py", "MaxHeapLeaderboard (_sift_up, _sift_down, insert, get_top)", "Lines 747 – 887"],
                ["Self-Balancing AVL Tree (LL/RR/LR/RL)", "dsa_engine.py", "AVLNode & AVLTreeMMR (_rotate_right, _rotate_left, _rebalance, find_closest_match)", "Lines 893 – 1224"],
            ],
            col_widths=[2500, 1500, 3800, 1800],
        )
    )

    parts.append(make_heading("2.3 Word-for-Word Explanation to Give the Teacher (Member 1)", 3))
    parts.append(
        make_quote_box(
            "What Member 1 Should Say to the Teacher",
            '"Ma\'am/Sir, I designed and implemented the Core Data Structures and Algorithmic Engine in dsa_engine.py. First, I built a Directed Acyclic Graph (TaxonomyDAG, Lines 253–416) that stores our animal database in a biological hierarchy: Kingdom -> Class -> Order -> Animal. Before adding any directed edge, _creates_cycle() runs Depth-First Search to prevent cycles. During gameplay, bfs_generate_hints() runs Breadth-First Search using a FIFO queue (collections.deque) from Kingdom:Animalia to dynamically generate the 3 progressive clues.\n\nSecond, for forgiving player spelling mistakes, I implemented a Prefix Trie combined with a Levenshtein Non-Deterministic Finite Automaton (Lines 423–744). When a player types a guess like \'elephnt\', fuzzy_search_trie() steps the Levenshtein NFA simultaneously alongside a DFS traversal of the Prefix Trie, pruning any branch where minimum edit distance exceeds k (k=2 on Easy/Medium, k=1 on Difficult).\n\nThird, for the High Scores table, I built a custom array-backed Binary Max-Heap (MaxHeapLeaderboard, Lines 747–887) from scratch using _sift_up and _sift_down, giving O(1) retrieval of the top champion and O(log n) insertion. Finally, for player skill ratings and matchmaking, I built a Self-Balancing AVL Tree (AVLTreeMMR, Lines 893–1224) with explicit LL, RR, LR, and RL tree rotations so every lookup and update runs in strict O(log n) time."',
        )
    )

    parts.append(make_heading("2.4 Viva Questions & Answers for Member 1", 3))
    parts.append(
        make_qa(
            1,
            "Why did you use a Directed Acyclic Graph (DAG) and Breadth-First Search (BFS) for generating clues?",
            "Biological taxonomy forms a hierarchical directed structure (Kingdom -> Class -> Order -> Species). BFS explores the graph level-by-level using a FIFO queue (collections.deque), which naturally visits the broad Taxonomic Class & Order first (Clue 1) before reaching the specific leaf animal's Habitat (Clue 2) and Diagnostic Trait (Clue 3). Time complexity is O(V + E).",
        )
    )
    parts.append(
        make_qa(
            2,
            "How does combining a Prefix Trie with a Levenshtein Automaton improve fuzzy string matching?",
            "Running standard dynamic-programming edit distance against N separate words takes O(N * m * L) time. By storing all valid names and aliases in a Prefix Trie, shared prefixes are evaluated only once, and any Trie subtree whose minimum active NFA edit distance exceeds max_dist (1 or 2) is immediately pruned.",
        )
    )
    parts.append(
        make_qa(
            3,
            "How did you implement the Max-Heap without using Python's built-in heapq module?",
            "Python's heapq only provides a Min-Heap. In MaxHeapLeaderboard (Lines 747–887), we maintain a 0-indexed list where for any index i, parent is (i-1)//2, left child is 2i+1, and right child is 2i+2. On insert(), we append to the end and call _sift_up() in O(log n). The highest score is always at self._heap[0] in O(1) time.",
        )
    )
    parts.append(
        make_qa(
            4,
            "Why did you use an AVL Tree instead of a normal Binary Search Tree (BST) for player MMR ratings?",
            "If players are inserted in sorted order of rating, a normal BST degenerates into a skewed linked list with O(n) search time. Our AVLTreeMMR computes balance_factor = height(left) - height(right) at every node after insertion/deletion and performs LL, RR, LR, or RL rotations whenever |balance_factor| > 1, guaranteeing O(log n) height.",
        )
    )

    # =========================================================================
    # MEMBER 2: AUTOMATA & GAME LOGIC ENGINEER (`game_logic.py`)
    # =========================================================================
    parts.append(make_heading("3. MEMBER 2: AUTOMATA & GAME LOGIC ENGINEER (game_logic.py)", 2))

    parts.append(make_heading("3.1 Detailed Work Done by Member 2", 3))
    parts.append(
        make_bullet(
            "Formal Deterministic Finite Automaton (GameDFA): ",
            "Engineered the 5-tuple DFA state machine M = (Q, Sigma, delta, q0, F) with 5 states (MAIN_MENU, INIT_MODE, GUESSING, HINT_REVEAL, GAME_OVER) and 7 input events (SELECT_MODE, ROUND_READY, REQUEST_HINT, RESUME_GUESS, NEXT_ROUND, END_GAME, RESTART). Enforces O(1) hash-table transitions and raises InvalidStateTransitionError on illegal transitions.",
        )
    )
    parts.append(
        make_bullet(
            "Three-Level Difficulty Engine (Easy, Medium, Difficult): ",
            "Implemented DIFFICULTY_CONFIG across both Single Player and Multiplayer controllers to dynamically adjust lives (4/3/2), countdown timers (45s/30s/20s and 75s/60s/40s), free starting clues on Easy, Levenshtein typo strictness (max_dist=2 vs. 1), and difficulty-ordered animal decks.",
        )
    )
    parts.append(
        make_bullet(
            "Single Player Survival Controller (SinglePlayerController): ",
            "Implemented survival rules: 3 wrong guesses on one animal = -1 Life, timer reaching 0s = -1 Life, progressive clue point decay (100 -> 75 -> 50 -> 0 pts), 0-point skip after Clue 3, and automatic Game Over persistence to the Max-Heap Leaderboard and AVL Tree.",
        )
    )
    parts.append(
        make_bullet(
            "Multiplayer Competitive Controller & Thread-Safe Race Lockout (MultiplayerController): ",
            "Implemented the 10-round continuous match engine and atomic race-condition lockout using threading.Lock (_race_lock) + round_locked boolean so the first player to submit a valid fuzzy-matched guess locks out the opponent and claims the round's points.",
        )
    )

    parts.append(make_heading("3.2 Exact Code Reference Map for Member 2 (Open game_logic.py)", 3))
    parts.append(
        make_table(
            headers=["Concept to Show Teacher", "File Name", "Class / Function Name", "Exact Lines"],
            rows=[
                ["Formal States (Q) & Alphabet (Sigma) Enums", "game_logic.py", "GameState, GameEvent, InvalidStateTransitionError", "Lines 42 – 89"],
                ["5-Tuple DFA State Machine & Transition Table", "game_logic.py", "GameDFA (TRANSITION_TABLE, trigger, can_transition)", "Lines 96 – 237"],
                ["Guess Normalization & NFA/Trie Bridge", "game_logic.py", "_normalize_guess() & _evaluate_animal_guess()", "Lines 313 – 373"],
                ["Single Player Difficulty & Survival Rules", "game_logic.py", "SinglePlayerController (DIFFICULTY_CONFIG, start_game, start_next_animal)", "Lines 380 – 585"],
                ["Hint Point Decay (100 -> 75 -> 50 -> 0 pts)", "game_logic.py", "SinglePlayerController.reveal_hint() & skip_after_all_hints()", "Lines 587 – 668"],
                ["3-Strike Mistake & Timeout Life Deduction", "game_logic.py", "SinglePlayerController.submit_guess() & handle_timeout()", "Lines 670 – 845"],
                ["Multiplayer 10-Round Engine & Mutex Lockout", "game_logic.py", "MultiplayerController (start_match, submit_guess with self._race_lock)", "Lines 925 – 1345"],
            ],
            col_widths=[2500, 1500, 3800, 1800],
        )
    )

    parts.append(make_heading("3.3 Word-for-Word Explanation to Give the Teacher (Member 2)", 3))
    parts.append(
        make_quote_box(
            "What Member 2 Should Say to the Teacher",
            '"Ma\'am/Sir, I designed and implemented the Automata State Machine and Game Logic Layer in game_logic.py. At the heart of my module is GameDFA (Lines 96–237), a formal Deterministic Finite Automaton defined as the 5-tuple (Q, Sigma, delta, q0, F). Q has 5 states: MAIN_MENU, INIT_MODE, GUESSING, HINT_REVEAL, and GAME_OVER. Sigma has 7 events, and delta is an O(1) dictionary transition table. Every action in the game—starting a mode, revealing a clue, advancing to the next animal, or ending the game—must pass through GameDFA.trigger(), which prevents any invalid state jump.\n\nOn top of the DFA, I built SinglePlayerController (Lines 380–918) and MultiplayerController (Lines 925–1460) with 3 Difficulty Levels (Easy, Medium, and Difficult). In Single Player, players start with 4, 3, or 2 lives; revealing clues drops the reward from 100 -> 75 -> 50 -> 0 points, and making 3 wrong guesses or letting the timer expire deducts 1 life.\n\nIn Multiplayer, 2 players compete over 10 continuous rounds. Because both players (either on split-screen or over the network link) can press Enter at the exact same millisecond, I implemented a thread-safe race-condition lockout in MultiplayerController.submit_guess() (Lines 1185–1345) using Python\'s threading.Lock (self._race_lock). The first player whose guess is accepted by the Levenshtein NFA atomically sets self.round_locked = True, scores the points, and locks out the second player for that round."',
        )
    )

    parts.append(make_heading("3.4 Viva Questions & Answers for Member 2", 3))
    parts.append(
        make_qa(
            1,
            "What is the formal 5-tuple definition of your GameDFA and why is a DFA better than simple boolean flags?",
            "Our DFA is M = (Q, Sigma, delta, q0, F) where Q is the set of 5 states, Sigma is the set of 7 input events, delta: Q x Sigma -> Q is the transition table (Lines 115–138), q0 = MAIN_MENU, and F = {GAME_OVER}. Unlike scattered boolean flags (which can enter contradictory states like game_over=True while guessing=True), a DFA guarantees the game is in exactly one valid state at any instant.",
        )
    )
    parts.append(
        make_qa(
            2,
            "What happens inside the DFA when a player clicks 'Reveal Clue'?",
            "The controller calls self.dfa.trigger(GameEvent.REQUEST_HINT), which transitions the DFA from GUESSING -> HINT_REVEAL, increments hints_revealed, fetches the next BFS clue, and immediately triggers GameEvent.RESUME_GUESS to transition HINT_REVEAL -> GUESSING.",
        )
    )
    parts.append(
        make_qa(
            3,
            "How did you handle the race condition in Multiplayer when both players submit an answer at the same time?",
            "In MultiplayerController.submit_guess() (Lines 1209–1325), the entire evaluation block is wrapped inside 'with self._race_lock:' (a threading.Lock mutex). The first thread to enter checks if self.round_locked is False; if its guess is valid, it sets self.round_locked = True before releasing the lock. The second thread waiting on the lock immediately sees self.round_locked == True and receives locked_out = True.",
        )
    )
    parts.append(
        make_qa(
            4,
            "How do the Easy, Medium, and Difficult levels change the game logic?",
            "DIFFICULTY_CONFIG (Lines 413–417 and 959–963) adjusts 5 parameters: (1) Starting lives (4, 3, or 2), (2) Countdown timer (45s/30s/20s in Single Player; 75s/60s/40s in Multiplayer), (3) Auto-unlocking Clue 1 for free on Easy while keeping the reward at 100 pts, (4) Levenshtein edit distance tolerance (k=2 on Easy/Medium vs. k=1 on Difficult), and (5) Ordering the animal deck by difficulty tier.",
        )
    )

    # =========================================================================
    # MEMBER 3: UI/UX, PIL GRAPHICS & MULTIPLAYER ROOM SERVER (`gui_main.py`)
    # =========================================================================
    parts.append(
        make_heading(
            "4. MEMBER 3: UI/UX, PILLOW GRAPHICS & MULTIPLAYER ROOM SERVER ENGINEER (gui_main.py)",
            2,
        )
    )

    parts.append(make_heading("4.1 Detailed Work Done by Member 3", 3))
    parts.append(
        make_bullet(
            "Runtime Alpha-Channel Silhouette Processor (Pillow / PIL): ",
            "Implemented SilhouetteGenerator.generate_silhouette_from_png() which loads standard transparent RGBA PNGs at runtime, loops over every (x, y) pixel, and converts all non-transparent pixels (a > 0) to solid black (0, 0, 0, a) (#000000) while keeping transparent pixels (0, 0, 0, 0)—never using pre-made shadow files.",
        )
    )
    parts.append(
        make_bullet(
            "2x Supersampled Realistic Wildlife Sprite Generator: ",
            "Implemented SilhouetteGenerator._draw_animal_sprite() using 640x640 supersampling, Catmull-Rom splines (_catmull_rom_spline), tapered strokes, and Lanczos downsampling (320x320) to generate 17 realistic animal PNGs.",
        )
    )
    parts.append(
        make_bullet(
            "Clean Event-Driven Tkinter Desktop GUI & Non-Blocking Timers: ",
            "Built WhosThatAnimalGUI combining pack() and grid() geometry managers across the Main Menu, Single Player view, 3-Column Split-Screen Multiplayer view, and Game Over modal, with <Return> key bindings and non-blocking root.after(1000, ...) countdown timers.",
        )
    )
    parts.append(
        make_bullet(
            "Shareable Multiplayer Room Link Server & HTML5/JS Web Client: ",
            "Built MultiplayerRoomServer using Python's built-in ThreadingHTTPServer, socket, and urllib. Generates a shareable invite link (http://<LAN_IP>:<PORT>/room/<CODE>) so a friend can join from any mobile/laptop browser or paste the link into the desktop app.",
        )
    )

    parts.append(make_heading("4.2 Exact Code Reference Map for Member 3 (Open gui_main.py)", 3))
    parts.append(
        make_table(
            headers=["Concept to Show Teacher", "File Name", "Class / Function Name", "Exact Lines"],
            rows=[
                ["Runtime RGBA -> #000000 Alpha Iteration", "gui_main.py", "SilhouetteGenerator.generate_silhouette_from_png()", "Lines 94 – 140"],
                ["Spotlight Card Compositing & PhotoImage Cache", "gui_main.py", "SilhouetteGenerator.render_card_photo()", "Lines 160 – 238"],
                ["2x Supersampled Spline Animal Renderer", "gui_main.py", "SilhouetteGenerator._catmull_rom_spline() & _draw_animal_sprite()", "Lines 255 – 1760"],
                ["Multiplayer HTTP Room Link Server & Web UI", "gui_main.py", "MultiplayerRoomServer (start_room, get_room_state_dict, build_web_client_html)", "Lines 1765 – 2080"],
                ["Main Menu, Difficulty Selector & Tables", "gui_main.py", "WhosThatAnimalGUI.show_main_menu(), _build_leaderboard_panel(), _build_avl_mmr_panel()", "Lines 2236 – 2710"],
                ["Single Player UI & Non-Blocking .after() Timer", "gui_main.py", "WhosThatAnimalGUI._build_single_player_ui(), _start_sp_timer(), _tick_sp_timer()", "Lines 2713 – 3255"],
                ["Multiplayer Split-Screen UI & Room Link Bar", "gui_main.py", "WhosThatAnimalGUI.create_multiplayer_room_and_start(), _build_multiplayer_ui(), _apply_mp_guess_result_to_ui()", "Lines 3258 – 4050"],
            ],
            col_widths=[2500, 1500, 3800, 1800],
        )
    )

    parts.append(make_heading("4.3 Word-for-Word Explanation to Give the Teacher (Member 3)", 3))
    parts.append(
        make_quote_box(
            "What Member 3 Should Say to the Teacher",
            '"Ma\'am/Sir, I built the Presentation Layer, Dynamic Image Processing Engine, and Multiplayer Room Link Server in gui_main.py. First, in SilhouetteGenerator.generate_silhouette_from_png() (Lines 94–140), instead of using pre-made shadow images, my code loads the transparent RGBA animal PNG at runtime and iterates through every pixel\'s (r, g, b, a) channels. Wherever alpha > 0, it converts the pixel to solid black (0, 0, 0, a) (#000000) while keeping alpha == 0 transparent. I also built a 2x-supersampled procedural wildlife renderer (Lines 255–1760) using Catmull-Rom splines and Lanczos downsampling.\n\nSecond, I built the Event-Driven Tkinter GUI (WhosThatAnimalGUI, Lines 2086–4145) using pack() for main layout stacks and grid() for the 6-column HUD, High Score/Ranking tables, and the 3-column Split-Screen Multiplayer arena. For the countdown timers, I used self.root.after(1000, ...) with after_cancel() cleanup so the GUI never freezes while waiting.\n\nThird, I built MultiplayerRoomServer (Lines 1765–2080) using Python\'s ThreadingHTTPServer. When a player clicks \'Create Room & Get Link\', the app detects the LAN IP, starts a room server, and copies a shareable link (http://<IP>:<PORT>/room/<CODE>) to the clipboard. A friend can open that link on any phone or laptop browser—or paste it into the desktop app—to play a live 10-round match with synchronized timers, clues, and instant lockout."',
        )
    )

    parts.append(make_heading("4.4 Viva Questions & Answers for Member 3", 3))
    parts.append(
        make_qa(
            1,
            "Show me in code how you convert the animal image into a black silhouette at runtime.",
            "In gui_main.py at Lines 119–138 inside generate_silhouette_from_png(), we call src_px = rgba_image.load() and dst_px = silhouette_img.load(), then loop over y in range(height) and x in range(width). For each pixel (r, g, b, a), if a > 0 we set dst_px[x, y] = (0, 0, 0, a), else (0, 0, 0, 0). Keeping 'a' preserves smooth anti-aliased edges.",
        )
    )
    parts.append(
        make_qa(
            2,
            "Why did you use self.root.after(1000, ...) instead of time.sleep(1) for the countdown timers?",
            "Tkinter runs a single-threaded event loop (mainloop). Calling time.sleep(1) blocks the main thread, freezing all buttons and keyboard input. self.root.after(1000, callback) schedules a non-blocking callback 1000ms later so animations and typing remain completely smooth.",
        )
    )
    parts.append(
        make_qa(
            3,
            "How does the Shareable Multiplayer Room Link work across devices?",
            "MultiplayerRoomServer (Lines 1765–2080) runs a background ThreadingHTTPServer bound to 0.0.0.0. Opening GET /room/<CODE> serves a responsive HTML5/JS client that polls GET /api/room/<CODE>/state every 650ms, fetches the runtime silhouette from /api/room/<CODE>/image.png, and sends guesses to POST /api/room/<CODE>/guess.",
        )
    )
    parts.append(
        make_qa(
            4,
            "How do you safely update Tkinter widgets when a friend submits a guess from a background HTTP thread?",
            "Because Tkinter is not thread-safe, the HTTP thread appends a lambda callback into self.room_server._ui_events (Lines 1894, 1905), and _pump_room_ui_events() (Lines 3849–3859, scheduled via root.after(150, ...)) executes those callbacks safely on the main Tkinter thread.",
        )
    )

    # =========================================================================
    # SECTION 5: BONUS — IF TEACHER ASKS TO DIVIDE ONLY THE FRONTEND (`gui_main.py`)
    # =========================================================================
    parts.append(
        make_heading(
            "5. BONUS REFERENCE: IF ASKED TO DIVIDE ONLY THE FRONTEND (gui_main.py) AMONG 3 MEMBERS",
            2,
        )
    )
    parts.append(
        make_table(
            headers=["Member", "Frontend Sub-Role", "Exact Methods & Lines in gui_main.py", "Key Viva Focus"],
            rows=[
                [
                    "Member 1",
                    "Pillow (PIL) Graphics & Runtime Silhouette Engine",
                    "SilhouetteGenerator: generate_silhouette_from_png, create_silhouette, render_card_photo, _catmull_rom_spline, _draw_animal_sprite (Lines 55 – 1760)",
                    "RGBA pixel iteration (a > 0 -> (0,0,0,a)), PhotoImage garbage collection prevention, 2x Lanczos supersampling.",
                ],
                [
                    "Member 2",
                    "Tkinter Main Menu, Dashboards, Difficulty & Single Player UI",
                    "WhosThatAnimalGUI: show_main_menu, _build_leaderboard_panel, _build_avl_mmr_panel, _build_single_player_ui, _start_sp_timer, _tick_sp_timer (Lines 2086 – 3255)",
                    "pack() vs. grid() layout separation, <Return> event binding, non-blocking root.after(1000) & after_cancel().",
                ],
                [
                    "Member 3",
                    "Multiplayer Split-Screen UI, Shareable Room Link & Web Client",
                    "MultiplayerRoomServer (Lines 1765 – 2080) & WhosThatAnimalGUI: create_multiplayer_room_and_start, _build_multiplayer_ui, _apply_mp_guess_result_to_ui (Lines 3258 – 4145)",
                    "3-column split grid(), disabling opponent Entry on lockout, clipboard copy, HTTP-to-Tkinter thread queue (_pump_room_ui_events).",
                ],
            ],
            col_widths=[1300, 2300, 3400, 2600],
        )
    )

    body_xml = "\n".join(parts)

    document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    {body_xml}
    <w:sectPr>
      <w:pgSz w:w="12240" w:h="15840"/>
      <w:pgMar w:top="1080" w:right="1080" w:bottom="1080" w:left="1080" w:header="720" w:footer="720" w:gutter="0"/>
    </w:sectPr>
  </w:body>
</w:document>"""

    content_types_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""

    rels_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as docx_zip:
        docx_zip.writestr("[Content_Types].xml", content_types_xml)
        docx_zip.writestr("_rels/.rels", rels_xml)
        docx_zip.writestr("word/document.xml", document_xml)


if __name__ == "__main__":
    out_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "Team_Work_Division_Teacher_Explanation_and_Viva_QA.docx",
    )
    build_team_division_docx(out_file)
    print(f"Created DOCX: {out_file} ({os.path.getsize(out_file)} bytes)")
