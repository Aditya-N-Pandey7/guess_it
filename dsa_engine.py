"""
dsa_engine.py - Core Data Structures & Automata Engine for "Who's That Animal?"

Implements 4 foundational Data Structures and Automata from scratch:
1. TaxonomyDAG (Directed Acyclic Graph) with cycle detection and BFS hint generation.
2. PrefixTrie + LevenshteinAutomaton (NFA + Trie DFS intersection for O(m) fuzzy string matching).
3. MaxHeapLeaderboard (Array-backed Binary Max-Heap Priority Queue for O(1) top / O(log n) updates).
4. AVLTreeMMR (Self-Balancing Binary Search Tree with explicit LL/RR/LR/RL rotations for MMR).
"""

from __future__ import annotations

import copy
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set, Tuple


# ==============================================================================
# 1. ANIMAL RECORD & BUILT-IN DATASET
# ==============================================================================

@dataclass
class AnimalRecord:
    """Canonical data contract representing an animal in the Taxonomy DAG and Trie."""
    name: str                  # Lowercase canonical name, e.g., "african elephant"
    display_name: str          # Formatted title name, e.g., "African Elephant"
    kingdom: str               # Taxonomic Kingdom, e.g., "Animalia"
    animal_class: str          # Hint 1: Taxonomic Class, e.g., "Mammalia"
    order: str                 # Taxonomic Order, e.g., "Proboscidea"
    region: str                # Hint 2: Geographic Region / Habitat
    trait: str                 # Hint 3: Specific Diagnostic Trait
    image_path: str            # Relative path to transparent PNG sprite
    aliases: List[str] = field(default_factory=list)  # Accepted short names (e.g., ["elephant"])
    difficulty: str = "EASY"   # Difficulty tier: "EASY", "MEDIUM", or "HARD"

    def all_accepted_names(self) -> List[str]:
        """Returns canonical name plus all lowercase aliases."""
        names = [self.name.lower().strip()]
        for alias in self.aliases:
            cleaned = alias.lower().strip()
            if cleaned and cleaned not in names:
                names.append(cleaned)
        return names


def get_default_animal_dataset() -> List[AnimalRecord]:
    """Returns a rich built-in dataset of 16 diverse animals across major vertebrate classes."""
    return [
        AnimalRecord(
            name="african elephant",
            display_name="African Elephant",
            kingdom="Animalia",
            animal_class="Mammalia",
            order="Proboscidea",
            region="Sub-Saharan African Savannas, Woodlands & Bush",
            trait="Largest land mammal with a prehensile muscular trunk, fan-like ears, and ivory tusks",
            image_path="assets/animals/african_elephant.png",
            aliases=["elephant"],
            difficulty="EASY",
        ),
        AnimalRecord(
            name="bengal tiger",
            display_name="Bengal Tiger",
            kingdom="Animalia",
            animal_class="Mammalia",
            order="Carnivora",
            region="Indian Subcontinent Mangroves (Sundarbans), Grasslands & Tropical Forests",
            trait="Apex solitary big cat with vertical dark stripes over orange fur and retractable claws",
            image_path="assets/animals/bengal_tiger.png",
            aliases=["tiger"],
            difficulty="EASY",
        ),
        AnimalRecord(
            name="emperor penguin",
            display_name="Emperor Penguin",
            kingdom="Animalia",
            animal_class="Aves",
            order="Sphenisciformes",
            region="Antarctic Sea Ice & Frigid Southern Ocean Waters",
            trait="Tallest flightless seabird that breeds during Antarctic winter and dives deep with flipper wings",
            image_path="assets/animals/emperor_penguin.png",
            aliases=["penguin"],
            difficulty="EASY",
        ),
        AnimalRecord(
            name="bald eagle",
            display_name="Bald Eagle",
            kingdom="Animalia",
            animal_class="Aves",
            order="Accipitriformes",
            region="North American Coasts, Large Lakes & River Valleys",
            trait="Powerful bird of prey with a white-feathered head, hooked yellow beak, and talons for catching fish",
            image_path="assets/animals/bald_eagle.png",
            aliases=["eagle"],
            difficulty="MEDIUM",
        ),
        AnimalRecord(
            name="king cobra",
            display_name="King Cobra",
            kingdom="Animalia",
            animal_class="Reptilia",
            order="Squamata",
            region="Southeast Asian & Indian Dense Rainforests and Bamboo Thickets",
            trait="World's longest venomous snake that flares an iconic neck hood and preys on other snakes",
            image_path="assets/animals/king_cobra.png",
            aliases=["cobra"],
            difficulty="MEDIUM",
        ),
        AnimalRecord(
            name="komodo dragon",
            display_name="Komodo Dragon",
            kingdom="Animalia",
            animal_class="Reptilia",
            order="Squamata",
            region="Indonesian Lesser Sunda Islands (Komodo, Rinca & Flores)",
            trait="Heaviest living monitor lizard with serrated teeth, venom glands, and a yellow forked tongue",
            image_path="assets/animals/komodo_dragon.png",
            aliases=["komodo"],
            difficulty="HARD",
        ),
        AnimalRecord(
            name="red-eyed tree frog",
            display_name="Red-Eyed Tree Frog",
            kingdom="Animalia",
            animal_class="Amphibia",
            order="Anura",
            region="Neotropical Rainforests of Central America & Southern Mexico",
            trait="Nocturnal arboreal amphibian with vivid crimson eyes, neon-green body, and orange suction toe pads",
            image_path="assets/animals/red_eyed_tree_frog.png",
            aliases=["tree frog", "red eyed tree frog", "frog"],
            difficulty="HARD",
        ),
        AnimalRecord(
            name="great white shark",
            display_name="Great White Shark",
            kingdom="Animalia",
            animal_class="Chondrichthyes",
            order="Lamniformes",
            region="Temperate & Coastal Pelagic Oceans Worldwide",
            trait="Cartilaginous apex marine predator with rows of serrated triangular teeth and electroreceptive snout",
            image_path="assets/animals/great_white_shark.png",
            aliases=["shark", "white shark"],
            difficulty="EASY",
        ),
        AnimalRecord(
            name="giant panda",
            display_name="Giant Panda",
            kingdom="Animalia",
            animal_class="Mammalia",
            order="Carnivora",
            region="Montane Bamboo Forests of South-Central China (Sichuan)",
            trait="Black-and-white bear with a modified wrist bone acting as a pseudo-thumb to grip bamboo stalks",
            image_path="assets/animals/giant_panda.png",
            aliases=["panda"],
            difficulty="EASY",
        ),
        AnimalRecord(
            name="platypus",
            display_name="Platypus",
            kingdom="Animalia",
            animal_class="Mammalia",
            order="Monotremata",
            region="Freshwater Rivers, Billabongs & Streams of Eastern Australia and Tasmania",
            trait="Egg-laying semi-aquatic mammal with a leathery duck-like bill, beaver tail, and venomous ankle spurs",
            image_path="assets/animals/platypus.png",
            aliases=["duckbill platypus"],
            difficulty="HARD",
        ),
        AnimalRecord(
            name="red kangaroo",
            display_name="Red Kangaroo",
            kingdom="Animalia",
            animal_class="Mammalia",
            order="Diprotodontia",
            region="Arid & Semi-Arid Outback Deserts and Scrublands of Australia",
            trait="Largest marsupial that bounds on spring-like hind legs, balances with a muscular tail, and carries joeys in a pouch",
            image_path="assets/animals/red_kangaroo.png",
            aliases=["kangaroo"],
            difficulty="MEDIUM",
        ),
        AnimalRecord(
            name="bottlenose dolphin",
            display_name="Bottlenose Dolphin",
            kingdom="Animalia",
            animal_class="Mammalia",
            order="Artiodactyla",
            region="Warm Temperate & Tropical Oceans, Bays, and Estuaries Worldwide",
            trait="Highly intelligent marine cetacean with a curved dorsal fin, blowhole, and biological sonar (echolocation)",
            image_path="assets/animals/bottlenose_dolphin.png",
            aliases=["dolphin"],
            difficulty="EASY",
        ),
        AnimalRecord(
            name="snowy owl",
            display_name="Snowy Owl",
            kingdom="Animalia",
            animal_class="Aves",
            order="Strigiformes",
            region="Circumglobal Arctic Tundra of North America & Eurasia",
            trait="Diurnal white-plumaged raptor with golden eyes, feathered talons, and silent serrated flight feathers",
            image_path="assets/animals/snowy_owl.png",
            aliases=["owl"],
            difficulty="MEDIUM",
        ),
        AnimalRecord(
            name="veiled chameleon",
            display_name="Veiled Chameleon",
            kingdom="Animalia",
            animal_class="Reptilia",
            order="Squamata",
            region="Mountainous Plateaus, Wadis & Forests of the Arabian Peninsula",
            trait="Arboreal reptile with independently rotating eyes, a prehensile curled tail, and a ballistic sticky tongue",
            image_path="assets/animals/veiled_chameleon.png",
            aliases=["chameleon"],
            difficulty="HARD",
        ),
        AnimalRecord(
            name="axolotl",
            display_name="Axolotl",
            kingdom="Animalia",
            animal_class="Amphibia",
            order="Urodela",
            region="High-Altitude Freshwater Lakes & Canals of Xochimilco, Mexico",
            trait="Neotenic aquatic salamander with feathery external gills and the ability to regenerate whole limbs",
            image_path="assets/animals/axolotl.png",
            aliases=["mexican walking fish"],
            difficulty="HARD",
        ),
        AnimalRecord(
            name="clownfish",
            display_name="Clownfish",
            kingdom="Animalia",
            animal_class="Actinopterygii",
            order="Ovalentaria",
            region="Warm Indo-Pacific Coral Reefs & Lagoons",
            trait="Bright orange ray-finned fish with three white bars that lives symbiotically inside stinging sea anemones",
            image_path="assets/animals/clownfish.png",
            aliases=["anemonefish"],
            difficulty="MEDIUM",
        ),
    ]


