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

from openerp.osv import osv, fields

class count_3_validation(osv.osv_memory):
    _name = 'count_3.validation.report'
    _description = 'Physical inventory count 3 validation report'

    _columns = {
        'inventory_id': fields.many2one('stock.inventory', 'Select inventory', ondelete='cascade', select=True),
        'sector': fields.char('Select sector', size=100),
    }

    def print_report(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        datas = {}
        datas['model'] = context.get('active_model', 'ir.ui.menu')
        datas['form'] = self.read(cr, uid, ids, ['inventory_id',  'sector'], context=context)[0]
        for field in ['inventory_id']:
            if isinstance(datas['form'][field], tuple):
                datas['form'][field] = datas['form'][field][0]
        return self.pool['report'].get_action(cr, uid, [], 'physical_inventory_multiple_counts.count_3_validation_template', data=datas, context=context)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
