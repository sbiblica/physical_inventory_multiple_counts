# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

{
    'name': 'Physical Inventory With Multiple Counts',
    'version': '1.0.8',
    'author': 'acentoNET',
    'summary': 'Inventory, Logistic, Storage',
    'description' : """
Physical Inventory with Multiple Counts
=======================================
    """,
    'website': 'http://www.acentonet.com',
    'category': 'Warehouse Management',
    'depends': ["stock", "product"],
    'init_xml' : [],
    'demo_xml' : [],
    'data': [
        'stock_inventory_view_multicount.xml',
        'physical_inventory_multicount_report.xml',
        'views/report_inventory_counts_1_2.xml',
        'views/report_inventory_count_3.xml',
        'views/count_3_validation_template.xml',
        'views/report_inventory_count_4.xml',
        'report/count_3_differences_graph.xml',
        'report/count_4_graph.xml',
        'wizard/count_3_details_wizard.xml',
        'wizard/count_3_validation_wizard.xml',
    ],
    'sequence': 150,
    'installable': False,
    'application': True,
    'auto_install': False,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
