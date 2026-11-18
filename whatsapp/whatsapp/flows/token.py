# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

from typing import NamedTuple

import frappe

SEPARATOR = ":"


class FlowToken(NamedTuple):
	"""The Flow token a message sends. A template button sends the message's token with the button's index,
	because Meta's response names neither the button nor the Flow."""

	base: str
	button_index: int | None = None

	@classmethod
	def new(cls) -> "FlowToken":
		return cls(frappe.generate_hash(length=24))

	@classmethod
	def parse(cls, sent: str) -> "FlowToken":
		base, separator, index = sent.rpartition(SEPARATOR)
		if separator and base and index.isdigit():
			return cls(base, int(index))
		return cls(sent)

	def for_button(self, index: int) -> "FlowToken":
		return FlowToken(self.base, index)

	def __str__(self) -> str:
		return self.base if self.button_index is None else f"{self.base}{SEPARATOR}{self.button_index}"