# ==============================================================================
# 2. TAXONOMY DIRECTED ACYCLIC GRAPH (DAG) & BFS HINT GENERATOR
# ==============================================================================

class CycleDetectedError(ValueError):
    """Raised when adding a directed edge would introduce a cycle into the Taxonomy DAG."""


class TaxonomyDAG:
    """
    Directed Acyclic Graph (DAG) organizing animals into a biological taxonomy:
        Kingdom:Animalia -> Class:<animal_class> -> Order:<order> -> Animal:<name>

    Uses Breadth-First Search (BFS) with an explicit FIFO queue (`collections.deque`)
    starting from `"Kingdom:Animalia"` to locate a target animal and construct its
    3 progressive hints dynamically.
    """

    ROOT_NODE = "Kingdom:Animalia"

    def __init__(self, preload_defaults: bool = True) -> None:
        self.adj: Dict[str, List[str]] = {}
        self.node_meta: Dict[str, dict] = {}
        self.animals_by_name: Dict[str, AnimalRecord] = {}
        self.alias_to_canonical: Dict[str, str] = {}

        self._ensure_node(self.ROOT_NODE, level="Kingdom", label="Animalia")
        if preload_defaults:
            for record in get_default_animal_dataset():
                self.add_animal(record)

    def _ensure_node(self, node_id: str, **metadata) -> None:
        if node_id not in self.adj:
            self.adj[node_id] = []
        if node_id not in self.node_meta:
            self.node_meta[node_id] = {}
        self.node_meta[node_id].update(metadata)

    def _creates_cycle(self, u: str, v: str) -> bool:
        """
        DFS reachability check: returns True if `u` is already reachable from `v`
        (meaning adding directed edge u -> v would close a cycle).
        """
        if u == v:
            return True
        visited: Set[str] = set()
        stack: List[str] = [v]
        while stack:
            curr = stack.pop()
            if curr == u:
                return True
            if curr not in visited:
                visited.add(curr)
                for neighbor in self.adj.get(curr, []):
                    if neighbor not in visited:
                        stack.append(neighbor)
        return False

    def add_edge(self, u: str, v: str) -> None:
        """Adds a directed edge `u -> v` after verifying the DAG acyclicity invariant."""
        self._ensure_node(u)
        self._ensure_node(v)
        if v in self.adj[u]:
            return
        if self._creates_cycle(u, v):
            raise CycleDetectedError(f"Cannot add edge '{u}' -> '{v}': cycle detected in TaxonomyDAG.")
        self.adj[u].append(v)

    def add_animal(self, record: AnimalRecord) -> None:
        """Inserts an AnimalRecord and builds its Kingdom -> Class -> Order -> Animal path in the DAG."""
        canonical = record.name.lower().strip()
        kingdom_node = f"Kingdom:{record.kingdom}"
        class_node = f"Class:{record.animal_class}"
        order_node = f"Order:{record.order}"
        animal_node = f"Animal:{canonical}"

        self._ensure_node(kingdom_node, level="Kingdom", label=record.kingdom)
        self._ensure_node(class_node, level="Class", label=record.animal_class)
        self._ensure_node(order_node, level="Order", label=record.order)
        self._ensure_node(
            animal_node,
            level="Animal",
            label=record.display_name,
            region=record.region,
            trait=record.trait,
            record=record,
        )

        self.add_edge(kingdom_node, class_node)
        self.add_edge(class_node, order_node)
        self.add_edge(order_node, animal_node)

        self.animals_by_name[canonical] = record
        for accepted in record.all_accepted_names():
            self.alias_to_canonical[accepted] = canonical

    def resolve_canonical_name(self, name_or_alias: str) -> Optional[str]:
        """Resolves a canonical name or short alias (e.g., 'elephant' -> 'african elephant')."""
        key = name_or_alias.lower().strip()
        return self.alias_to_canonical.get(key)

    def get_animal(self, name_or_alias: str) -> Optional[AnimalRecord]:
        """Fetches the AnimalRecord by canonical name or alias."""
        canonical = self.resolve_canonical_name(name_or_alias)
        if canonical is None:
            return None
        return self.animals_by_name.get(canonical)

    def get_all_animals(self) -> List[AnimalRecord]:
        """Returns all registered AnimalRecord instances in insertion order."""
        return list(self.animals_by_name.values())

    def bfs_lineage_path(self, animal_name: str) -> List[str]:
        """
        Executes Breadth-First Search (BFS) from `Kingdom:Animalia` to `Animal:<canonical_name>`
        and returns the reconstructed list of DAG node IDs along the shortest taxonomic path.
        """
        canonical = self.resolve_canonical_name(animal_name)
        if canonical is None:
            raise KeyError(f"Animal '{animal_name}' not found in TaxonomyDAG.")

        target_node = f"Animal:{canonical}"
        queue: deque[str] = deque([self.ROOT_NODE])
        parent_map: Dict[str, Optional[str]] = {self.ROOT_NODE: None}

        while queue:
            current = queue.popleft()
            if current == target_node:
                break
            for neighbor in self.adj.get(current, []):
                if neighbor not in parent_map:
                    parent_map[neighbor] = current
                    queue.append(neighbor)

        if target_node not in parent_map:
            raise RuntimeError(f"Target node '{target_node}' is unreachable from '{self.ROOT_NODE}'.")

        # Reconstruct path from root to target animal node
        path: List[str] = []
        cursor: Optional[str] = target_node
        while cursor is not None:
            path.append(cursor)
            cursor = parent_map[cursor]
        path.reverse()
        return path

    def bfs_generate_hints(self, animal_name: str) -> List[str]:
        """
        Performs Breadth-First Search (BFS) across the Taxonomy DAG to locate `animal_name`
        and dynamically generates the ordered 3-hint progression:
          - Hint 1 (Cost 25 pts -> 75 pts remaining): Taxonomic Class & Order discovered via BFS path.
          - Hint 2 (Cost 25 pts -> 50 pts remaining): Geographic Region & Habitat.
          - Hint 3 (Cost 50 pts ->  0 pts remaining): Specific Diagnostic Trait.
        """
        path = self.bfs_lineage_path(animal_name)
        animal_node = path[-1]
        meta = self.node_meta[animal_node]
        record: AnimalRecord = meta["record"]

        # Extract taxonomic labels traversed along the BFS lineage (excluding the secret animal leaf itself)
        lineage_labels: List[str] = []
        for node_id in path[:-1]:
            n_meta = self.node_meta.get(node_id, {})
            level = n_meta.get("level", "")
            label = n_meta.get("label", node_id)
            lineage_labels.append(f"{level}: {label}" if level else label)

        lineage_str = " → ".join(lineage_labels)
        hint_1 = f"Taxonomic Class: {record.animal_class} ({lineage_str})"
        hint_2 = f"Region / Habitat: {record.region}"
        hint_3 = f"Specific Trait: {record.trait}"
        return [hint_1, hint_2, hint_3]


