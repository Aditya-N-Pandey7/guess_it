# 🐾 Who's That Animal? — Heavy DSA & Automata Desktop Game

A desktop & live multiplayer animal-guessing game built with **Python 3**, **Tkinter**, **Pillow (PIL)**, and custom **Data Structures & Automata** engineered from scratch.

---

## ✨ Key Features

- **🎨 Realistic 2×-Supersampled Animal Illustrations & Dynamic Shadows**:
  - 17 anatomically detailed wildlife sprites rendered on a `640×640` canvas and Lanczos-downsampled to `320×320`.
  - **Runtime Alpha-Channel Silhouette Engine**: Converts non-transparent RGBA pixels (`alpha > 0`) to solid black `#000000` on the fly—no pre-made shadow files.
- **🎮 Three Difficulty Levels (`🟢 Easy`, `🟡 Medium`, `🔴 Difficult`)**:
  - Scales lives (`4 / 3 / 2`), countdown timers (`45s / 30s / 20s` in Single Player; `75s / 60s / 40s` in Multiplayer), starting free clues, animal ordering, and typo tolerance.
- **🌐 Live 1v1 Multiplayer with Shareable Room Links**:
  - Click **🌐 Create Room & Get Link** to spin up a built-in HTTP/REST room server (`http://<LAN_IP>:<PORT>/room/<CODE>`).
  - Send the link to a friend—they can join immediately from **any web browser** (phone, tablet, laptop, PC) or paste the link into the desktop app!
  - Also supports **⚔ Play on This Screen** (local split-screen 1v1).
- **🧠 Core DSA & Automata Engine Under the Hood**:
  1. **Taxonomy Directed Acyclic Graph (`TaxonomyDAG`) + BFS**: Traverses `Kingdom → Class → Order → Animal` using Breadth-First Search (`collections.deque`) with DFS cycle detection to dynamically generate the 3 progressive clues.
  2. **Prefix Trie (`PrefixTrie`) + Levenshtein NFA (`LevenshteinAutomaton`)**: Performs $O(m)$ typo-tolerant fuzzy matching by intersecting a Levenshtein Non-Deterministic Finite Automaton with the Trie via DFS branch pruning.
  3. **Binary Max-Heap Leaderboard (`MaxHeapLeaderboard`)**: Custom array-backed priority queue with $O(1)$ top champion peek and $O(\log n)$ sift-up / sift-down updates.
  4. **Self-Balancing AVL Tree (`AVLTreeMMR`)**: Maintains player skill ratings (MMR) using explicit LL, RR, LR, and RL rotations ($|\text{BF}| \le 1$) and $O(\log n)$ closest-opponent search.
  5. **Deterministic Finite Automaton (`GameDFA`)**: Formal 5-tuple state machine $(Q, \Sigma, \delta, q_0, F)$ governing `MAIN_MENU → INIT_MODE → GUESSING → HINT_REVEAL → GAME_OVER`.

---

## 🚀 How to Run

### 1. Install Pillow
```bash
pip install pillow
```

### 2. Launch the Game
```bash
python gui_main.py
```

### 3. Run Self-Verification Suites (Optional)
```bash
python dsa_engine.py
python game_logic.py
python gui_main.py --self-test
```

---

## 📂 Project Structure

| File | Description |
| :--- | :--- |
| `dsa_engine.py` | **[Level 1]** Taxonomy DAG + BFS, Prefix Trie + Levenshtein NFA, Binary Max-Heap Leaderboard, and Self-Balancing AVL Tree (MMR). |
| `game_logic.py` | **[Level 2]** Formal DFA State Machine, Single Player Survival Controller, and Thread-Safe Multiplayer Controller with atomic lockout. |
| `gui_main.py` | **[Level 3]** 2×-Supersampled PIL Wildlife Sprite Generator, Runtime Alpha-Channel Silhouette Processor, Clean Tkinter GUI, and HTTP Room Link Server. |
| `docs/SSOT.md` | Architectural Single Source of Truth (SSOT) & data contracts. |
| `Whos_That_Animal_Rules_and_Technical_Sheet.docx` | Printable Microsoft Word (`.docx`) Official Game Rules & Technical Implementation Sheet. |
| `generate_sheets_docx.py` | Generator script for the `.docx` rules and technical sheet. |
