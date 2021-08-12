from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def setup():
	setup_custom_fields()

def on_company_update(doc, method=""):
	if doc.get('country', '').lower() == 'india':
		setup_custom_fields()

def setup_custom_fields():
	custom_fields = {
		'Sales Invoice': [
			dict(
				fieldname='einvoice_section', label='E-Invoice Details',
				fieldtype='Section Break', insert_after='amended_from',
				print_hide=1, depends_on='e_invoice', collapsible=1,
				collapsible_depends_on='e_invoice', hidden=0
			),
		
			dict(
				fieldname='e_invoice', label='E-Invoice', fieldtype='Link',
				read_only=1, insert_after='einvoice_section',
				options='E Invoice', no_copy=1, print_hide=1,
				depends_on='e_invoice', hidden=0
			),
			
			dict(
				fieldname='irn', label='IRN', fieldtype='Data', read_only=1,
				insert_after='e_invoice', no_copy=1, print_hide=1,
				depends_on='eval: doc.einvoice_status != "IRN Cancelled"',
				fetch_from='e_invoice.irn', hidden=0, translatable=0
			),
			
			dict(
				fieldname='ack_no', label='Ack. No.', fieldtype='Data',
				read_only=1, insert_after='irn', no_copy=1, hidden=0,
				depends_on='eval: doc.einvoice_status != "IRN Cancelled"',
				fetch_from='e_invoice.ack_no', print_hide=1, translatable=0
			),

			dict(
				fieldname='col_break_1', label='', fieldtype='Column Break',
				insert_after='ack_no', print_hide=1, read_only=1
			),

			dict(
				fieldname='einvoice_status', label='E-Invoice Status',
				fieldtype='Data', read_only=1, no_copy=1, hidden=0,
				insert_after='col_break_1', print_hide=1, depends_on='e_invoice',
				fetch_from='e_invoice.status', options='', translatable=0
			),

			dict(
				fieldname='ack_date', label='Ack. Date', fieldtype='Data',
				read_only=1, insert_after='einvoice_status', hidden=0,
				depends_on='eval: doc.einvoice_status != "IRN Cancelled"',
				fetch_from='e_invoice.ack_date', no_copy=1, print_hide=1, translatable=0
			),

			dict(
				fieldname='irn_cancel_date', label='IRN Cancelled On',
				fieldtype='Data', read_only=1, insert_after='einvoice_status', hidden=0,
				depends_on='eval: doc.einvoice_status == "IRN Cancelled"',
				fetch_from='e_invoice.irn_cancel_date', no_copy=1, print_hide=1, translatable=0
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
			)
		]
	}

	print('Creating Custom Fields for E-Invoicing...')
	create_custom_fields(custom_fields, update=True)