# ==============================================================================
# 3. PREFIX TRIE & LEVENSHTEIN AUTOMATON (NFA INTERSECTION)
# ==============================================================================

class TrieNode:
    """Single character node inside the `PrefixTrie`."""

    __slots__ = ("children", "is_end", "word", "canonical_name")

    def __init__(self) -> None:
        self.children: Dict[str, TrieNode] = {}
        self.is_end: bool = False
        self.word: Optional[str] = None
        self.canonical_name: Optional[str] = None


class PrefixTrie:
    """
    Prefix Tree (Trie) storing valid animal names and aliases for fast prefix
    and Levenshtein NFA intersection queries.
    """

    def __init__(self) -> None:
        self.root = TrieNode()
        self.size = 0

    def insert(self, word: str, canonical_name: Optional[str] = None) -> None:
        """Inserts `word` into the Trie and binds it to `canonical_name` (defaults to `word`)."""
        cleaned = word.lower().strip()
        if not cleaned:
            return
        canonical = (canonical_name or cleaned).lower().strip()
        node = self.root
        for ch in cleaned:
            if ch not in node.children:
                node.children[ch] = TrieNode()
            node = node.children[ch]
        if not node.is_end:
            self.size += 1
        node.is_end = True
        node.word = cleaned
        node.canonical_name = canonical

    def populate_from_dag(self, dag: TaxonomyDAG) -> None:
        """Populates the Trie with all canonical animal names and aliases from a `TaxonomyDAG`."""
        for record in dag.get_all_animals():
            for accepted in record.all_accepted_names():
                self.insert(accepted, canonical_name=record.name)

    def search_exact(self, word: str) -> bool:
        """Returns True if `word` exists as a complete entry in the Trie in O(m) time."""
        cleaned = word.lower().strip()
        node = self.root
        for ch in cleaned:
            if ch not in node.children:
                return False
            node = node.children[ch]
        return node.is_end

    def resolve_exact(self, word: str) -> Optional[str]:
        """Returns the canonical animal name if `word` is an exact match in the Trie."""
        cleaned = word.lower().strip()
        node = self.root
        for ch in cleaned:
            if ch not in node.children:
                return None
            node = node.children[ch]
        return node.canonical_name if node.is_end else None


