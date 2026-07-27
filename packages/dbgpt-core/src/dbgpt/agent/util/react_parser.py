import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from dbgpt.vis.tags.vis_thinking import VisThinking


@dataclass
class ReActStep:
    """
    Dataclass representing a single step in the ReAct pattern.
    """

    thought: Optional[str] = None
    phase: Optional[str] = None
    action_intention: Optional[str] = None
    action_reason: Optional[str] = None
    action: Optional[str] = None
    action_input: Optional[Any] = None
    observation: Optional[Any] = None
    is_terminal: bool = False


class ReActOutputParser:
    """
    Parser for ReAct format model outputs with configurable prefixes.
    This parser extracts structured information from language model outputs
    that follow the ReAct pattern: Thought -> Phase -> Action -> Action Input
    -> Observation.
    """

    def __init__(
        self,
        thought_prefix: str = "Thought:",
        phase_prefix: str = "Phase:",
        action_intention_prefix: str = "Action Intention:",
        action_reason_prefix: str = "Action Reason:",
        action_prefix: str = "Action:",
        action_input_prefix: str = "Action Input:",
        observation_prefix: str = "Observation:",
        terminate_action: str = "terminate",
    ):
        """
        Initialize the ReAct output parser with configurable prefixes.

        Args:
            thought_prefix: Prefix string that indicates the start of a thought.
            phase_prefix: Prefix string that indicates the start of a phase.
            action_intention_prefix: Prefix string that indicates the start of
                an action intention.
            action_reason_prefix: Prefix string that indicates the start of an
                action reason.
            action_prefix: Prefix string that indicates the start of an action.
            action_input_prefix: Prefix string that indicates the start of action input.
            observation_prefix: Prefix string that indicates the start of an
                observation.
            terminate_action: String that indicates termination action.
        """
        self.thought_prefix = thought_prefix
        self.phase_prefix = phase_prefix
        self.action_intention_prefix = action_intention_prefix
        self.action_reason_prefix = action_reason_prefix
        self.action_prefix = action_prefix
        self.action_input_prefix = action_input_prefix
        self.observation_prefix = observation_prefix
        self.terminate_action = terminate_action

        # Escape special regex characters in prefixes
        self.thought_prefix_escaped = re.escape(thought_prefix)
        self.phase_prefix_escaped = re.escape(phase_prefix)
        self.action_intention_prefix_escaped = re.escape(action_intention_prefix)
        self.action_reason_prefix_escaped = re.escape(action_reason_prefix)
        self.action_prefix_escaped = re.escape(action_prefix)
        self.action_input_prefix_escaped = re.escape(action_input_prefix)
        self.observation_prefix_escaped = re.escape(observation_prefix)

    def _prefix_line_pattern(self, escaped_prefix: str) -> str:
        """Build a regex for a ReAct prefix at the start of a logical line."""
        return rf"^[ \t]*{escaped_prefix}\s*"

    def _markdown_fence_spans(self, text: str) -> List[tuple[int, int]]:
        """Return markdown fenced-code spans so ReAct labels inside are ignored."""
        fence_pattern = re.compile(
            r"^[ \t]*(```+|~~~+)[^\n]*\n.*?^[ \t]*\1[ \t]*$",
            re.DOTALL | re.MULTILINE,
        )
        return [match.span() for match in fence_pattern.finditer(text)]

    @staticmethod
    def _is_in_spans(pos: int, spans: List[tuple[int, int]]) -> bool:
        return any(start <= pos < end for start, end in spans)

    def _find_prefix_matches(self, text: str, escaped_prefix: str) -> List[re.Match]:
        """Find line-start ReAct prefix matches outside markdown code fences."""
        pattern = re.compile(self._prefix_line_pattern(escaped_prefix), re.MULTILINE)
        fence_spans = self._markdown_fence_spans(text)
        return [
            match
            for match in pattern.finditer(text)
            if not self._is_in_spans(match.start(), fence_spans)
        ]

    def _mask_prefixes_in_fences(self, text: str) -> str:
        """Mask ReAct labels inside code fences while preserving string offsets."""
        chars = list(text)
        escaped_prefixes = (
            self.thought_prefix_escaped,
            self.phase_prefix_escaped,
            self.action_intention_prefix_escaped,
            self.action_reason_prefix_escaped,
            self.action_prefix_escaped,
            self.action_input_prefix_escaped,
            self.observation_prefix_escaped,
        )
        for start, end in self._markdown_fence_spans(text):
            fenced_text = text[start:end]
            for escaped_prefix in escaped_prefixes:
                pattern = re.compile(
                    self._prefix_line_pattern(escaped_prefix), re.MULTILINE
                )
                for match in pattern.finditer(fenced_text):
                    prefix_start = start + match.start()
                    while prefix_start < end and chars[prefix_start] in (" ", "\t"):
                        prefix_start += 1
                    if prefix_start < end:
                        chars[prefix_start] = "_"
        return "".join(chars)

    def _strip_vis_thinking_blocks(self, text: str) -> str:
        """Remove vis-thinking wrappers produced by reasoning model output."""
        fence = "`" * 6
        pattern = (
            rf"{re.escape(fence)}{re.escape(VisThinking.vis_tag())}"
            rf"\s*\n.*?\n{re.escape(fence)}\s*"
        )
        return re.sub(pattern, "", text, flags=re.DOTALL)

    def _strip_think_tags(self, text: str) -> str:
        """Convert <think>...</think> blocks from reasoning models into Thought: prefix.

        Handles two cases:
        1. <think> at the start of output (no Thought: prefix) -> add Thought: prefix
        2. Thought: <think>...</think> (already has prefix) -> just strip the tags
        """
        # Case 1: <think> follows "Thought:" prefix -> strip tags, keep content
        text = re.sub(
            r"(Thought:\s*)<think>(.*?)</think>\s*",
            r"\1\2\n",
            text,
            flags=re.DOTALL,
        )
        # Case 2: standalone <think> -> convert to Thought: prefix
        def _replace_think(m: re.Match) -> str:
            content = m.group(1).strip()
            return f"Thought: {content}\n\n" if content else ""

        return re.sub(
            r"<think>(.*?)</think>\s*", _replace_think, text, flags=re.DOTALL
        )

    def _strip_minimax_tool_call(self, text: str) -> str:
        """Convert MiniMax-style tool-call blocks into standard ReAct format.

        MiniMax models emit tool calls in several non-standard forms, all of
        which bypass the ReAct prefix the system prompt asks for:

        Form 1 — ``<minimax:tool_call>`` block::

            <minimax:tool_call>
            sql_query
            Action Input: {"sql": "SELECT ..."}

        Form 2 — ``<invoke>`` / ``<parameter>`` XML-ish tags::

            <invoke name="sql_query">
            <parameter name="sql">SELECT ...</parameter>
            </invoke>

        Both forms may be preceded by free-form natural language that should
        become the ``Thought:`` line. We rewrite any matched block into::

            Thought: <preceding natural-language text>
            Action: sql_query
            Action Input: {"sql": "SELECT ..."}

        so the standard ReAct regex matches. Unknown tags are left
        untouched.
        """
        # --- Form 1: <minimax:tool_call> ... </minimax:tool_call> ----------
        if "<minimax:tool_call>" in text:
            text = self._convert_minimax_block(text)

        # --- Form 2: <invoke name="..."> ... </invoke> --------------------
        if "<invoke " in text or "<invoke>" in text:
            text = self._convert_invoke_block(text)

        # --- Form 3: [TOOL_CALL]{tool => "...", args => {...}}[/TOOL_CALL] -
        if "[TOOL_CALL]" in text:
            text = self._convert_tool_call_block(text)

        return text

    @staticmethod
    def _convert_minimax_block(text: str) -> str:
        """Rewrite a single ``<minimax:tool_call>`` block."""
        before_tag, _, after_tag = text.partition("<minimax:tool_call>")
        after_tag = after_tag.replace("</minimax:tool_call>", "")
        after_tag = after_tag.strip("\n").strip()

        action_name = None
        rest = after_tag
        first_newline = after_tag.find("\n")
        if first_newline != -1:
            action_name = after_tag[:first_newline].strip()
            rest = after_tag[first_newline + 1 :].strip()
        else:
            idx = after_tag.find("Action Input:")
            if idx != -1:
                action_name = after_tag[:idx].strip()
                rest = after_tag[idx:].strip()

        thought_text = before_tag.strip() or "use tool"
        parts = [f"Thought: {thought_text}"]
        if action_name:
            parts.append(f"Action: {action_name}")
        if rest:
            parts.append(rest)
        return "\n".join(parts)

    @staticmethod
    def _convert_invoke_block(text: str) -> str:
        """Rewrite ``<invoke name="...">...</invoke>`` blocks.

        Extracts the tool name from the ``name`` attribute and each
        ``<parameter name="X">VALUE</parameter>`` pair into a JSON object,
        then emits standard ReAct prefixes.
        """
        invoke_pattern = re.compile(
            r"<invoke(?:\s+name=\"(?P<name>[^\"]+)\")?\s*>(?P<body>.*?)</invoke>",
            re.DOTALL,
        )
        param_pattern = re.compile(
            r"<parameter\s+name=\"(?P<key>[^\"]+)\">\s*(?P<val>.*?)\s*</parameter>",
            re.DOTALL,
        )

        def _replace(match: re.Match) -> str:
            tool_name = match.group("name") or ""
            body = match.group("body") or ""
            params: Dict[str, str] = {}
            for pm in param_pattern.finditer(body):
                params[pm.group("key")] = pm.group("val").strip()
            action_input = json.dumps(params, ensure_ascii=False) if params else ""
            out = [f"Action: {tool_name}"]
            if action_input:
                out.append(f"Action Input: {action_input}")
            return "\n".join(out)

        new_text = invoke_pattern.sub(_replace, text)

        # If there is free-form text before the first <invoke>, promote it
        # to a Thought: line so the parser can still pick up the step.
        first_invoke = new_text.find("Action:")
        if first_invoke > 0:
            prefix = new_text[:first_invoke].strip()
            if prefix and not prefix.lower().startswith("thought:"):
                new_text = f"Thought: {prefix}\n" + new_text[first_invoke:]
        return new_text

    @staticmethod
    def _convert_tool_call_block(text: str) -> str:
        """Rewrite ``[TOOL_CALL]{tool => "...", args => {...}}[/TOOL_CALL]`` blocks.

        This is another MiniMax output variant. The block uses square-bracket
        tags and arrow-style key-value pairs instead of JSON, e.g.::

            [TOOL_CALL]
            {tool => "sql_query", args => { --sql "SELECT * FROM t" }}
            [/TOOL_CALL]

        We extract the tool name and the ``--sql`` argument (the only
        argument ``sql_query`` accepts) and emit standard ReAct prefixes.
        Free-form text before the block is promoted to ``Thought:``.
        """
        tool_call_pattern = re.compile(
            r"\[TOOL_CALL\]\s*(?P<body>.*?)\s*\[/TOOL_CALL\]",
            re.DOTALL,
        )

        def _replace(match: re.Match) -> str:
            body = (match.group("body") or "").strip()
            # Extract tool name: tool => "..."
            tool_match = re.search(r"tool\s*=>\s*\"([^\"]+)\"", body)
            tool_name = tool_match.group(1) if tool_match else ""
            # Extract sql argument: --sql "..." (supports multi-line)
            sql_match = re.search(r"--sql\s+\"((?:[^\"\\]|\\.)*)\"", body)
            if not sql_match:
                # Fallback: args => { --key "val" } pattern
                sql_match = re.search(r"args\s*=>\s*\{[^}]*\"([^\"]+)\"[^}]*\}", body)
            sql_value = sql_match.group(1) if sql_match else ""
            action_input = json.dumps({"sql": sql_value}, ensure_ascii=False) if sql_value else ""
            out = [f"Action: {tool_name}"] if tool_name else []
            if action_input:
                out.append(f"Action Input: {action_input}")
            return "\n".join(out)

        new_text = tool_call_pattern.sub(_replace, text)

        # Promote free-form text before the first [TOOL_CALL] to Thought:
        first_action = new_text.find("Action:")
        if first_action > 0:
            prefix = new_text[:first_action].strip()
            if prefix and not prefix.lower().startswith("thought:"):
                new_text = f"Thought: {prefix}\n" + new_text[first_action:]
        return new_text

    def _strip_markdown_code_fence(self, text: str) -> str:
        """Remove a markdown fence that wraps the whole ReAct response."""
        stripped = text.strip()
        match = re.fullmatch(r"```[a-zA-Z0-9_-]*\s*\n(.*?)\n```", stripped, re.DOTALL)
        if match:
            return match.group(1).strip()
        return text

    def _normalize_react_text(self, text: str) -> str:
        """Normalize common wrappers before ReAct parsing."""
        if not text:
            return text

        text = self._strip_think_tags(text)
        text = self._strip_vis_thinking_blocks(text)
        text = self._strip_minimax_tool_call(text)
        text = self._strip_markdown_code_fence(text)
        stripped = text.lstrip()
        fence = "`" * 6
        opening = f"{fence}{VisThinking.vis_tag()}"
        if not stripped.startswith(opening):
            return text

        lines = stripped.splitlines()
        if len(lines) < 3 or lines[0].strip() != opening:
            return text

        closing_index = None
        for idx in range(1, len(lines)):
            if lines[idx].strip() == fence:
                trailing_content = "\n".join(lines[idx + 1 :]).lstrip()
                if not trailing_content or trailing_content.startswith(
                    self.thought_prefix
                ):
                    closing_index = idx
                    break

        if closing_index is None:
            return text

        return "\n".join(lines[closing_index + 1 :]).lstrip()

    def parse(self, text: str) -> List[ReActStep]:
        """
        Parse the ReAct format output text into structured steps.

        Args:
            text: The text to parse, containing ReAct formatted content.

        Returns:
            List of ReActStep dataclasses, each containing thought, action,
                action_input, and observation.
        """
        # Split the text into steps based on thought prefix
        steps = []

        # Remove any leading/trailing whitespace
        text = self._normalize_react_text(text).strip()

        # Find all line-start instances of the thought prefix outside code fences.
        thought_matches = self._find_prefix_matches(text, self.thought_prefix_escaped)

        if not thought_matches:
            return []

        # Process each thought section
        for i, match in enumerate(thought_matches):
            start_pos = match.start()

            # Determine end position (either next thought or end of text)
            if i < len(thought_matches) - 1:
                end_pos = thought_matches[i + 1].start()
            else:
                end_pos = len(text)

            # Extract the current step's text
            step_text = text[start_pos:end_pos].strip()

            # Parse the step
            step_data = self._parse_step(step_text)
            if step_data:
                steps.append(step_data)

        return steps

    def parse_current_step(self, text: str) -> List[ReActStep]:
        """Parse the single step that should be executed in the current round.

        Some reasoning models incorrectly emit a whole ReAct trajectory in one
        response. DB-GPT executes one action per round, so callers that are about
        to run tools should use only the first actionable step while preserving
        ``parse()`` for history and diagnostics.
        """
        steps = self.parse(text)
        if len(steps) <= 1:
            return steps
        for step in steps:
            if step.action:
                return [step]
        return [steps[0]]

    def _parse_step(self, step_text: str) -> Optional[ReActStep]:
        """
        Parse a single step of the ReAct format.

        Args:
            step_text: Text containing a single thought-action-input-observation
                sequence.

        Returns:
            ReActStep dataclass with thought, action, action_input, and observation,
                or None if parsing fails.
        """
        # Initialize the result
        thought = None
        phase = None
        action_intention = None
        action_reason = None
        action = None
        action_input = None
        observation = None
        is_terminal = False
        match_text = self._mask_prefixes_in_fences(step_text)

        # Extract thought
        thought_line = self._prefix_line_pattern(self.thought_prefix_escaped)
        phase_line = self._prefix_line_pattern(self.phase_prefix_escaped)
        action_intention_line = self._prefix_line_pattern(
            self.action_intention_prefix_escaped
        )
        action_reason_line = self._prefix_line_pattern(
            self.action_reason_prefix_escaped
        )
        action_line = self._prefix_line_pattern(self.action_prefix_escaped)
        action_input_line = self._prefix_line_pattern(self.action_input_prefix_escaped)
        observation_line = self._prefix_line_pattern(self.observation_prefix_escaped)

        thought_match = re.search(
            rf"{thought_line}(.*?)(?={phase_line}|{action_intention_line}|"
            rf"{action_reason_line}|{action_line}|{observation_line}|\Z)",
            match_text,
            re.DOTALL | re.MULTILINE,
        )
        if thought_match:
            thought = step_text[thought_match.start(1) : thought_match.end(1)].strip()

        # Extract phase (optional, between thought and action)
        phase_match = re.search(
            rf"{phase_line}(.*?)(?={action_intention_line}|{action_reason_line}|"
            rf"{action_line}|{action_input_line}|{observation_line}|\Z)",
            match_text,
            re.DOTALL | re.MULTILINE,
        )
        if phase_match:
            phase = step_text[phase_match.start(1) : phase_match.end(1)].strip() or None

        # Extract action intention (optional, short user-facing intent)
        action_intention_match = re.search(
            rf"{action_intention_line}(.*?)(?={action_reason_line}|{action_line}|"
            rf"{action_input_line}|{observation_line}|\Z)",
            match_text,
            re.DOTALL | re.MULTILINE,
        )
        if action_intention_match:
            action_intention = (
                step_text[
                    action_intention_match.start(1) : action_intention_match.end(1)
                ].strip()
                or None
            )

        # Extract action reason (optional, short user-facing reason)
        action_reason_match = re.search(
            rf"{action_reason_line}(.*?)(?={action_intention_line}|{action_line}|"
            rf"{action_input_line}|{observation_line}|\Z)",
            match_text,
            re.DOTALL | re.MULTILINE,
        )
        if action_reason_match:
            action_reason = (
                step_text[
                    action_reason_match.start(1) : action_reason_match.end(1)
                ].strip()
                or None
            )

        # Extract action
        action_match = re.search(
            rf"{action_line}(.*?)(?={action_input_line}|{observation_line}|\Z)",
            match_text,
            re.DOTALL | re.MULTILINE,
        )
        if action_match:
            action = step_text[action_match.start(1) : action_match.end(1)].strip()

            # Check if this is a terminate action
            is_terminal = action.lower() == self.terminate_action.lower()

        # Extract action input
        action_input_match = re.search(
            rf"{action_input_line}(.*?)(?={observation_line}|{thought_line}|\Z)",
            match_text,
            re.DOTALL | re.MULTILINE,
        )
        if action_input_match:
            action_input_text = step_text[
                action_input_match.start(1) : action_input_match.end(1)
            ].strip()

            # Try to parse action input as JSON if it looks like JSON
            if (
                action_input_text.startswith("{") and action_input_text.endswith("}")
            ) or (
                action_input_text.startswith("[") and action_input_text.endswith("]")
            ):
                try:
                    action_input = json.loads(action_input_text)
                except json.JSONDecodeError:
                    action_input = action_input_text
            else:
                action_input = action_input_text

        # Extract observation
        observation_match = re.search(
            rf"{observation_line}(.*?)(?={thought_line}|\Z)",
            match_text,
            re.DOTALL | re.MULTILINE,
        )
        if observation_match:
            observation_text = step_text[
                observation_match.start(1) : observation_match.end(1)
            ].strip()

            # Try to parse observation as JSON if it looks like JSON
            if (
                observation_text.startswith("{") and observation_text.endswith("}")
            ) or (observation_text.startswith("[") and observation_text.endswith("]")):
                try:
                    observation = json.loads(observation_text)
                except json.JSONDecodeError:
                    observation = observation_text
            else:
                observation = observation_text

        # Only return if we have at least thought or action
        if thought or action:
            return ReActStep(
                thought=thought,
                phase=phase,
                action_intention=action_intention,
                action_reason=action_reason,
                action=action,
                action_input=action_input,
                observation=observation,
                is_terminal=is_terminal,
            )
        return None

    def get_final_output(self, steps: List[ReActStep]) -> Optional[str]:
        """
        Get the final output from a terminate action if it exists.

        Args:
            steps: List of parsed steps.

        Returns:
            The final output string or None if no terminate action is found.
        """
        for step in reversed(steps):  # Look from the end
            if step.is_terminal and step.action == self.terminate_action:
                if (
                    isinstance(step.action_input, dict)
                    and "result" in step.action_input
                ):
                    return step.action_input["result"]
                if (
                    isinstance(step.action_input, dict)
                    and "output" in step.action_input
                ):
                    return step.action_input["output"]
        return None
