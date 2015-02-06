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

import time
import datetime
from openerp.osv import osv
from openerp.report import report_sxw


class count_3_validation(report_sxw.rml_parse):

    def _get_inventory_name(self, form):
        name = ''
        inventory_obj = self.pool.get('stock.inventory')
        for inventory in inventory_obj.browse(self.cr, self.uid, form['inventory_id']):
            name = inventory.name
        return name

    def _get_inventory_date(self, form):
        date = datetime.date.today()
        inventory_obj = self.pool.get('stock.inventory')
        for inventory in inventory_obj.browse(self.cr, self.uid, form['inventory_id']):
            date = inventory.date
        return date

    def _get_inventory_responsible(self, form, number):
        sql = 'Select max(responsible_'
        if number == 2:
            sql = sql + '2'
        else:
            sql = sql + '1'
        sql = sql + ') As responsible From stock_inventory_count_3  Where inventory_id = %s And sector = %s '
        self.cr.execute(sql, (form['inventory_id'], form['sector']))
        sql_res = self.cr.dictfetchone()
        return sql_res['responsible']

    def lines(self, form):
        self.cr.execute(
            'Select P.default_code as product_code, T.name as product_name, C.product_qty_1, C.product_qty_2, C.difference '
            'From stock_inventory_count_3 C, product_product P, product_template T '
            'Where C.inventory_id = %s '
            'And C.sector = %s '
            'And C.difference <> 0 '
            'And P.id = C.product_id '
            'And T.id = P.product_tmpl_id '
            'Order By T.name',
            (form['inventory_id'], form['sector'])
        )
        return self.cr.dictfetchall()

    def __init__(self, cr, uid, name, context):
        super(count_3_validation, self).__init__(cr, uid, name, context=context)
        self.localcontext.update( {
            'time': time,
            "get_inventory_name": self._get_inventory_name,
            "get_inventory_date": self._get_inventory_date,
            "get_inventory_responsible": self._get_inventory_responsible,
            "lines": self.lines,
        })


class report_count_3_validation(osv.AbstractModel):
    _name = 'report.physical_inventory_multiple_counts.count_3_validation_template'
    _inherit = 'report.abstract_report'
    _template = 'physical_inventory_multiple_counts.count_3_validation_template'
    _wrapped_report_class = count_3_validation

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