class LevenshteinNFAInstance:
    """
    Explicit Non-Deterministic Finite Automaton (NFA) for a fixed pattern `P` of length `m`
    and maximum Levenshtein edit distance `k`.

    Each NFA state is a tuple `(index, errors)` where:
      - `0 <= index <= m` is the character position in `P`
      - `0 <= errors <= k` is the number of edit operations (insertions, deletions, substitutions) consumed.

    Supports both:
      1. Explicit NFA state-set stepping with epsilon-closure (deletion transitions).
      2. O(m) state-vector stepping over a `PrefixTrie` with branch pruning whenever `min(state) > k`.
    """

    def __init__(self, pattern: str, max_dist: int = 2) -> None:
        self.pattern: str = pattern.lower().strip()
        self.m: int = len(self.pattern)
        self.max_dist: int = max(0, max_dist)

    def initial_nfa_states(self) -> Set[Tuple[int, int]]:
        """
        Returns the epsilon-closure of the start state `(0, 0)`:
        deleting up to `max_dist` prefix characters from the pattern consumes `e` errors at index `e`.
        """
        return {(e, e) for e in range(min(self.m, self.max_dist) + 1)}

    def epsilon_closure(self, states: Set[Tuple[int, int]]) -> Set[Tuple[int, int]]:
        """
        Expands a set of `(index, errors)` NFA states along epsilon (deletion) edges:
        from `(i, e)`, we can skip `pattern[i]` without reading input to reach `(i + 1, e + 1)`.
        """
        closure = set(states)
        queue = deque(states)
        while queue:
            idx, err = queue.popleft()
            if idx < self.m and err < self.max_dist:
                next_state = (idx + 1, err + 1)
                if next_state not in closure:
                    closure.add(next_state)
                    queue.append(next_state)
        return closure

    def step_nfa_states(self, states: Set[Tuple[int, int]], ch: str) -> Set[Tuple[int, int]]:
        """
        Transitions a set of `(index, errors)` NFA states on reading character `ch`,
        applying match, insertion, and substitution transitions followed by epsilon-closure.
        """
        next_raw: Set[Tuple[int, int]] = set()
        for idx, err in states:
            # 1. Match or Substitution transition (consumes pattern[idx] and input ch)
            if idx < self.m:
                if self.pattern[idx] == ch:
                    next_raw.add((idx + 1, err))
                elif err < self.max_dist:
                    next_raw.add((idx + 1, err + 1))
            # 2. Insertion transition (consumes input ch while staying at idx)
            if err < self.max_dist:
                next_raw.add((idx, err + 1))

        # 3. Epsilon closure (deletion transitions) + dominate/minimize error per index
        closed = self.epsilon_closure(next_raw)
        best_per_idx: Dict[int, int] = {}
        for idx, err in closed:
            if err <= self.max_dist:
                if idx not in best_per_idx or err < best_per_idx[idx]:
                    best_per_idx[idx] = err
        return {(idx, err) for idx, err in best_per_idx.items()}

    def is_accepting(self, states: Set[Tuple[int, int]]) -> Tuple[bool, int]:
        """
        Returns `(True, min_dist)` if any state in `states` can reach the final index `m`
        within `max_dist` errors, else `(False, max_dist + 1)`.
        """
        best = self.max_dist + 1
        for idx, err in states:
            remaining = self.m - idx
            total_err = err + remaining
            if total_err <= self.max_dist and total_err < best:
                best = total_err
        return (best <= self.max_dist, best)

    def initial_vector(self) -> List[int]:
        """Returns the initial O(m) NFA distance vector `[0, 1, 2, ..., m]` capped at `max_dist + 1`."""
        cap = self.max_dist + 1
        return [min(i, cap) for i in range(self.m + 1)]

    def step_vector(self, prev_vec: List[int], ch: str) -> List[int]:
        """
        O(m) transition of the NFA distance vector upon reading character `ch` in the Trie.
        Equivalent to evaluating all active `(index, errors)` NFA states in parallel.
        """
        cap = self.max_dist + 1
        new_vec = [min(prev_vec[0] + 1, cap)]
        for i in range(1, self.m + 1):
            cost = 0 if self.pattern[i - 1] == ch else 1
            substitution = prev_vec[i - 1] + cost
            insertion = prev_vec[i] + 1
            deletion = new_vec[i - 1] + 1
            new_vec.append(min(substitution, insertion, deletion, cap))
        return new_vec


