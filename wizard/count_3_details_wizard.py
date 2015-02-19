
from openerp import tools
from openerp.osv import fields, osv
from openerp.tools.translate import _

class count_3_details_report(osv.osv_memory):

    _name = "count_3.details.report"
    _description = "Wizard that generates reports for physical inventory counts"
    _columns = {
        'inventory_id': fields.many2one('stock.inventory', 'Select inventory', ondelete='cascade', select=True),
        'sector': fields.char('Select sector', size=100),
    }

    def open_table(self, cr, uid, ids, context=None):
        var = 1
        if context is None:
            context = {}
        data = self.read(cr, uid, ids, context=context)[0]
        ctx = context.copy()
        ctx['inventory_id'] = data['inventory_id']
        ctx['sector'] = data['sector']
        return {
            'name': _('Inventory count 3 details'),
            'view_type': 'form',
            'view_mode': 'tree',
            'res_model': 'stock.inventory.count_3',
            'type': 'ir.actions.act_window',
            'context': ctx,
        }