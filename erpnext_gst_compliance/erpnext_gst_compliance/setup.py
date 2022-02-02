import frappe
from frappe.utils import cint, add_to_date
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def setup():
	copy_adequare_credentials()
	enable_report_and_print_format()
	setup_custom_fields()
	handle_existing_e_invoices()

def on_company_update(doc, method=""):
	if frappe.db.count('Company', {'country': 'India'}) <=1:
		setup_custom_fields()

def setup_custom_fields():
	custom_fields = {
		'Sales Invoice': [
			dict(
				fieldname='einvoice_section', label='E-Invoice Details',
				fieldtype='Section Break', insert_after='amended_from',
				print_hide=1, depends_on='eval: doc.e_invoice || doc.irn',
				collapsible_depends_on='eval: doc.e_invoice || doc.irn',
				collapsible=1, hidden=0
			),

			dict(
				fieldname='irn', label='IRN', fieldtype='Data', read_only=1,
				depends_on='irn', insert_after='einvoice_section', no_copy=1,
				print_hide=1, fetch_from='e_invoice.irn', hidden=0, translatable=0
			),

			dict(
				fieldname='irn_cancel_date', label='IRN Cancelled On',
				fieldtype='Data', read_only=1, insert_after='irn', hidden=0,
				depends_on='eval: doc.einvoice_status == "IRN Cancelled"',
				fetch_from='e_invoice.irn_cancel_date', no_copy=1, print_hide=1, translatable=0
			),
			
			dict(
				fieldname='ack_no', label='Ack. No.', fieldtype='Data',
				read_only=1, insert_after='irn', no_copy=1, hidden=0,
				depends_on='eval: doc.einvoice_status != "IRN Cancelled"',
				fetch_from='e_invoice.ack_no', print_hide=1, translatable=0
			),

			dict(
				fieldname='ack_date', label='Ack. Date', fieldtype='Data',
				read_only=1, insert_after='ack_no', hidden=0,
				depends_on='eval: doc.einvoice_status != "IRN Cancelled"',
				fetch_from='e_invoice.ack_date', no_copy=1, print_hide=1, translatable=0
			),

			dict(
				fieldname='col_break_1', label='', fieldtype='Column Break',
				insert_after='ack_date', print_hide=1, read_only=1
			),

			dict(
				fieldname='e_invoice', label='E-Invoice', fieldtype='Link',
				read_only=1, insert_after='col_break_1',
				options='E Invoice', no_copy=1, print_hide=1,
				depends_on='eval: doc.e_invoice || doc.irn', hidden=0
			),

			dict(
				fieldname='einvoice_status', label='E-Invoice Status',
				fieldtype='Data', read_only=1, no_copy=1, hidden=0,
				insert_after='e_invoice', print_hide=1, options='',
				depends_on='eval: doc.e_invoice || doc.irn',
				fetch_from='e_invoice.status', translatable=0
			),

			dict(
				fieldname='qrcode_image', label='QRCode', fieldtype='Attach Image',
				hidden=1, insert_after='ack_date', fetch_from='e_invoice.qrcode_path',
				no_copy=1, print_hide=1, read_only=1
			),

			dict(
				fieldname='ewaybill', label='E-Way Bill No.', fieldtype='Data',
				allow_on_submit=1, insert_after='einvoice_status', fetch_from='e_invoice.ewaybill', translatable=0,
				depends_on='eval:((doc.docstatus === 1 || doc.ewaybill) && doc.eway_bill_cancelled === 0)'
			),

			dict(
				fieldname='eway_bill_validity', label='E-Way Bill Validity',
				fieldtype='Data', no_copy=1, print_hide=1, depends_on='ewaybill',
				read_only=1, allow_on_submit=1, insert_after='ewaybill'
			)
		]
	}

	print('Creating Custom Fields for E-Invoicing...')
	create_custom_fields(custom_fields, update=True)