class LevenshteinAutomaton:
    """
    High-level Levenshtein Automaton service intersecting `LevenshteinNFAInstance` with
    `PrefixTrie` via Depth-First Search (DFS) with branch pruning.

    Complexity per query of length `m`:
      - Each visited Trie edge executes in O(m) time.
      - Any Trie subtree whose minimum active NFA state distance exceeds `max_dist` is
        immediately pruned (`min(state_vec) > max_dist`), avoiding full dictionary scans.
    """

    @staticmethod
    def effective_max_dist(word_len: int, requested_max_dist: int = 2) -> int:
        """
        Scales typo tolerance safely for very short words so 2 typos on a 3-letter word
        cannot match an arbitrary 3-letter word:
          - len <= 2: 0 typos
          - len <= 4: up to 1 typo
          - len >= 5: up to requested_max_dist (default 2 typos)
        """
        if word_len <= 2:
            return 0
        if word_len <= 4:
            return min(1, requested_max_dist)
        return requested_max_dist

    @classmethod
    def fuzzy_search_trie(
        cls,
        query: str,
        trie: PrefixTrie,
        max_dist: int = 2,
    ) -> Tuple[bool, Optional[str], int]:
        """
        Simultaneously steps the Levenshtein NFA and traverses the `PrefixTrie` via DFS.
        Prunes any Trie branch where the minimum active NFA state error exceeds `max_dist`.

        Returns:
            `(matched: bool, canonical_animal_name: Optional[str], best_distance: int)`
        """
        cleaned_query = " ".join(query.lower().strip().split())
        if not cleaned_query:
            return (False, None, max_dist + 1)

        eff_max = cls.effective_max_dist(len(cleaned_query), max_dist)
        nfa = LevenshteinNFAInstance(cleaned_query, eff_max)
        init_vec = nfa.initial_vector()
        init_states = nfa.initial_nfa_states()

        best_dist = eff_max + 1
        best_canonical: Optional[str] = None
        best_word_len: int = 0

        def _dfs(node: TrieNode, vec: List[int], nfa_states: Set[Tuple[int, int]]) -> None:
            nonlocal best_dist, best_canonical, best_word_len

            if node.is_end and node.canonical_name is not None:
                accepted, dist_nfa = nfa.is_accepting(nfa_states)
                dist_vec = vec[nfa.m]
                dist = min(dist_nfa, dist_vec)
                word_len = len(node.word or "")
                allowed = min(eff_max, cls.effective_max_dist(word_len, max_dist))
                if accepted and dist <= allowed:
                    # Prefer strictly smaller edit distance; break ties by longer matched word
                    if dist < best_dist or (dist == best_dist and word_len > best_word_len):
                        best_dist = dist
                        best_canonical = node.canonical_name
                        best_word_len = word_len

            # Explore Trie children in deterministic order
            for ch, child in node.children.items():
                next_vec = nfa.step_vector(vec, ch)
                # PRUNING CONDITION: if every NFA state exceeds eff_max, prune entire subtree
                if min(next_vec) <= eff_max:
                    next_states = nfa.step_nfa_states(nfa_states, ch)
                    if next_states:
                        _dfs(child, next_vec, next_states)

        _dfs(trie.root, init_vec, init_states)
        if best_canonical is not None and best_dist <= eff_max:
            return (True, best_canonical, best_dist)
        return (False, None, max_dist + 1)

    @classmethod
    def fuzzy_match(
        cls,
        query: str,
        trie: PrefixTrie,
        max_dist: int = 2,
    ) -> Tuple[bool, Optional[str], int]:
        """Alias for `fuzzy_search_trie` matching the SSOT contract."""
        return cls.fuzzy_search_trie(query=query, trie=trie, max_dist=max_dist)

    @classmethod
    def matches_target(
        cls,
        query: str,
        target: str,
        max_dist: int = 2,
    ) -> Tuple[bool, int]:
        """
        Evaluates whether `query` matches `target` within `max_dist` edit distance
        by intersecting the Levenshtein NFA with a mini-Trie built from `target`.
        """
        mini_trie = PrefixTrie()
        mini_trie.insert(target, canonical_name=target)
        matched, _, dist = cls.fuzzy_search_trie(query, mini_trie, max_dist=max_dist)
        return (matched, dist)

    @classmethod
    def matches_animal(
        cls,
        query: str,
        target_record: AnimalRecord,
        max_dist: int = 2,
    ) -> Tuple[bool, int]:
        """
        Evaluates whether the player's `query` matches `target_record` (either its full
        canonical name or any of its registered aliases) within `max_dist` typos.
        """
        mini_trie = PrefixTrie()
        for accepted in target_record.all_accepted_names():
            mini_trie.insert(accepted, canonical_name=target_record.name)
        matched, _, dist = cls.fuzzy_search_trie(query, mini_trie, max_dist=max_dist)
        return (matched, dist)


# ==============================================================================
# 4. MAX-HEAP LEADERBOARD (PRIORITY QUEUE FROM SCRATCH)
# ==============================================================================

@dataclass
class LeaderboardEntry:
    """Single entry stored inside the Binary Max-Heap."""
    player_name: str
    score: int
    timestamp: float = field(default_factory=time.time)

    def sort_key(self) -> Tuple[int, float]:
        """
        Max-Heap comparison key:
          1. Higher `score` has strictly higher priority.
          2. Earlier `timestamp` wins ties (`-timestamp` is larger for earlier entries).
        """
        return (self.score, -self.timestamp)


