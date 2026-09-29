import frappe
from frappe.utils.password import Auth

from whatsapp.patches.v1_0.rename_doctypes_to_wa_prefix import DOCTYPE_RENAMES


def execute():
	"""Point saved passwords at the renamed DocTypes.

	Renaming a DocType leaves its rows in `__Auth` under the old name, so after the WA
	rename `get_password("access_token")` on a WA Account found nothing.
	"""
	for old, new in DOCTYPE_RENAMES:
		# Another app (frappe_whatsapp) still has a DocType by the old name; those are its passwords.
		if frappe.db.exists("DocType", old):
			continue

		rows = frappe.qb.from_(Auth).select(Auth.name, Auth.fieldname).where(Auth.doctype == old).run()
		for name, fieldname in rows:
			_move_password(old, new, name, fieldname)


def _move_password(old: str, new: str, name: str, fieldname: str) -> None:
	stored_under_old = _matches(old, name, fieldname)
	# A password saved again after the rename is the newer one.
	if frappe.qb.from_(Auth).select(Auth.name).where(_matches(new, name, fieldname)).run():
		frappe.qb.from_(Auth).delete().where(stored_under_old).run()
	else:
		frappe.qb.update(Auth).set(Auth.doctype, new).where(stored_under_old).run()


def _matches(doctype: str, name: str, fieldname: str):
	return (Auth.doctype == doctype) & (Auth.name == name) & (Auth.fieldname == fieldname)
