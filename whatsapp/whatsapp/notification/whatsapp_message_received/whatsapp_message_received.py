import frappe
from frappe import _

from whatsapp.whatsapp.api.utils import infer_content_type

MEDIA_LABELS = {
	"image": "Photo",
	"video": "Video",
	"audio": "Audio message",
	"document": "Document",
}

PREVIEW_LIMIT = 140


def get_context(context):
	return {"message_preview": _message_preview(context["doc"])}


def _message_preview(doc) -> str:
	"""One-line body for the in-app notification: the text, or what kind of media arrived."""
	if doc.message:
		text = frappe.utils.strip_html(doc.message).strip()
		if len(text) <= PREVIEW_LIMIT:
			return text
		return text[:PREVIEW_LIMIT].rstrip() + "…"

	# infer_content_type returns "text" when there is no MIME type, i.e. no media either
	label = MEDIA_LABELS.get(infer_content_type(doc.mime_type))
	return _(label) if label else ""