class MaxHeapLeaderboard:
    """
    Array-backed Binary Max-Heap implemented from scratch (without `heapq`) to provide:
      - O(1) top-player lookup (`get_top()`)
      - O(log n) score insertion (`insert()`) via `_sift_up`
      - O(log n) max extraction (`extract_max()`) via `_sift_down`
    """

    def __init__(self, seed_defaults: bool = True) -> None:
        self._heap: List[LeaderboardEntry] = []
        if seed_defaults:
            self.seed_defaults()

    def __len__(self) -> int:
        return len(self._heap)

    @staticmethod
    def _parent(idx: int) -> int:
        return (idx - 1) // 2

    @staticmethod
    def _left(idx: int) -> int:
        return 2 * idx + 1

    @staticmethod
    def _right(idx: int) -> int:
        return 2 * idx + 2

    def _higher_priority(self, i: int, j: int) -> bool:
        """Returns True if entry at index `i` has strictly higher priority than index `j`."""
        return self._heap[i].sort_key() > self._heap[j].sort_key()

    def _swap(self, i: int, j: int) -> None:
        self._heap[i], self._heap[j] = self._heap[j], self._heap[i]

    def _sift_up(self, idx: int) -> None:
        """Restores the Max-Heap property upwards from `idx` in O(log n) time."""
        while idx > 0:
            parent_idx = self._parent(idx)
            if self._higher_priority(idx, parent_idx):
                self._swap(idx, parent_idx)
                idx = parent_idx
            else:
                break

    def _sift_down(self, idx: int) -> None:
        """Restores the Max-Heap property downwards from `idx` in O(log n) time."""
        n = len(self._heap)
        while True:
            largest = idx
            left = self._left(idx)
            right = self._right(idx)

            if left < n and self._higher_priority(left, largest):
                largest = left
            if right < n and self._higher_priority(right, largest):
                largest = right

            if largest != idx:
                self._swap(idx, largest)
                idx = largest
            else:
                break

    def insert(self, player_name: str, score: int) -> None:
        """
        Inserts or updates a player's high score in the Max-Heap in O(log n) time.
        If the player already exists with a lower score, updates their score and sifts up;
        otherwise appends a new node and sifts up.
        """
        cleaned_name = player_name.strip() or "Anonymous Ranger"
        int_score = int(score)

        # Check if player already has an entry; if so, keep their personal best
        for i, entry in enumerate(self._heap):
            if entry.player_name.lower() == cleaned_name.lower():
                if int_score > entry.score:
                    entry.score = int_score
                    entry.timestamp = time.time()
                    self._sift_up(i)
                    self._sift_down(i)
                return

        entry = LeaderboardEntry(player_name=cleaned_name, score=int_score, timestamp=time.time())
        self._heap.append(entry)
        self._sift_up(len(self._heap) - 1)

    def get_top(self) -> Optional[Tuple[str, int]]:
        """O(1) retrieval of the highest-scoring player without modifying the heap."""
        if not self._heap:
            return None
        top = self._heap[0]
        return (top.player_name, top.score)

    def extract_max(self) -> Optional[Tuple[str, int]]:
        """Removes and returns the highest-scoring player in O(log n) time."""
        if not self._heap:
            return None
        top = self._heap[0]
        last = self._heap.pop()
        if self._heap:
            self._heap[0] = last
            self._sift_down(0)
        return (top.player_name, top.score)

    def get_top_k(self, k: int = 10) -> List[Tuple[str, int]]:
        """
        Returns the top `k` `(player_name, score)` tuples in descending order by cloning
        the internal heap array and performing `k` O(log n) extractions.
        """
        if not self._heap or k <= 0:
            return []
        clone = MaxHeapLeaderboard(seed_defaults=False)
        clone._heap = [copy.copy(e) for e in self._heap]
        result: List[Tuple[str, int]] = []
        limit = min(k, len(clone._heap))
        for _ in range(limit):
            item = clone.extract_max()
            if item is not None:
                result.append(item)
        return result

    def verify_heap_invariant(self) -> bool:
        """Verifies that every parent node has priority >= its left and right children."""
        n = len(self._heap)
        for i in range(n):
            left = self._left(i)
            right = self._right(i)
            if left < n and self._higher_priority(left, i):
                return False
            if right < n and self._higher_priority(right, i):
                return False
        return True

    def seed_defaults(self) -> None:
        """Seeds the arcade leaderboard with baseline rangers so the UI is populated on launch."""
        defaults = [
            ("Darwin_1859", 950),
            ("Linnaeus_Taxon", 825),
            ("Jane_Goodall", 775),
            ("Attenborough", 700),
            ("Steve_Irwin", 650),
        ]
        base_time = time.time() - 3600
        for offset, (name, sc) in enumerate(defaults):
            entry = LeaderboardEntry(player_name=name, score=sc, timestamp=base_time + offset)
            self._heap.append(entry)
            self._sift_up(len(self._heap) - 1)


# ==============================================================================
# 5. SELF-BALANCING AVL TREE FOR MULTIPLAYER MMR MATCHMAKING
# ==============================================================================

class AVLNode:
    """Node inside the self-balancing `AVLTreeMMR`."""

    __slots__ = ("player_id", "mmr", "wins", "games", "height", "left", "right")

    def __init__(self, player_id: str, mmr: int, wins: int = 0, games: int = 0) -> None:
        self.player_id: str = player_id
        self.mmr: int = int(mmr)
        self.wins: int = int(wins)
        self.games: int = int(games)
        self.height: int = 1
        self.left: Optional[AVLNode] = None
        self.right: Optional[AVLNode] = None

    @property
    def key(self) -> Tuple[int, str]:
        """Composite BST ordering key `(mmr, player_id.lower())` for strict total ordering."""
        return (self.mmr, self.player_id.lower())

    def to_dict(self) -> dict:
        win_rate = round((self.wins / self.games) * 100.0, 1) if self.games > 0 else 0.0
        return {
            "player_id": self.player_id,
            "mmr": self.mmr,
            "wins": self.wins,
            "games": self.games,
            "win_rate": win_rate,
            "height": self.height,
        }


