"""
dialog_engine.py
================
Parses a .rug dialog script and matches user utterances to rules.
Returns (speak_text, [action_names]) — no robot calls here.

Supported features:
  - # comments, blank lines, whitespace tolerance
  - ~definitions
  - [] choice lists in patterns and outputs (including quoted phrases)
  - variable capture with _ and $var recall
  - nested scopes u, u1, u2, u3, ...
  - action tags: <tag_name>
  - unknown action tag: warns and ignores
  - deliberate syntax errors: reports line number and skips rule
"""

import re
import random
import logging

logger = logging.getLogger(__name__)

# ── Known valid action tags (mapped in action_runner.py) ────────────────────
VALID_ACTIONS = {
    "head_yes",
    "head_no",
    "arm_raise",
    "dance90",
    "wave",
    "home",
    "stop",
    "forward",
    "backward",
    "turn_left",
    "turn_right",
    "center_head",
    "open_gripper",
    "close_gripper",
}

# ── Regex helpers ────────────────────────────────────────────────────────────
_ACTION_RE  = re.compile(r"<(\w+)>")
_BRACKET_RE = re.compile(r"\[([^\]]*)\]")
_DEF_LINE   = re.compile(r"^\s*~(\w+)\s*:\s*\[([^\]]*)\]\s*$")
_RULE_LINE  = re.compile(r"^\s*(u\d*)\s*:\s*\((.+?)\)\s*:\s*(.+?)\s*$", re.DOTALL)


def _infer_var_name(pattern: str, position: int, index: int) -> str:
    """
    Try to infer a sensible variable name from the words around the _ wildcard.
    Checks words after _ first (they're most specific), then words before.
    Falls back to positional names.
    """
    POSITIONAL = ["name", "age", "color", "item", "var4", "var5"]
    hints = {
        "name": "name", "called": "name",
        "age": "age", "old": "age", "years": "age",
        "color": "color", "colour": "color",
        "like": "item", "want": "item",
    }
    # words after the underscore (more context-specific)
    after  = pattern[position:].strip().split()
    before = pattern[:position].strip().split()

    for word in after + list(reversed(before)):
        w = word.lower().rstrip("?.,!")
        if w in hints:
            return hints[w]
    return POSITIONAL[index] if index < len(POSITIONAL) else f"var{index}"


def _tokenize_choices(raw: str) -> list[str]:
    """Split a bracket body like: hello hi "hi there" into tokens."""
    tokens = []
    for m in re.finditer(r'"[^"]*"|\S+', raw):
        tokens.append(m.group().strip('"'))
    return tokens


def _expand_def(text: str, defs: dict[str, list[str]]) -> str:
    """Replace ~name in text with a regex alternation group."""
    def replacer(m):
        name = m.group(1)
        if name in defs:
            alts = [re.escape(t) for t in defs[name]]
            return "(?:" + "|".join(alts) + ")"
        return m.group(0)
    return re.sub(r"~(\w+)", replacer, text)


def _pattern_to_regex(pattern: str, defs: dict) -> tuple[re.Pattern, list[str]]:
    """
    Convert a .rug pattern string to a compiled regex.
    Returns (compiled_pattern, [capture_var_names]).

    Supports:
      ~definition  → alternation group
      [a b "c d"]  → alternation group
      _            → named capture group (sequential: name, age, …)
    """
    capture_names = []
    VAR_NAMES = ["name", "age", "color", "item", "var4", "var5"]

    p = pattern.strip()

    # expand ~defs first
    p = _expand_def(p, defs)

    # expand [choice lists]
    def expand_brackets(m):
        tokens = _tokenize_choices(m.group(1))
        alts = [re.escape(t) for t in tokens]
        return "(?:" + "|".join(alts) + ")"
    p = _BRACKET_RE.sub(expand_brackets, p)

    # replace _ with a named capture group
    # Count wildcards first so the last one can be greedy
    total_wildcards = len(re.findall(r"\b_\b", p))
    idx = [0]
    def replace_wildcard(m):
        vname = _infer_var_name(p, m.start(), idx[0])
        capture_names.append(vname)
        greed = ".+" if idx[0] == total_wildcards - 1 else ".+?"
        idx[0] += 1
        return f"(?P<{vname}>{greed})"
    p = re.sub(r"\b_\b", replace_wildcard, p)

    compiled = re.compile(r"^\s*" + p + r"\s*$", re.IGNORECASE)
    return compiled, capture_names


class Rule:
    def __init__(self, scope: str, pattern_re: re.Pattern,
                 raw_output: str, captures: list[str], line_no: int):
        self.scope      = scope          # "u", "u1", "u2", …
        self.pattern_re = pattern_re
        self.raw_output = raw_output     # un-expanded output string
        self.captures   = captures       # variable names from _
        self.line_no    = line_no