def copy_adequare_credentials():
	if frappe.db.exists('E Invoice Settings'):
		credentials = frappe.db.sql('select * from `tabE Invoice User`', as_dict=1)
		if not credentials:
			return

		print('Copying Credentials for E-Invoicing...')
		from frappe.utils.password import get_decrypted_password
		try:
			adequare_settings = frappe.get_single('Adequare Settings')
			adequare_settings.credentials = []
			for credential in credentials:
				adequare_settings.append('credentials', {
					'company': credential.company,
					'gstin': credential.gstin,
					'username': credential.username,
					'password': get_decrypted_password('E Invoice User', credential.name)
				})
			adequare_settings.enabled = 1
			adequare_settings.flags.ignore_validate = True
			adequare_settings.save()
			frappe.db.commit()

			e_invoicing_settings = frappe.get_single('E Invoicing Settings')
			e_invoicing_settings.service_provider = 'Adequare Settings'
			e_invoicing_settings.save()
		except:
			frappe.log_error(title="Failed to copy Adeqaure Credentials")

def enable_report_and_print_format():
	frappe.db.set_value("Print Format", "GST E-Invoice", "disabled", 0)
	if not frappe.db.get_value('Custom Role', dict(report='E-Invoice Summary')):
		frappe.get_doc(dict(
			doctype='Custom Role',
			report='E-Invoice Summary',
			roles= [
				dict(role='Accounts User'),
				dict(role='Accounts Manager')
			]
		)).insert()

def handle_existing_e_invoices():
	if frappe.get_all('Sales Invoice', {'irn': ['is', 'set']}):
		try:
			update_sales_invoices()
			create_einvoices()
		except Exception:
			frappe.log_error(title="Backporting Sales Invoices Failed")

def update_sales_invoices():
	einvoices = frappe.db.sql("""
		select
			name, irn, irn_cancelled, ewaybill, eway_bill_cancelled, einvoice_status
		from
			`tabSales Invoice`
		where
			ifnull(irn, '') != ''
	""", as_dict=1)

	if not einvoices:
		return

	print('Updating Sales Invoices...')
	for invoice in einvoices:
		einvoice_status = 'IRN Generated'
		if cint(invoice.irn_cancelled):
			einvoice_status = 'IRN Cancelled'
		if invoice.ewaybill:
			einvoice_status = 'E-Way Bill Generated'
		if cint(invoice.eway_bill_cancelled):
			einvoice_status = 'E-Way Bill Cancelled'

		frappe.db.set_value('Sales Invoice', invoice.name, 'einvoice_status', einvoice_status, update_modified=False)
	frappe.db.commit()

def create_einvoices():
	draft_einvoices = frappe.db.sql("""
		select
			name, irn, ack_no, ack_date, irn_cancelled, irn_cancel_date,
			ewaybill, eway_bill_validity, einvoice_status, qrcode_image, docstatus
		from
			`tabSales Invoice`
		where
			ifnull(irn, '') != '' AND docstatus = 0
	""", as_dict=1)

	draft_einvoices_names = [d.name for d in draft_einvoices]

	# sales invoices with irns created within 24 hours
	recent_einvoices = frappe.db.sql("""
		select
			name, irn, ack_no, ack_date, irn_cancelled, irn_cancel_date,
			ewaybill, eway_bill_validity, einvoice_status, qrcode_image, docstatus
		from
			`tabSales Invoice`
		where
			ifnull(irn, '') != '' AND docstatus != 2 AND
			timestamp(ack_date) >= %s and name not in %s
	""", (add_to_date(None, hours=-24), draft_einvoices_names), as_dict=1)

	if not draft_einvoices + recent_einvoices:
		return

	print('Creating E-Invoices...')
	for invoice in draft_einvoices + recent_einvoices:
		try:
			einvoice = frappe.new_doc('E Invoice')

			einvoice.invoice = invoice.name
			einvoice.irn = invoice.irn
			einvoice.ack_no = invoice.ack_no
			einvoice.ack_date = invoice.ack_date
			einvoice.ewaybill = invoice.ewaybill
			einvoice.status = invoice.einvoice_status
			einvoice.qrcode_path = invoice.qrcode_image
			einvoice.irn_cancelled = invoice.irn_cancelled
			einvoice.irn_cancelled_on = invoice.irn_cancel_date
			einvoice.eway_bill_validity = invoice.eway_bill_validity

			einvoice.sync_with_sales_invoice()

			einvoice.flags.ignore_permissions = 1
			einvoice.flags.ignore_validate = 1
			einvoice.save()
			if invoice.docstatus != 0:
				einvoice.submit()

		except Exception:
			frappe.log_error(title="E-Invoice Creation Failed")

def before_test():
	from frappe.test_runner import make_test_records_for_doctype
	for doctype in ['Company', 'Customer']:
		frappe.local.test_objects[doctype] = []
		make_test_records_for_doctype(doctype, force=1)