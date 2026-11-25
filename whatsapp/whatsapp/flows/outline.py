# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import json
import re

REFERENCE = re.compile(r"^\$\{(?:screen\.(\w+)\.)?(form|data)\.(\w+)\}$")
UNTRACED = {"label": "", "component": "", "type": "unknown"}
ANSWER_TYPES = {
	"TextArea": "string",
	"RadioButtonsGroup": "string",
	"Dropdown": "string",
	"DatePicker": "date",
	"CheckboxGroup": "array",
	"ChipsSelector": "array",
	"OptIn": "boolean",
	"PhotoPicker": "media",
	"DocumentPicker": "media",
}


class FlowOutline:
	"""What the app reads out of a Flow's JSON. The only place Flow JSON is parsed."""

	def __init__(
		self,
		screens: list,
		entry_screens: dict,
		answers: list,
		sensitive: list,
		screen_titles: dict | None = None,
	):
		self.screens = screens
		# Absent from outlines stored before titles were read.
		self.screen_titles = screen_titles or {}
		self.entry_screens = entry_screens
		self.answers = answers
		self.sensitive = sensitive

	@classmethod
	def from_flow_json(cls, flow_json: str | dict) -> "FlowOutline":
		"""Raise ValueError when the JSON is invalid or has no screens."""
		flow = FlowGraph(_load(flow_json))
		answers = flow.answers()
		return cls(
			screens=flow.screen_ids,
			screen_titles={
				screen_id: title
				for screen_id, screen in flow.screens.items()
				if isinstance(title := screen.get("title"), str) and title
			},
			entry_screens={screen_id: flow.declared_data(screen_id) for screen_id in flow.entry_screen_ids()},
			answers=[answer for answer, _ in answers],
			sensitive=[answer["key"] for answer, is_sensitive in answers if is_sensitive],
		)

	@classmethod
	def from_dict(cls, data: dict) -> "FlowOutline":
		return cls(**data)

	def as_dict(self) -> dict:
		return {
			"screens": self.screens,
			"screen_titles": self.screen_titles,
			"entry_screens": self.entry_screens,
			"answers": self.answers,
			"sensitive": self.sensitive,
		}


class FlowGraph:
	"""Screens of a Flow indexed by id, with their input components and actions."""

	def __init__(self, flow: dict):
		self.routing_model = flow.get("routing_model") or {}
		self.screens = {
			screen["id"]: screen
			for screen in flow["screens"]
			if isinstance(screen, dict) and screen.get("id")
		}
		self.screen_ids = list(self.screens)
		self.actions = {screen_id: [] for screen_id in self.screen_ids}
		self.inputs = {screen_id: {} for screen_id in self.screen_ids}
		for screen_id, screen in self.screens.items():
			self._collect(screen_id, screen.get("layout"))

	def entry_screen_ids(self) -> list[str]:
		targets = {target for targets in self.routing_model.values() for target in targets}
		targets.update(target for _, target, _ in self.navigations())
		return [screen_id for screen_id in self.screen_ids if screen_id not in targets]

	def declared_data(self, screen_id: str) -> dict:
		data = self.screens[screen_id].get("data") or {}
		return {key: _declared_type(declaration) for key, declaration in data.items()}

	def answers(self) -> list[tuple[dict, bool]]:
		"""Return (answer, is sensitive) for each complete payload key, in first-seen order.

		The first traced answer for a key wins; an untraced one only holds the place until then.
		"""
		answers = {}
		for screen_id, payload in self._completions():
			for key, value in flatten(payload):
				if key == "flow_token" or _is_traced(answers.get(key)):
					continue
				answers[key] = self._answer(screen_id, key, value)
		return list(answers.values())

	def navigations(self):
		"""Yield (source screen, target screen, payload) for every navigate action."""
		for screen_id, actions in self.actions.items():
			for action in actions:
				if action.get("name") == "navigate":
					yield screen_id, (action.get("next") or {}).get("name"), action.get("payload") or {}

	def _completions(self):
		for screen_id, actions in self.actions.items():
			for action in actions:
				if action.get("name") == "complete":
					yield screen_id, action.get("payload") or {}

	def _answer(self, screen_id: str, key: str, value) -> tuple[dict, bool]:
		found = self._trace(screen_id, value, set())
		if not found:
			return {"key": key, **UNTRACED}, False
		input_screen_id, component = found
		answer = {
			"key": key,
			"label": component.get("label") or component.get("text") or "",
			"component": component.get("type", ""),
			"type": _answer_type(component),
		}
		return answer, self._is_sensitive(input_screen_id, component)

	def _trace(self, screen_id: str, value, seen: set) -> tuple[str, dict] | None:
		"""Find the input component behind a payload value, following ${data.x} back through navigates."""
		match = REFERENCE.match(value) if isinstance(value, str) else None
		if not match:
			return None
		screen_id = match.group(1) or screen_id
		source, name = match.group(2), match.group(3)
		if source == "form":
			component = self.inputs.get(screen_id, {}).get(name)
			return (screen_id, component) if component else None
		if (screen_id, name) in seen:
			return None
		seen.add((screen_id, name))
		for source_screen_id, target, payload in self.navigations():
			if target == screen_id and name in payload:
				if found := self._trace(source_screen_id, payload[name], seen):
					return found
		return None

	def _is_sensitive(self, screen_id: str, component: dict) -> bool:
		if component.get("type") == "TextInput" and component.get("input-type") in ("password", "passcode"):
			return True
		return component.get("name") in (self.screens[screen_id].get("sensitive") or [])

	def _collect(self, screen_id: str, node):
		if isinstance(node, list):
			for item in node:
				self._collect(screen_id, item)
			return
		if not isinstance(node, dict):
			return
		if node.get("type") and node.get("name"):
			self.inputs[screen_id][node["name"]] = node
		for key, value in node.items():
			if key.endswith("-action") and isinstance(value, dict):
				self.actions[screen_id].append(value)
			else:
				self._collect(screen_id, value)


def _load(flow_json: str | dict) -> dict:
	if isinstance(flow_json, str):
		try:
			flow_json = json.loads(flow_json)
		except json.JSONDecodeError as e:
			raise ValueError(f"Flow JSON is not valid JSON: {e}")
	if not isinstance(flow_json, dict) or not isinstance(flow_json.get("screens"), list):
		raise ValueError("Flow JSON has no screens")
	return flow_json


def _is_traced(found: tuple[dict, bool] | None) -> bool:
	return bool(found) and bool(found[0]["component"])


def _declared_type(declaration) -> str:
	return declaration.get("type", "unknown") if isinstance(declaration, dict) else "unknown"


def flatten(payload: dict, prefix: str = ""):
	for key, value in payload.items():
		if isinstance(value, dict):
			yield from flatten(value, f"{prefix}{key}.")
		else:
			yield f"{prefix}{key}", value


def _answer_type(component: dict) -> str:
	component_type = component.get("type")
	if component_type == "TextInput":
		return "number" if component.get("input-type") == "number" else "string"
	if component_type == "CalendarPicker":
		return "object" if component.get("mode") == "range" else "date"
	return ANSWER_TYPES.get(component_type, "unknown")
