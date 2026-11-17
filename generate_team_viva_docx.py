"""
Generates a comprehensive Microsoft Word (.docx) document containing:
1. Full-Project 3-Member Team Work Division (Backend DSA, Game Logic/Automata, Frontend UI/Graphics)
2. Frontend-Only 3-Member Team Work Division (inside gui_main.py)
3. Exact Teacher Presentation Scripts (Word-for-Word Explanation for Each Member)
4. Viva / Evaluation Questions & Answers for Each Member
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
            "WHO'S THAT ANIMAL? — 3-Member Team Work Division, Teacher Explanation Scripts & Viva Q&A",
            1,
        )
    )
    parts.append(
        make_paragraph(
            "Complete breakdown of: (1) Full-Project 3-Member Division across Backend DSA, Automata/Logic, and Frontend UI, "
            "and (2) Frontend-Only 3-Member Division inside gui_main.py, including word-for-word teacher explanation scripts "
            "and Viva questions & answers for every member.",
            italic=True,
        )
    )

    # =========================================================================
    # SECTION 1: FULL-PROJECT 3-MEMBER WORK DIVISION
    # =========================================================================
    parts.append(make_heading("PART 1: FULL-PROJECT 3-MEMBER WORK DIVISION (3-TIER ARCHITECTURE)", 2))
    parts.append(
        make_table(
            headers=["Team Member", "Role Title", "Module Owned", "Core Components & Algorithms Implemented"],
            rows=[
                [
                    "Member 1",
                    "Core DSA & Data Architect",
                    "dsa_engine.py & docs/SSOT.md",
                    "AnimalRecord dataset (16+ species with difficulty tiers), TaxonomyDAG with DFS cycle guard & BFS hint traversal, PrefixTrie + LevenshteinAutomaton (NFA fuzzy matching), Binary MaxHeapLeaderboard, and Self-Balancing AVLTreeMMR (LL/RR/LR/RL rotations).",
                ],
                [
                    "Member 2",
                    "Automata & Game Logic Engineer",
                    "game_logic.py & docs/SSOT.md",
                    "Formal 5-tuple GameDFA state machine (MAIN_MENU -> INIT_MODE -> GUESSING -> HINT_REVEAL -> GAME_OVER), Difficulty Engine (Easy/Medium/Difficult), SinglePlayerController (lives, 3-strike rule, point decay), and MultiplayerController (10 rounds, threading.Lock race-condition lockout).",
                ],
                [
                    "Member 3",
                    "UI/UX, PIL Graphics & Room Server Engineer",
                    "gui_main.py & generate_sheets_docx.py",
                    "Pillow (PIL) 2x supersampled realistic animal sprites, runtime RGBA-to-#000000 alpha-channel silhouette generator, Event-Driven Tkinter GUI (pack/grid + non-blocking .after() timers), and HTTP/REST Multiplayer Shareable Room Link Server + Web Client.",
                ],
            ],
            col_widths=[1400, 2100, 1900, 4200],
        )
    )

    # =========================================================================
    # SECTION 2: FRONTEND-ONLY 3-MEMBER DIVISION (gui_main.py)
    # =========================================================================
    parts.append(make_heading("PART 2: FRONTEND-ONLY 3-MEMBER WORK DIVISION (INSIDE gui_main.py)", 2))
    parts.append(
        make_paragraph(
            "If the evaluation focuses specifically on dividing the Frontend & Presentation Layer (gui_main.py) "
            "equally among the 3 team members, here is the exact code ownership and line mapping:"
        )
    )
    parts.append(
        make_table(
            headers=["Member", "Frontend Subsystem", "Classes & Methods in gui_main.py", "Code Lines"],
            rows=[
                [
                    "Member 1",
                    "Pillow (PIL) Graphics Engine & Runtime Alpha Silhouette Processor",
                    "SilhouetteGenerator (generate_silhouette_from_png, create_silhouette, load_revealed, render_card_photo, _catmull_rom_spline, _draw_animal_sprite)",
                    "Lines 55 – 1760",
                ],
                [
                    "Member 2",
                    "Tkinter Main Menu, Dashboards, Difficulty Selector & Single Player UI",
                    "WhosThatAnimalGUI (show_main_menu, _build_leaderboard_panel, _build_avl_mmr_panel, start_single_player, _build_single_player_ui, _start_sp_timer, _tick_sp_timer, _on_sp_submit_guess)",
                    "Lines 2086 – 3255",
                ],
                [
                    "Member 3",
                    "Multiplayer Split-Screen Arena, Shareable Room Link UI & Web Client Frontend",
                    "MultiplayerRoomServer (build_web_client_html, REST UI sync) + WhosThatAnimalGUI (create_multiplayer_room_and_start, join_multiplayer_via_link, _build_multiplayer_ui, _on_mp_submit_guess, _show_game_over_modal)",
                    "Lines 1765 – 2080 & 3258 – 4145",
                ],
            ],
            col_widths=[1300, 2500, 4100, 1700],
        )
    )

    # =========================================================================
    # SECTION 3: MEMBER 1 — WORK, TEACHER EXPLANATION & VIVA Q&A
    # =========================================================================
    parts.append(make_heading("PART 3: MEMBER 1 — PILLOW (PIL) GRAPHICS & RUNTIME SILHOUETTE ENGINE", 2))

    parts.append(make_heading("3.1 Work Done by Member 1", 3))
    parts.append(
        make_bullet(
            "Runtime Alpha-Channel Silhouette Conversion (generate_silhouette_from_png): ",
            "Loads standard transparent 4-channel RGBA animal PNGs at runtime, iterates pixel-by-pixel over (x, y) inspecting (r, g, b, a), and converts every non-transparent pixel (a > 0) to solid black (0, 0, 0, a) (#000000) while preserving transparent background pixels (0, 0, 0, 0). No pre-made shadow files are stored on disk.",
        )
    )
    parts.append(
        make_bullet(
            "2x Supersampled Realistic Animal Sprite Engine (_draw_animal_sprite): ",
            "Renders 17 anatomically detailed wildlife sprites on a 640x640 RGBA canvas using Catmull-Rom splines (_catmull_rom_spline), tapered strokes, and multi-layered shading, then downsamples to 320x320 using Image.Resampling.LANCZOS.",
        )
    )
    parts.append(
        make_bullet(
            "Spotlight Card Compositing & PhotoImage Caching (render_card_photo): ",
            "Composites either the black silhouette (revealed=False) or full-color animal (revealed=True) onto a radial spotlight card and caches the resulting ImageTk.PhotoImage.",
        )
    )

    parts.append(make_heading("3.2 Word-for-Word Explanation to Give the Teacher (Member 1)", 3))
    parts.append(
        make_quote_box(
            "Member 1 Presentation Script",
            '"Ma\'am/Sir, I handled the Image Processing and Dynamic Asset Layer of the frontend using Python\'s Pillow (PIL) library. A core requirement of our project was that we must not use pre-made shadow images. So in generate_silhouette_from_png(), whenever a round starts, my code loads the standard 4-channel RGBA animal PNG at runtime and iterates pixel-by-pixel through the Alpha channel. Wherever alpha > 0 (meaning part of the animal\'s body), I overwrite the RGB channels to (0, 0, 0, alpha) which is solid black #000000, while keeping alpha == 0 completely transparent. Because I preserve the original alpha value instead of forcing it to 255, the edges stay smooth and anti-aliased. When the player guesses right, render_card_photo(revealed=True) swaps the black silhouette with the full-color RGBA sprite on the Tkinter canvas."',
        )
    )

    parts.append(make_heading("3.3 Viva Questions & Answers for Member 1", 3))
    parts.append(
        make_qa(
            1,
            "How do you generate the black animal shadow without saving a separate shadow image file?",
            "In generate_silhouette_from_png(), we open the PNG in 'RGBA' mode and access the pixel matrix using image.load(). We run a nested loop over width and height. If a pixel's alpha channel a > 0, we write (0, 0, 0, a) into the destination image; if a == 0, we write (0, 0, 0, 0).",
        )
    )
    parts.append(
        make_qa(
            2,
            "Why did you write (0, 0, 0, a) instead of (0, 0, 0, 255) for the silhouette?",
            "Keeping the original alpha value 'a' preserves edge anti-aliasing (semi-transparent border pixels along curved edges like feathers, ears, and whiskers), preventing jagged or pixelated edges on the silhouette.",
        )
    )
    parts.append(
        make_qa(
            3,
            "Why do you store self.sp_image_lbl.image = photo after setting image=photo on a Tkinter Label?",
            "Python's garbage collector automatically deletes local ImageTk.PhotoImage objects once a function exits, which causes the Tkinter image to turn blank. Keeping an explicit reference on the widget (.image = photo) and in self._photo_cache prevents garbage collection.",
        )
    )
    parts.append(
        make_qa(
            4,
            "What is 2x supersampling and Image.Resampling.LANCZOS in your sprite generator?",
            "We draw each animal at double resolution (640x640) and scale it down to 320x320 using the Lanczos sinc filter so curves, splines, and fine details look crisp and realistic.",
        )
    )

    # =========================================================================
    # SECTION 4: MEMBER 2 — WORK, TEACHER EXPLANATION & VIVA Q&A
    # =========================================================================
    parts.append(
        make_heading(
            "PART 4: MEMBER 2 — TKINTER MAIN MENU, DASHBOARDS, DIFFICULTY & SINGLE PLAYER UI",
            2,
        )
    )

    parts.append(make_heading("4.1 Work Done by Member 2", 3))
    parts.append(
        make_bullet(
            "Main Menu, Difficulty Selector & Dashboards (show_main_menu): ",
            "Built the Main Menu using pack() and grid(), including Player Name inputs, the interactive 3-level Difficulty Selector (Easy, Medium, Difficult), the High Scores table (_build_leaderboard_panel), and the Player Rankings / Opponent Finder table (_build_avl_mmr_panel).",
        )
    )
    parts.append(
        make_bullet(
            "Single Player Arena HUD & Clues Panel (_build_single_player_ui): ",
            "Designed the 6-column grid() HUD bar (Player Name + Level, Score, Lives, Dynamic Reward 100/75/50/0 pts, Mistakes 0/3, and Countdown Timer), the Mystery Shadow display card, and the progressive 3-clue panel with the 0-point Skip button.",
        )
    )
    parts.append(
        make_bullet(
            "Event Binding & Non-Blocking Timers (_start_sp_timer, _tick_sp_timer, _on_sp_submit_guess): ",
            "Bound the <Return> (Enter) key to the guess Entry box for instant submission and implemented non-blocking 1-second timer callbacks using self.root.after(1000, ...) with after_cancel() cleanup.",
        )
    )

    parts.append(make_heading("4.2 Word-for-Word Explanation to Give the Teacher (Member 2)", 3))
    parts.append(
        make_quote_box(
            "Member 2 Presentation Script",
            '"Ma\'am/Sir, I built the Tkinter Event-Driven Desktop Interface, Main Menu Dashboards, Difficulty Selector, and Single Player Survival UI. I used a hybrid geometry manager architecture: pack() is used for top-to-bottom structural containers, while grid() is used for multi-column aligned components like the 6-column Single Player HUD and the High Score / Player Ranking tables. A critical part of my work was implementing non-blocking timers. If we used time.sleep(1) for the 45s/30s/20s countdown, the entire Tkinter window would freeze and stop accepting keyboard input. Instead, I used self.root.after(1000, self._tick_sp_timer) to schedule 1-second callbacks on Tkinter\'s event loop, and self.root.after_cancel() whenever a player solves an animal or switches screens so timers never overlap."',
        )
    )

    parts.append(make_heading("4.3 Viva Questions & Answers for Member 2", 3))
    parts.append(
        make_qa(
            1,
            "Where did you use pack() vs. grid() in the GUI, and why shouldn't you mix them inside the same parent frame?",
            "pack() stacks major sections vertically (header, main body, bottom input bar), while grid() arranges rows and columns inside child frames (the 6-column HUD, 2-column dashboard, and tables). Tkinter raises an error if pack() and grid() are used on direct siblings inside the exact same parent widget, so we isolate each grid() layout inside its own tk.Frame.",
        )
    )
    parts.append(
        make_qa(
            2,
            "Why did you use root.after(1000, ...) instead of time.sleep(1) or a while loop for the timer?",
            "Tkinter is single-threaded and runs on mainloop(). Calling time.sleep() blocks the UI thread, freezing buttons and text entry. root.after(1000, callback) registers a non-blocking timer event with Tkinter's event loop so the UI stays 100% responsive.",
        )
    )
    parts.append(
        make_qa(
            3,
            "Why is root.after_cancel() necessary in _cancel_all_timers()?",
            "If a player guesses the animal with 18 seconds left and advances to the next animal without canceling the previous .after() timer ID, two timers would tick simultaneously (making the clock count down twice as fast). after_cancel() prevents timer stacking.",
        )
    )
    parts.append(
        make_qa(
            4,
            "How does the <Return> key submission work on the Guess Entry box?",
            "We bind the keyboard event using self.sp_entry.bind('<Return>', lambda _e: self._on_sp_submit_guess()), which reads the tk.StringVar(), clears the input box, and updates the HUD and clue panels immediately.",
        )
    )

    # =========================================================================
    # SECTION 5: MEMBER 3 — WORK, TEACHER EXPLANATION & VIVA Q&A
    # =========================================================================
    parts.append(
        make_heading(
            "PART 5: MEMBER 3 — MULTIPLAYER SPLIT-SCREEN UI, SHAREABLE ROOM LINK & WEB CLIENT",
            2,
        )
    )

    parts.append(make_heading("5.1 Work Done by Member 3", 3))
    parts.append(
        make_bullet(
            "3-Column Vertically Split Multiplayer Arena (_build_multiplayer_ui): ",
            "Built the split-screen 1v1 arena using grid() with Column 0 (Player 1 Left Station with independent <Return> Entry), Column 1 (Center Shared Silhouette, Round X/10, 75s/60s/40s Timer, and Shared Clues), and Column 2 (Player 2 Right Station with independent <Return> Entry).",
        )
    )
    parts.append(
        make_bullet(
            "Visual Lockout Enforcement (_apply_mp_guess_result_to_ui): ",
            "The instant either player answers correctly, immediately disables both Entry boxes (state='disabled'), flashes the winner banner, shows the lockout notice on the opponent's station, and reveals the full-color animal before advancing.",
        )
    )
    parts.append(
        make_bullet(
            "Shareable Room Link UI & HTML5/JS Web Client (MultiplayerRoomServer & build_web_client_html): ",
            "Built the 'Create Room & Get Link' flow that starts the background HTTP server, copies http://<LAN_IP>:<PORT>/room/<CODE> to the clipboard, serves the live mobile/desktop browser client, and marshals network events onto the Tkinter main thread via _pump_room_ui_events().",
        )
    )

    parts.append(make_heading("5.2 Word-for-Word Explanation to Give the Teacher (Member 3)", 3))
    parts.append(
        make_quote_box(
            "Member 3 Presentation Script",
            '"Ma\'am/Sir, I designed and implemented the Multiplayer Frontend Layer—both the 3-Column Split-Screen Desktop Arena and the Shareable Room Link Web Interface. In the desktop app, I used grid() with 3 columns: Player 1\'s station on the left, the shared animal shadow and clues in the center, and Player 2\'s station on the right. To allow two friends to play across different devices using a link, I also built the Room Invite Link system (MultiplayerRoomServer). When Player 1 clicks \'Create Room & Get Link\', the app generates a shareable URL like http://192.168.0.101:54321/room/ANM123 and copies it to the clipboard. When Player 2 opens that link in any browser—or pastes it into their desktop app—my frontend syncs the live timer, silhouette image, clues, and scores every 650ms. The moment either player submits the right answer, my UI immediately disables the opponent\'s input box (state=\'disabled\') to visually enforce the lockout."',
        )
    )

    parts.append(make_heading("5.3 Viva Questions & Answers for Member 3", 3))
    parts.append(
        make_qa(
            1,
            "How does the Split-Screen Multiplayer UI prevent the second player from typing after the first player wins the round?",
            "Inside _apply_mp_guess_result_to_ui(), as soon as result.get('correct') is True, we immediately call self.mp_p1_entry.configure(state='disabled') and self.mp_p2_entry.configure(state='disabled') (and disable the submit button on the web client as well) while displaying the winner banner.",
        )
    )
    parts.append(
        make_qa(
            2,
            "How can a background HTTP thread safely update Tkinter GUI labels when a friend joins or guesses via the Room Link?",
            "Tkinter widgets are not thread-safe and must only be modified on the main thread. When the HTTP server receives a /join, /guess, or /hint request on a background thread, it appends a callback to self.room_server._ui_events, and _pump_room_ui_events() (scheduled via self.root.after(150, ...)) executes those UI updates safely on the main Tkinter thread.",
        )
    )
    parts.append(
        make_qa(
            3,
            "How does the friend's browser display the runtime-generated black silhouette without pre-made image files?",
            "The browser <img> tag requests /api/room/<CODE>/image.png?round=X&revealed=0. When requested, render_current_card_png() calls Member 1's PIL silhouette generator in memory, encodes it into a BytesIO PNG buffer, and streams those bytes directly over HTTP.",
        )
    )
    parts.append(
        make_qa(
            4,
            "How did you copy the Room Link to the user's Windows clipboard without external libraries?",
            "Using Tkinter's built-in clipboard methods: self.root.clipboard_clear() followed by self.root.clipboard_append(share_url).",
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
