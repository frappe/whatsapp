# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

from typing import NamedTuple

import frappe

SEPARATOR = ":"


class FlowToken(NamedTuple):
	"""The Flow token a message sends. A template button sends the message's token with the button's index
	and Flow, because Meta's response names neither, and the template's buttons can change after the send."""

	base: str
	button_index: int | None = None
	flow: str | None = None

	@classmethod
	def new(cls) -> "FlowToken":
		return cls(frappe.generate_hash(length=24))

	@classmethod
	def parse(cls, sent: str) -> "FlowToken":
		parts = sent.split(SEPARATOR)
		if len(parts) == 3 and all(parts) and parts[1].isdigit():
			return cls(parts[0], int(parts[1]), parts[2])
		return cls(sent)

	def for_button(self, index: int, flow: str) -> "FlowToken":
		return FlowToken(self.base, index, flow)

	def __str__(self) -> str:
		if self.flow is None:
			return self.base
		return SEPARATOR.join((self.base, str(self.button_index), self.flow))
