# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from lxml import etree

from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestAccountEdiUblCii(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref)

        cls.uom_units = cls.env.ref("uom.product_uom_unit")
        cls.uom_dozens = cls.env.ref("uom.product_uom_dozen")

        cls.displace_prdct = cls.env["product.product"].create(
            {
                "name": "Displacement",
                "uom_id": cls.uom_units.id,
                "standard_price": 90.0,
            }
        )

        cls.place_prdct = cls.env["product.product"].create(
            {
                "name": "Placement",
                "uom_id": cls.uom_units.id,
                "standard_price": 80.0,
            }
        )

    def test_import_product(self):
        line_vals = [
            {"product_id": self.place_prdct.id, "product_uom_id": self.uom_units.id},
            {"product_id": self.displace_prdct.id, "product_uom_id": self.uom_units.id},
            {"product_id": self.displace_prdct.id, "product_uom_id": self.uom_units.id},
            {
                "product_id": self.displace_prdct.id,
                "product_uom_id": self.uom_dozens.id,
            },
        ]
        invoice = self.env["account.move"].create(
            {
                "partner_id": self.company_data_2["company"].partner_id.id,
                "move_type": "out_invoice",
                "invoice_line_ids": [(0, 0, vals) for vals in line_vals],
            }
        )
        invoice.action_post()

        facturx_attachment = invoice.edi_document_ids.attachment_id
        xml_tree = etree.fromstring(facturx_attachment.raw)

        # Testing the case where a product on the invoice has a UoM with a different category than the one in the DB
        wrong_uom_line = xml_tree.findall(
            "./{*}SupplyChainTradeTransaction/{*}IncludedSupplyChainTradeLineItem"
        )[1]
        wrong_uom_line.find("./{*}SpecifiedLineTradeDelivery/{*}BilledQuantity").attrib[
            "unitCode"
        ] = "HUR"

        new_invoice = self.env.ref(
            "account_edi_facturx.edi_facturx_1_0_05"
        )._create_invoice_from_xml_tree(
            facturx_attachment.name,
            xml_tree,
            invoice.journal_id,
        )

        self.assertRecordValues(new_invoice.invoice_line_ids, line_vals)

    def test_import_tax_prediction(self):
        """We are going to create 2 tax and import the e-invoice twice.

        On the first attempt, as there isn't any data to leverage, the classic 'search' will be called and we expect
        the first tax created to be the selected one as the retrieval order is `sequence, id`.

        We will set the second tax on the bill and post it which make it the most probable one.

        On the second attempt, we expect that second tax to be retrieved.
        """
        self.env.ref(
            "base.EUR"
        ).active = True  # EUR might not be active and is used in the xml testing file
        if not hasattr(self.env["account.move.line"], "_predict_specific_tax"):
            self.skipTest(
                "The predictive bill module isn't install and thus prediction with edi can't be tested."
            )
        # create 2 new taxes for the test seperatly to ensure the first gets the smaller id
        new_tax_1 = self.env["account.tax"].create(
            {
                "name": "tax with lower id could be retrieved first",
                "amount_type": "percent",
                "type_tax_use": "purchase",
                "amount": 16.0,
            }
        )
        new_tax_2 = self.env["account.tax"].create(
            {
                "name": "tax with higher id could be retrieved second",
                "amount_type": "percent",
                "type_tax_use": "purchase",
                "amount": 16.0,
            }
        )

        file_path = "bis3_bill_example.xml"
        file_path = f"{self.test_module}/tests/test_files/{file_path}"
        with file_open(file_path, "rb") as file:
            xml_attachment = self.env["ir.attachment"].create(
                {
                    "mimetype": "application/xml",
                    "name": "test_invoice.xml",
                    "raw": file.read(),
                }
            )

        # Import the document for the first time
        bill = self.import_attachment(
            xml_attachment, self.company_data["default_journal_purchase"]
        )

        # Ensure the first tax is retrieved as there isn't any prediction that could be leverage
        self.assertEqual(bill.invoice_line_ids.tax_ids, new_tax_1)

        # Set the second tax on the line to make it the most probable one
        bill.invoice_line_ids.tax_ids = new_tax_2
        bill.action_post()

        # Import the bill again and ensure the prediction did his work
        bill = self.import_attachment(
            xml_attachment, self.company_data["default_journal_purchase"]
        )
        self.assertEqual(bill.invoice_line_ids.tax_ids, new_tax_2)

    def test_peppol_eas_endpoint_compute(self):
        partner = self.partner_a
        partner.vat = "DE123456788"

        self.assertRecordValues(
            partner,
            [
                {
                    "peppol_eas": "9930",
                    "peppol_endpoint": "DE123456788",
                }
            ],
        )

        partner.vat = "FR23334175221"

        self.assertRecordValues(
            partner,
            [
                {
                    "peppol_eas": "9957",
                    "peppol_endpoint": "FR23334175221",
                }
            ],
        )

        partner.vat = "23334175221"

        self.assertRecordValues(
            partner,
            [
                {
                    "peppol_eas": "9957",
                    "peppol_endpoint": "FR23334175221",
                }
            ],
        )

        partner.write(
            {
                "vat": "BE0477472701",
                "company_registry": "0477472701",
            }
        )

        self.assertRecordValues(
            partner,
            [
                {
                    "peppol_eas": "0208",
                    "peppol_endpoint": "0477472701",
                }
            ],
        )

    def test_import_partner_peppol_fields(self):
        """Check that the peppol fields are used to retrieve the partner when importing a Bis 3 xml."""
        partner = self.env["res.partner"].create(
            {
                "name": "My Belgian Partner",
                "vat": "BE0477472701",
                "peppol_eas": "0208",
                "peppol_endpoint": "0477472701",
                "email": "mypartner@email.com",
            }
        )
        invoice = self.env["account.move"].create(
            {
                "partner_id": partner.id,
                "move_type": "out_invoice",
                "invoice_line_ids": [Command.create({"product_id": self.product_a.id})],
            }
        )
        invoice.action_post()
        xml_attachment = self.env["ir.attachment"].create(
            {
                "raw": self.env["account.edi.xml.ubl_bis3"]._export_invoice(invoice)[0],
                "name": "test_invoice.xml",
            }
        )

        # There is a duplicated partner (with the same name and email)
        self.env["res.partner"].create(
            {
                "name": "My Belgian Partner",
                "email": "mypartner@email.com",
            }
        )
        # Change the fields of the partner, keep the peppol fields
        partner.update(
            {
                "name": "Turlututu",
                "email": False,
                "vat": False,
            }
        )
        # The partner should be retrieved based on the peppol fields
        imported_invoice = self.import_attachment(
            xml_attachment, self.company_data["default_journal_sale"]
        )
        self.assertEqual(imported_invoice.partner_id, partner)

    def test_export_pdf_contains_facturx(self):
        """Check that we generate a Factur-x xml when we render the invoice action report."""
        invoice = self.env["account.move"].create(
            {
                "partner_id": self.partner_a.id,
                "move_type": "out_invoice",
                "invoice_line_ids": [Command.create({"product_id": self.product_a.id})],
            }
        )
        invoice.action_post()

        with patch(
            "odoo.addons.account_edi_ubl_cii.models.account_edi_xml_cii_facturx.AccountEdiXmlCII._export_invoice",
            side_effect=lambda m: (b"<xml>Tmp</xml>", {}),
        ) as patched:
            self.env["ir.actions.report"].with_context(
                force_report_rendering=True
            )._render("account.account_invoices", invoice.ids)
            patched.assert_called_once()

    def test_actual_delivery_date_in_cii_xml(self):
        invoice = self.env["account.move"].create(
            {
                "partner_id": self.partner_a.id,
                "move_type": "out_invoice",
                "invoice_line_ids": [Command.create({"product_id": self.product_a.id})],
                "delivery_date": "2024-12-31",
            }
        )
        invoice.action_post()

        xml_attachment = self.env["ir.attachment"].create(
            {
                "raw": self.env["account.edi.xml.cii"]._export_invoice(invoice)[0],
                "name": "test_invoice.xml",
            }
        )
        xml_tree = etree.fromstring(xml_attachment.raw)
        actual_delivery_date = xml_tree.find(
            ".//ram:ActualDeliverySupplyChainEvent/ram:OccurrenceDateTime/udt:DateTimeString",
            {
                "rsm": "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100",
                "ram": "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100",
                "udt": "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100",
            },
        )
        self.assertEqual(actual_delivery_date.text, "20241231")
