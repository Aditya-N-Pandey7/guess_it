"""
Generates a properly formatted Microsoft Word (.docx) document containing:
1. Official Game Rules Sheet for "Who's That Animal?"
2. Technical Implementation Sheet (DSA, Automata & Software Frameworks)
Uses standard library `zipfile` + OpenXML (`word/document.xml`, `[Content_Types].xml`, etc.)
so it requires zero external packages and opens cleanly in Microsoft Word, Google Docs, and LibreOffice.
"""

import os
import zipfile
from xml.sax.saxutils import escape


def _xml_text(text: str) -> str:
    return escape(text, {'"': "&quot;", "'": "&apos;"})


def make_heading(text: str, level: int = 1) -> str:
    sizes = {1: "36", 2: "28", 3: "23"}
    colors = {1: "0F172A", 2: "0284C7", 3: "0D9488"}
    space_before = {1: "280", 2: "220", 3: "160"}
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


def build_docx(output_path: str) -> None:
    parts: list[str] = []

    parts.append(make_heading("WHO'S THAT ANIMAL? — Official Game Rules & Technical Architecture Sheet", 1))
    parts.append(
        make_paragraph(
            "Complete player rulebook (Single Player, 1v1 Multiplayer Room Link, Difficulty Levels & Scoring) "
            "and full engineering breakdown of all Data Structures, Automata, and Software Frameworks.",
            italic=True,
        )
    )

    parts.append(make_heading("PART 1: OFFICIAL GAME RULES SHEET", 2))

    parts.append(make_heading("1.1 Game Objective", 3))
    parts.append(
        make_paragraph(
            "Identify the mystery animal from its solid black shadow (silhouette) and up to 3 progressive clues "
            "before the countdown timer expires. When the animal is guessed correctly (or when the round ends), "
            "the full-color wildlife illustration is revealed."
        )
    )

    parts.append(make_heading("1.2 Answering & Spelling Rules", 3))
    parts.append(
        make_bullet(
            "How to Submit: ",
            "Type the animal's name in the guess box and press Enter (or click the Guess button).",
        )
    )
    parts.append(
        make_bullet(
            "Full or Short Names Accepted: ",
            "Players can enter either the full name (e.g., African Elephant, Bengal Tiger, Great White Shark) "
            "or the common short name (e.g., Elephant, Tiger, Shark, Penguin, Eagle, Cobra, Frog, Panda, Kangaroo, Dolphin, Owl, Chameleon).",
        )
    )
    parts.append(
        make_bullet(
            "Typo & Spelling Forgiveness: ",
            "On Easy and Medium levels, up to 2 character typos are forgiven automatically (e.g., 'elephnt' or 'pengin'). "
            "On Difficult level, spelling is stricter and allows at most 1 character typo.",
        )
    )

    parts.append(make_heading("1.3 Clues & Point Scoring Schedule", 3))
    parts.append(
        make_paragraph(
            "Each animal has 3 progressive clues: Clue 1 (Animal Group / Class), Clue 2 (Habitat & Geographic Region), "
            "and Clue 3 (Specific Signature Trait)."
        )
    )
    parts.append(
        make_table(
            headers=["Clues Revealed", "Single Player Points", "Multiplayer (1v1) Points", "Clue Description"],
            rows=[
                ["0 Clues (Shadow Only)", "100 pts", "100 pts", "Solved purely from the animal's black shadow"],
                ["1 Clue Revealed", "75 pts (100 pts on Easy)", "75 pts (100 pts on Easy)", "Clue 1: Animal Group / Taxonomic Class & Order"],
                ["2 Clues Revealed", "50 pts (75 pts on Easy)", "50 pts (75 pts on Easy)", "Clue 2: Geographic Region & Natural Habitat"],
                ["3 Clues Revealed", "0 pts (Can Skip Animal)", "25 pts", "Clue 3: Specific Diagnostic / Signature Trait"],
            ],
            col_widths=[2200, 2100, 2100, 3200],
        )
    )

    parts.append(make_heading("1.4 Difficulty Levels (Easy • Medium • Difficult)", 3))
    parts.append(
        make_table(
            headers=["Rule / Parameter", "Easy Level", "Medium Level", "Difficult Level"],
            rows=[
                ["Single Player Lives", "4 Lives (❤ ❤ ❤ ❤)", "3 Lives (❤ ❤ ❤)", "2 Lives (❤ ❤)"],
                ["Single Player Timer", "45 seconds per animal", "30 seconds per animal", "20 seconds per animal"],
                ["Multiplayer Round Timer", "75 seconds per round", "60 seconds per round", "40 seconds per round"],
                ["Starting Free Clue", "Clue 1 unlocked for free (100 pts)", "All 3 clues start locked", "All 3 clues start locked"],
                ["Spelling Tolerance", "Up to 2 character typos", "Up to 2 character typos", "Strict (max 1 character typo)"],
                ["Animal Deck Order", "Iconic animals first (Elephant, Tiger, Penguin, Shark, Panda, Dolphin)", "Balanced mix (Eagle, Cobra, Kangaroo, Snowy Owl, Clownfish)", "Exotic animals first (Axolotl, Platypus, Komodo Dragon, Chameleon, Tree Frog)"],
            ],
            col_widths=[2100, 2500, 2500, 2500],
        )
    )

    parts.append(make_heading("1.5 Single Player Survival Mode Rules", 3))
    parts.append(make_bullet("Starting Lives: ", "Begin with 4 Lives (Easy), 3 Lives (Medium), or 2 Lives (Difficult)."))
    parts.append(make_bullet("3-Strike Mistake Rule: ", "Making 3 wrong guesses on the same animal deducts 1 Life (-1 ❤) and moves to the next animal."))
    parts.append(make_bullet("Timer Expiration Rule: ", "If the countdown timer reaches 0s before you solve the animal, you lose 1 Life (-1 ❤)."))
    parts.append(make_bullet("Skipping After Clue 3: ", "Revealing Clue 3 sets the reward to 0 points and unlocks the 'Next Animal (0 pts)' button so you can advance without losing a life."))
    parts.append(make_bullet("Game Over: ", "The survival run ends when Lives reach 0 or all animals in the deck are completed. Your score and rating are automatically saved."))

    parts.append(make_heading("1.6 Multiplayer (1v1) Rules — Shareable Room Link & Split-Screen", 3))
    parts.append(
        make_bullet(
            "Creating & Sharing a Room Link: ",
            "Click 'Create Room & Get Link' on the Main Menu. A room URL (http://<IP>:<PORT>/room/<CODE>) is copied to your clipboard. "
            "Send that link to your friend—they can open it in any web browser (phone, laptop, tablet, PC) or paste it into the 'Room Link' box in the desktop app.",
        )
    )
    parts.append(make_bullet("10 Continuous Rounds: ", "Each Multiplayer match runs for 10 rounds."))
    parts.append(
        make_bullet(
            "First Correct Answer Wins (Lockout Rule): ",
            "Both players see the same shadow, timer, and shared clues. The first player to submit a valid answer immediately locks out "
            "the opponent for that round, reveals the animal, and claims the round's points.",
        )
    )
    parts.append(make_bullet("Unlimited Attempts While Unlocked: ", "An incorrect guess in Multiplayer does not lock you out—both players can keep guessing until someone answers correctly or the timer expires."))

    parts.append(make_heading("PART 2: TECHNICAL IMPLEMENTATION SHEET (DSA, AUTOMATA & FRAMEWORKS)", 2))

    parts.append(make_heading("2.1 Three-Tier System Architecture", 3))
    parts.append(
        make_table(
            headers=["Architecture Tier", "Module File", "Key Classes & Responsibilities"],
            rows=[
                ["Single Source of Truth", "docs/SSOT.md", "Defines strict data contracts, class schemas, and module boundaries across all 3 tiers."],
                ["Level 1: Core DSA Engine", "dsa_engine.py", "AnimalRecord, TaxonomyDAG (BFS), PrefixTrie, LevenshteinAutomaton (NFA), MaxHeapLeaderboard, AVLTreeMMR."],
                ["Level 2: Automata & Rules", "game_logic.py", "GameDFA (5-tuple state machine), SinglePlayerController (survival rules), MultiplayerController (10-round race lockout)."],
                ["Level 3: UI, PIL & Room Server", "gui_main.py", "SilhouetteGenerator (2x supersampled PIL sprites + runtime RGBA->#000000), MultiplayerRoomServer (HTTP/REST), WhosThatAnimalGUI (Tkinter)."],
            ],
            col_widths=[2100, 1800, 5700],
        )
    )

    parts.append(make_heading("2.2 Data Structures & Algorithms (DSA) Implementation", 3))
    parts.append(
        make_table(
            headers=["DSA Concept", "Class / Method (dsa_engine.py)", "Implementation Details", "Complexity"],
            rows=[
                [
                    "Directed Acyclic Graph (DAG)",
                    "TaxonomyDAG (add_edge, add_animal, _creates_cycle)",
                    "Models biological hierarchy: Kingdom:Animalia -> Class -> Order -> Animal using adjacency lists. Enforces acyclicity on every edge insertion via DFS cycle detection.",
                    "O(V + E) cycle check & traversal",
                ],
                [
                    "Breadth-First Search (BFS)",
                    "TaxonomyDAG.bfs_lineage_path & bfs_generate_hints",
                    "Uses an explicit FIFO queue (collections.deque) and parent pointer map from Kingdom:Animalia to reconstruct the shortest taxonomic path and dynamically generate Clues 1, 2, and 3.",
                    "O(V + E) time, O(V) space",
                ],
                [
                    "Prefix Tree (Trie)",
                    "TrieNode & PrefixTrie (insert, search_exact, resolve_exact)",
                    "Stores all canonical animal names and accepted short aliases character-by-character. Maps terminal nodes directly to canonical animal identifiers.",
                    "O(L) insert & exact lookup",
                ],
                [
                    "Binary Max-Heap Priority Queue",
                    "MaxHeapLeaderboard (_sift_up, _sift_down, insert, get_top, extract_max, get_top_k)",
                    "Built from scratch over a contiguous array without heapq. Maintains the max-heap invariant parent >= children for instant retrieval of the top champion and sorted Top-K leaderboards.",
                    "O(1) top peek, O(log n) insert & extract",
                ],
                [
                    "Self-Balancing AVL Tree",
                    "AVLNode & AVLTreeMMR (_rotate_left, _rotate_right, _rebalance, upsert_player, find_closest_match)",
                    "Stores player skill ratings (MMR) and win/game records. Executes explicit LL, RR, LR, and RL tree rotations on every update to keep |balance_factor| <= 1, and finds closest-rated opponents.",
                    "O(log n) insert, delete, rebalance & closest search",
                ],
            ],
            col_widths=[1800, 2200, 3900, 1700],
        )
    )

    parts.append(make_heading("2.3 Automata Theory Implementation (DFA & Levenshtein NFA)", 3))
    parts.append(
        make_table(
            headers=["Automaton", "Class & Module", "Formal Definition & Game Role"],
            rows=[
                [
                    "Deterministic Finite Automaton (DFA)",
                    "GameDFA (game_logic.py)",
                    "Formal 5-tuple M = (Q, Sigma, delta, q0, F) with states Q = {MAIN_MENU, INIT_MODE, GUESSING, HINT_REVEAL, GAME_OVER} and events Sigma = {SELECT_MODE, ROUND_READY, REQUEST_HINT, RESUME_GUESS, NEXT_ROUND, END_GAME, RESTART}. Enforces deterministic transitions via delta(q, sigma) -> q' and raises InvalidStateTransitionError on illegal transitions.",
                ],
                [
                    "Levenshtein Non-Deterministic Finite Automaton (NFA)",
                    "LevenshteinNFAInstance & LevenshteinAutomaton (dsa_engine.py)",
                    "Constructs an edit-distance automaton over states (index, errors) with match, insertion, deletion (epsilon-closure), and substitution transitions. Intersects the NFA with the PrefixTrie via DFS (fuzzy_search_trie), pruning any Trie branch where min(distance_vector) > max_dist (k=2 on Easy/Medium, k=1 on Difficult).",
                ],
            ],
            col_widths=[2000, 2200, 5400],
        )
    )

    parts.append(make_heading("2.4 Software Frameworks, Graphics & Networking Stack", 3))
    parts.append(
        make_table(
            headers=["Framework / Module", "Component (gui_main.py / game_logic.py)", "Technical Implementation"],
            rows=[
                [
                    "Pillow (PIL.Image, ImageDraw, ImageTk) — 2x Supersampled Graphics",
                    "SilhouetteGenerator._draw_animal_sprite",
                    "Renders 17 wildlife illustrations on a 640x640 RGBA canvas using Catmull-Rom splines (_catmull_rom_spline), tapered strokes, and multi-layered anatomical shading, then downsamples to 320x320 using Image.Resampling.LANCZOS.",
                ],
                [
                    "Pillow (PIL) — Runtime Alpha-Channel Silhouette Engine",
                    "SilhouetteGenerator.generate_silhouette_from_png",
                    "Loads transparent RGBA PNGs at runtime and iterates pixel-by-pixel over (x, y): every non-transparent pixel (a > 0) is converted to solid black (0, 0, 0, a) (#000000), while transparent pixels remain (0, 0, 0, 0). No pre-made shadow files are used.",
                ],
                [
                    "Tkinter (tk, ttk) — Event-Driven Desktop GUI",
                    "WhosThatAnimalGUI",
                    "Combines pack() and grid() geometry managers for responsive layouts, binds <Return> keyboard events for instant guess submission, and uses non-blocking root.after(1000, ...) timers with after_cancel() cleanup to prevent UI thread freezing.",
                ],
                [
                    "Python Threading (threading.Lock) — Atomic Race Lockout",
                    "MultiplayerController.submit_guess",
                    "Uses a thread mutex (_race_lock) to synchronize local and remote Player 1 / Player 2 submissions. The first valid fuzzy-matched guess atomically sets round_locked = True, awards points, and locks out the opponent.",
                ],
                [
                    "HTTP & REST Server (http.server.ThreadingHTTPServer, socket, urllib)",
                    "MultiplayerRoomServer",
                    "Hosts a background multi-threaded HTTP server bound to 0.0.0.0, auto-detects LAN IP, generates shareable room links (http://<IP>:<PORT>/room/<CODE>), serves a live HTML5/JS web client for browser players, and synchronizes state via JSON REST endpoints (/join, /state, /guess, /hint, /image.png).",
                ],
            ],
            col_widths=[2100, 2300, 5200],
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
        "Whos_That_Animal_Rules_and_Technical_Sheet.docx",
    )
    build_docx(out_file)
    print(f"Created DOCX: {out_file} ({os.path.getsize(out_file)} bytes)")