class DialogEngine:
    def __init__(self):
        self.defs:    dict[str, list[str]] = {}
        self.rules:   list[Rule]           = []
        self.scope:   str                  = "u"        # current active scope
        self.vars:    dict[str, str]       = {}         # captured variables
        self._scope_stack: list[str]       = ["u"]     # for nested scopes

    # ── Loading ──────────────────────────────────────────────────────────────

    def load(self, filepath: str):
        """Parse a .rug file.  Reports errors but never crashes."""
        self.defs.clear()
        self.rules.clear()
        self.vars.clear()
        self.scope = "u"
        self._scope_stack = ["u"]

        with open(filepath, "r", encoding="utf-8") as fh:
            lines = fh.readlines()

        for lineno, raw in enumerate(lines, start=1):
            line = raw.strip()

            # blank line or comment
            if not line or line.startswith("#"):
                continue

            # ~definition line
            if line.startswith("~"):
                m = _DEF_LINE.match(line)
                if m:
                    name   = m.group(1)
                    tokens = _tokenize_choices(m.group(2))
                    self.defs[name] = tokens
                    logger.debug("DEF ~%s = %s", name, tokens)
                else:
                    logger.warning("LINE %d: bad definition syntax — skipped: %s",
                                   lineno, line)
                continue

            # rule line  u…:(pattern):output
            m = _RULE_LINE.match(line)
            if not m:
                logger.warning("LINE %d: syntax error (missing delimiter or bad format)"
                               " — skipped: %s", lineno, line)
                continue

            scope_tag   = m.group(1).strip()   # "u", "u1", …
            pattern_raw = m.group(2).strip()
            output_raw  = m.group(3).strip()

            # check for unbalanced brackets in output
            if output_raw.count("[") != output_raw.count("]"):
                logger.warning("LINE %d: unbalanced brackets in output — skipped: %s",
                               lineno, line)
                continue

            try:
                pattern_re, captures = _pattern_to_regex(pattern_raw, self.defs)
            except re.error as exc:
                logger.warning("LINE %d: regex compile error (%s) — skipped: %s",
                               lineno, exc, line)
                continue

            rule = Rule(scope_tag, pattern_re, output_raw, captures, lineno)
            self.rules.append(rule)
            logger.debug("RULE line=%d scope=%s pattern=%s",
                         lineno, scope_tag, pattern_raw)

        logger.info("Loaded %d rules, %d definitions from %s",
                    len(self.rules), len(self.defs), filepath)

    # ── Matching ─────────────────────────────────────────────────────────────

    def _scope_level(self, tag: str) -> int:
        """'u' → 0,  'u1' → 1,  'u2' → 2, …"""
        if tag == "u":
            return 0
        try:
            return int(tag[1:])
        except ValueError:
            return 0

    def _active_scopes(self) -> set[str]:
        """
        Current scope 'uN' means rules at level 0..N are all candidates.
        """
        cur = self._scope_level(self.scope)
        active = {"u"}
        for i in range(1, cur + 1):
            active.add(f"u{i}")
        return active

    def process(self, utterance: str) -> tuple[str, list[str]]:
        """
        Match utterance against loaded rules (respecting current scope).
        Returns (speak_text, [action_names]).
        Updates internal state (scope, variables).
        """
        utt = utterance.strip()
        active = self._active_scopes()

        for rule in self.rules:
            if rule.scope not in active:
                continue

            m = rule.pattern_re.match(utt)
            if not m:
                continue

            # capture variables
            for vname in rule.captures:
                try:
                    self.vars[vname] = m.group(vname)
                except IndexError:
                    pass

            # Advance scope: matching a rule at level N means the NEXT
            # expected replies are at level N+1.
            # A top-level u rule (level 0) activates u1 children.
            # A u1 rule (level 1) activates u2 children, etc.
            cur_level = self._scope_level(rule.scope)
            MAX_DEPTH = 6
            next_level = cur_level + 1
            if next_level <= MAX_DEPTH:
                self.scope = f"u{next_level}"
            else:
                logger.warning("Max nesting depth %d reached — resetting scope to u",
                               MAX_DEPTH)
                self.scope = "u"

            speak, actions = self._render(rule.raw_output)
            return speak, actions

        # no match
        return "I didn't understand that.", []

    # ── Rendering ────────────────────────────────────────────────────────────

    def _render(self, raw_output: str) -> tuple[str, list[str]]:
        """
        Expand the output string:
          - strip action tags, validate, collect them
          - expand [] choice lists
          - expand ~defs
          - substitute $var references
        Returns (speak_text, [valid_action_names])
        """
        # 1. collect and remove action tags
        actions = []
        for tag in _ACTION_RE.findall(raw_output):
            if tag in VALID_ACTIONS:
                actions.append(tag)
            else:
                logger.warning("Unknown action tag <%s> — ignored", tag)
        text = _ACTION_RE.sub("", raw_output).strip()

        # 2. expand [] choice list in output (pick one at random)
        def pick_choice(m):
            tokens = _tokenize_choices(m.group(1))
            return random.choice(tokens) if tokens else ""
        text = _BRACKET_RE.sub(pick_choice, text)

        # 3. expand ~defs in output (pick one word from the definition)
        def pick_def(m):
            name = m.group(1)
            if name in self.defs and self.defs[name]:
                return random.choice(self.defs[name])
            return m.group(0)
        text = re.sub(r"~(\w+)", pick_def, text)

        # 4. substitute $var references
        def sub_var(m):
            vname = m.group(1)
            if vname in self.vars and self.vars[vname]:
                return self.vars[vname]
            return "I don't know"
        text = re.sub(r"\$(\w+)", sub_var, text)

        return text.strip(), actions

    # ── Scope helpers ─────────────────────────────────────────────────────────

    def reset_scope(self):
        """Reset conversation scope to top level."""
        self.scope = "u"

    def reset_all(self):
        """Full reset: scope + variables."""
        self.scope = "u"
        self.vars.clear()