class AVLTreeMMR:
    """
    Self-Balancing AVL Binary Search Tree maintaining player Matchmaking Ratings (MMR).
    Guarantees height-balanced O(log n) insertions, deletions, updates, and nearest-MMR
    opponent lookups via explicit Left-Left (LL), Right-Right (RR), Left-Right (LR),
    and Right-Left (RL) rotations.
    """

    def __init__(self, seed_defaults: bool = True) -> None:
        self.root: Optional[AVLNode] = None
        self._player_index: Dict[str, AVLNode] = {}
        if seed_defaults:
            self.seed_defaults()

    def __len__(self) -> int:
        return len(self._player_index)

    @staticmethod
    def _get_height(node: Optional[AVLNode]) -> int:
        return node.height if node is not None else 0

    @classmethod
    def _update_height(cls, node: AVLNode) -> None:
        node.height = 1 + max(cls._get_height(node.left), cls._get_height(node.right))

    @classmethod
    def _get_balance(cls, node: Optional[AVLNode]) -> int:
        if node is None:
            return 0
        return cls._get_height(node.left) - cls._get_height(node.right)

    @classmethod
    def _rotate_right(cls, z: AVLNode) -> AVLNode:
        """Right rotation (fixes Left-Left heavy imbalance at `z`)."""
        y = z.left
        assert y is not None
        t3 = y.right

        # Perform rotation
        y.right = z
        z.left = t3

        # Update heights bottom-up
        cls._update_height(z)
        cls._update_height(y)
        return y

    @classmethod
    def _rotate_left(cls, z: AVLNode) -> AVLNode:
        """Left rotation (fixes Right-Right heavy imbalance at `z`)."""
        y = z.right
        assert y is not None
        t2 = y.left

        # Perform rotation
        y.left = z
        z.right = t2

        # Update heights bottom-up
        cls._update_height(z)
        cls._update_height(y)
        return y

    @classmethod
    def _rebalance(cls, node: AVLNode) -> AVLNode:
        """Updates height of `node` and executes LL, RR, LR, or RL rotations if |balance| > 1."""
        cls._update_height(node)
        balance = cls._get_balance(node)

        # Left heavy (LL or LR)
        if balance > 1:
            assert node.left is not None
            if cls._get_balance(node.left) < 0:
                # Left-Right (LR) case
                node.left = cls._rotate_left(node.left)
            # Left-Left (LL) case
            return cls._rotate_right(node)

        # Right heavy (RR or RL)
        if balance < -1:
            assert node.right is not None
            if cls._get_balance(node.right) > 0:
                # Right-Left (RL) case
                node.right = cls._rotate_right(node.right)
            # Right-Right (RR) case
            return cls._rotate_left(node)

        return node

    def _insert_node(self, root: Optional[AVLNode], new_node: AVLNode) -> AVLNode:
        if root is None:
            return new_node

        if new_node.key < root.key:
            root.left = self._insert_node(root.left, new_node)
        elif new_node.key > root.key:
            root.right = self._insert_node(root.right, new_node)
        else:
            # Exact key match: update statistics in place
            root.wins = new_node.wins
            root.games = new_node.games
            return root

        return self._rebalance(root)

    @staticmethod
    def _min_value_node(node: AVLNode) -> AVLNode:
        curr = node
        while curr.left is not None:
            curr = curr.left
        return curr

    def _delete_node(self, root: Optional[AVLNode], target_key: Tuple[int, str]) -> Optional[AVLNode]:
        if root is None:
            return None

        if target_key < root.key:
            root.left = self._delete_node(root.left, target_key)
        elif target_key > root.key:
            root.right = self._delete_node(root.right, target_key)
        else:
            # Node with only one child or no child
            if root.left is None:
                return root.right
            if root.right is None:
                return root.left

            # Node with two children: copy inorder successor's payload
            successor = self._min_value_node(root.right)
            root.player_id = successor.player_id
            root.mmr = successor.mmr
            root.wins = successor.wins
            root.games = successor.games
            self._player_index[root.player_id.lower()] = root
            root.right = self._delete_node(root.right, successor.key)

        return self._rebalance(root)

    def upsert_player(self, player_id: str, mmr: int, wins: int = 0, games: int = 0) -> dict:
        """
        Inserts a new player or updates an existing player's MMR and match statistics,
        re-balancing the AVL tree in O(log n) time.
        """
        cleaned_id = player_id.strip() or "Player"
        lookup_key = cleaned_id.lower()

        if lookup_key in self._player_index:
            old_node = self._player_index.pop(lookup_key)
            self.root = self._delete_node(self.root, old_node.key)

        new_node = AVLNode(player_id=cleaned_id, mmr=int(mmr), wins=int(wins), games=int(games))
        self._player_index[lookup_key] = new_node
        self.root = self._insert_node(self.root, new_node)
        return new_node.to_dict()

    def get_player(self, player_id: str) -> Optional[dict]:
        """Returns the player's MMR record dict if registered, else None."""
        node = self._player_index.get(player_id.strip().lower())
        return node.to_dict() if node is not None else None

    def update_match_result(
        self,
        p1_id: str,
        p2_id: str,
        p1_won: Optional[bool] = True,
        is_draw: bool = False,
        k_factor: int = 32,
    ) -> Tuple[dict, dict]:
        """
        Updates Elo/MMR ratings for `p1_id` and `p2_id` after a head-to-head match
        and re-balances both nodes inside the AVL tree.
          - `is_draw = True` or `p1_won = None` -> Draw
          - `p1_won = True`                     -> `p1_id` (or `winner_id`) won
          - `p1_won = False`                    -> `p2_id` won
        """
        if is_draw:
            p1_won = None
        p1_rec = self.get_player(p1_id) or self.upsert_player(p1_id, mmr=1200, wins=0, games=0)
        p2_rec = self.get_player(p2_id) or self.upsert_player(p2_id, mmr=1200, wins=0, games=0)

        r1 = p1_rec["mmr"]
        r2 = p2_rec["mmr"]

        expected_1 = 1.0 / (1.0 + 10.0 ** ((r2 - r1) / 400.0))
        expected_2 = 1.0 - expected_1

        if p1_won is True:
            score_1, score_2 = 1.0, 0.0
            w1, w2 = p1_rec["wins"] + 1, p2_rec["wins"]
        elif p1_won is False:
            score_1, score_2 = 0.0, 1.0
            w1, w2 = p1_rec["wins"], p2_rec["wins"] + 1
        else:
            score_1, score_2 = 0.5, 0.5
            w1, w2 = p1_rec["wins"], p2_rec["wins"]

        new_r1 = max(100, int(round(r1 + k_factor * (score_1 - expected_1))))
        new_r2 = max(100, int(round(r2 + k_factor * (score_2 - expected_2))))

        updated_1 = self.upsert_player(p1_id, mmr=new_r1, wins=w1, games=p1_rec["games"] + 1)
        updated_2 = self.upsert_player(p2_id, mmr=new_r2, wins=w2, games=p2_rec["games"] + 1)
        return (updated_1, updated_2)

    def find_closest_match(
        self,
        target_mmr: int,
        exclude_player: Optional[str] = None,
    ) -> Optional[dict]:
        """
        Traverses the AVL Tree in O(log n) time to locate the player whose MMR is closest
        to `target_mmr` (excluding `exclude_player` if specified).
        """
        exclude_key = exclude_player.strip().lower() if exclude_player else None
        best_node: Optional[AVLNode] = None
        best_diff: int = 10**9

        def _search(node: Optional[AVLNode]) -> None:
            nonlocal best_node, best_diff
            if node is None:
                return

            if node.player_id.lower() != exclude_key:
                diff = abs(node.mmr - target_mmr)
                if diff < best_diff or (diff == best_diff and (best_node is None or node.mmr > best_node.mmr)):
                    best_diff = diff
                    best_node = node

            # Binary search branch selection
            if target_mmr < node.mmr:
                _search(node.left)
                # Only check the other side if an excluded player forced us to miss a close neighbor
                if best_node is None or abs(node.mmr - target_mmr) <= best_diff:
                    _search(node.right)
            elif target_mmr > node.mmr:
                _search(node.right)
                if best_node is None or abs(node.mmr - target_mmr) <= best_diff:
                    _search(node.left)
            else:
                _search(node.left)
                _search(node.right)

        _search(self.root)
        return best_node.to_dict() if best_node is not None else None

    def inorder_rankings(self) -> List[dict]:
        """
        Performs a Reverse In-Order traversal (`Right -> Root -> Left`) of the AVL Tree
        to return all players sorted in descending order of MMR in O(n) time.
        """
        rankings: List[dict] = []

        def _reverse_inorder(node: Optional[AVLNode]) -> None:
            if node is None:
                return
            _reverse_inorder(node.right)
            entry = node.to_dict()
            entry["rank"] = len(rankings) + 1
            rankings.append(entry)
            _reverse_inorder(node.left)

        _reverse_inorder(self.root)
        return rankings

    def verify_balance(self) -> bool:
        """
        Recursively checks that every node in the AVL tree satisfies:
          1. `|balance_factor| <= 1`
          2. Strict BST key ordering (`left.key < node.key < right.key`)
          3. Correct cached subtree height
        """
        def _check(node: Optional[AVLNode], low: Optional[Tuple[int, str]], high: Optional[Tuple[int, str]]) -> bool:
            if node is None:
                return True
            if low is not None and not (low < node.key):
                return False
            if high is not None and not (node.key < high):
                return False
            balance = self._get_balance(node)
            if abs(balance) > 1:
                return False
            expected_h = 1 + max(self._get_height(node.left), self._get_height(node.right))
            if node.height != expected_h:
                return False
            return _check(node.left, low, node.key) and _check(node.right, node.key, high)

        return _check(self.root, None, None)

    def seed_defaults(self) -> None:
        """Pre-populates competitive players at various MMR tiers to showcase AVL rotations."""
        default_players = [
            ("Player 1", 1200, 5, 8),
            ("Player 2", 1200, 4, 8),
            ("Apex_Predator", 1540, 18, 22),
            ("Savanna_Scout", 1390, 12, 17),
            ("Bio_Grandmaster", 1680, 25, 28),
            ("Rookie_Tracker", 1060, 2, 7),
            ("Canopy_Explorer", 1285, 9, 15),
        ]
        for pid, mmr, wins, games in default_players:
            self.upsert_player(pid, mmr=mmr, wins=wins, games=games)


# ==============================================================================
# SELF-TEST SUITE
# ==============================================================================

def _run_self_tests() -> None:
    print("=" * 72)
    print("Running dsa_engine.py Self-Verification Suite...")
    print("=" * 72)

    # 1. Test TaxonomyDAG & BFS Hint Generation
    dag = TaxonomyDAG()
    animals = dag.get_all_animals()
    assert len(animals) >= 15, f"Expected >= 15 animals, got {len(animals)}"
    hints = dag.bfs_generate_hints("african elephant")
    assert len(hints) == 3
    assert "Mammalia" in hints[0] and "Proboscidea" in hints[0]
    assert "Sub-Saharan" in hints[1]
    assert "trunk" in hints[2]

    # Cycle detection test
    try:
        dag.add_edge("Animal:african elephant", "Kingdom:Animalia")
        raise AssertionError("CycleDetectedError was not raised!")
    except CycleDetectedError:
        pass
    print(f"[PASS] TaxonomyDAG verified ({len(animals)} animals, BFS hints & cycle guard active).")

    # 2. Test PrefixTrie & LevenshteinAutomaton (1-2 typo tolerance)
    trie = PrefixTrie()
    trie.populate_from_dag(dag)
    assert trie.search_exact("african elephant")
    assert trie.search_exact("elephant")
    assert not trie.search_exact("velociraptor")

    # Exact & fuzzy queries (1-2 character typos)
    m1, canon1, d1 = LevenshteinAutomaton.fuzzy_match("afrikan elephnt", trie, max_dist=2)
    assert m1 and canon1 == "african elephant" and d1 == 2, f"Got {(m1, canon1, d1)}"

    m2, canon2, d2 = LevenshteinAutomaton.fuzzy_match("elephnt", trie, max_dist=2)
    assert m2 and canon2 == "african elephant" and d2 == 1, f"Got {(m2, canon2, d2)}"

    m3, canon3, d3 = LevenshteinAutomaton.fuzzy_match("emperer pengun", trie, max_dist=2)
    assert m3 and canon3 == "emperor penguin" and d3 == 2, f"Got {(m3, canon3, d3)}"

    # Ensure unrelated word is rejected
    m4, canon4, _ = LevenshteinAutomaton.fuzzy_match("toaster oven", trie, max_dist=2)
    assert not m4 and canon4 is None

    elephant_rec = dag.get_animal("african elephant")
    assert elephant_rec is not None
    ok_target, dist_target = LevenshteinAutomaton.matches_animal("elefant", elephant_rec, max_dist=2)
    assert ok_target and dist_target == 2
    print("[PASS] PrefixTrie + LevenshteinAutomaton NFA intersection verified.")

    # 3. Test MaxHeapLeaderboard
    heap = MaxHeapLeaderboard(seed_defaults=True)
    heap.insert("Test_Champion", 1250)
    heap.insert("Mid_Tier", 500)
    assert heap.verify_heap_invariant()
    top = heap.get_top()
    assert top == ("Test_Champion", 1250), f"Unexpected top: {top}"
    top5 = heap.get_top_k(5)
    assert len(top5) == 5 and top5[0] == ("Test_Champion", 1250)
    assert heap.verify_heap_invariant()
    print(f"[PASS] MaxHeapLeaderboard verified (O(1) top={top}, invariant holds).")

    # 4. Test AVLTreeMMR
    avl = AVLTreeMMR(seed_defaults=True)
    # Stress-test sequential insertions (would degenerate a plain BST into a linked list)
    for idx in range(20):
        avl.upsert_player(f"StressBot_{idx}", mmr=1000 + idx * 50, wins=idx, games=idx + 2)
    assert avl.verify_balance(), "AVL Tree balance or BST invariant violated after insertions!"

    avl.update_match_result("Player 1", "Player 2", p1_won=True)
    assert avl.verify_balance(), "AVL Tree balance violated after match update!"

    closest = avl.find_closest_match(1215, exclude_player="Player 1")
    assert closest is not None and closest["player_id"] != "Player 1"
    rankings = avl.inorder_rankings()
    mmrs = [r["mmr"] for r in rankings]
    assert mmrs == sorted(mmrs, reverse=True), "AVL inorder_rankings not sorted descending!"
    print(f"[PASS] AVLTreeMMR verified ({len(rankings)} players, root height={avl.root.height if avl.root else 0}).")
    print("=" * 72)
    print("ALL 4 CORE DSA MODULES PASSED SELF-TESTS SUCCESSFULLY.")
    print("=" * 72)


if __name__ == "__main__":
    _run_self_tests()
