import logging
import time

from openerp.osv import fields, osv, orm
from openerp.tools.translate import _
from openerp.tools import mute_logger
import openerp.addons.decimal_precision as dp
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT

_logger = logging.getLogger(__name__)


class stock_inventory(osv.osv):
    _inherit = 'stock.inventory'

    def _get_available_filters_multicount(self, cr, uid, context=None):
        """
           This function will return the list of filter allowed according to the options checked
           in 'Settings\Warehouse'.

           :rtype: list of tuple
        """
        #default available choices
        res_filter = [('none', _('All products')), ('category', _('All products of one category')),
                      ('product', _('One product only'))]
        settings_obj = self.pool.get('stock.config.settings')
        config_ids = settings_obj.search(cr, uid, [], limit=1, order='id DESC', context=context)
        #If we don't have updated config until now, all fields are by default false and so should be not displayed
        if not config_ids:
            return res_filter

        stock_settings = settings_obj.browse(cr, uid, config_ids[0], context=context)
        if stock_settings.group_stock_tracking_owner:
            res_filter.append(('owner', _('One owner only')))
            res_filter.append(('product_owner', _('One product for a specific owner')))
        if stock_settings.group_stock_tracking_lot:
            res_filter.append(('lot', _('One Lot/Serial Number')))
        if stock_settings.group_stock_packaging:
            res_filter.append(('pack', _('A Pack')))
        return res_filter

    # Added relation fields to inventory counts

    INVENTORY_STATE_SELECTION = [
        ('draft', 'Draft'),
        ('confirm', 'In Progress'),
        ('count_3_consolidate', 'Count 3 consolidated'),
        ('count_3_select', 'Count 3 selected'),
        ('count_4_generate', 'Count 4 generated'),
        ('count_loaded', 'Count 4 loaded to physical'),
        ('cancel', 'Cancelled'),
        ('done', 'Validated'),
    ]

    _columns = {
        'inventory_counts_1_2_id': fields.one2many('stock.inventory.counts_1_2', 'inventory_id',
                                                   'Inventory counts 1 and 2',
                                                   readonly=True,
                                                   states={'draft': [('readonly', False)]}),
        'inventory_count_3_id': fields.one2many('stock.inventory.count_3', 'inventory_id',
                                                'Inventory count 3',
                                                readonly=True,
                                                states={'draft': [('readonly', False)]}),
        'inventory_count_4_id': fields.one2many('stock.inventory.count_4', 'inventory_id',
                                                'Inventory count 4',
                                                readonly=True,
                                                states={'draft': [('readonly', False)]}),
        'selected_count': fields.selection((('1', 'Count 1'), ('2', 'Count 2')),
                                           'Selected count',
                                           readonly=True,
                                           states={'count_3_consolidate': [('readonly', False)]},
                                           required=False,
                                           select=True),
        'category_id': fields.many2one('product.category', 'Product Category', readonly=True,
                                       states={'draft': [('readonly', False)]},
                                       help="Specify Category to focus your inventory on a particular category of products."),
        'state': fields.selection(INVENTORY_STATE_SELECTION, 'Status', readonly=True, select=True),
        'filter': fields.selection(_get_available_filters_multicount, 'Selection Filter', required=True),
    }

    _defaults = {
        'category_id': 1,
    }

    def prepare_inventory_multicount(self, cr, uid, ids, context=None):
        inventory_line_obj = self.pool.get('stock.inventory.line')
        for inventory in self.browse(cr, uid, ids, context=context):
            #clean the existing inventory lines before redoing an inventory proposal
            line_ids = [line.id for line in inventory.line_ids]
            inventory_line_obj.unlink(cr, uid, line_ids, context=context)
            #compute the inventory lines and create them
            vals = self._get_inventory_lines_multicount(cr, uid, inventory, context=context)
            for product_line in vals:
                inventory_line_obj.create(cr, uid, product_line, context=context)
        return self.write(cr, uid, ids, {'state': 'confirm', 'date': time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})

    def _get_inventory_lines_multicount(self, cr, uid, inventory, context=None):
        location_obj = self.pool.get('stock.location')
        product_obj = self.pool.get('product.product')
        location_ids = location_obj.search(cr, uid, [('id', 'child_of', [inventory.location_id.id])], context=context)
        domain = ' location_id in %s'
        args = (tuple(location_ids),)
        if inventory.partner_id:
            domain += ' and s.owner_id = %s'
            args += (inventory.partner_id.id,)
        if inventory.lot_id:
            domain += ' and s.lot_id = %s'
            args += (inventory.lot_id.id,)
        if inventory.product_id:
            domain += 'and s.product_id = %s'
            args += (inventory.product_id.id,)
        if inventory.package_id:
            domain += ' and s.package_id = %s'
            args += (inventory.package_id.id,)

        cr.execute('''
           SELECT p.id as product_id, sum(qty) as product_qty, s.location_id, s.lot_id as prod_lot_id, s.package_id,
           s.owner_id as partner_id
           FROM product_product p
           LEFT JOIN stock_quant s
           ON s.product_id = p.id
           and''' + domain + '''
           GROUP BY p.id, s.location_id, s.lot_id, s.package_id, s.owner_id
        ''', args)
        vals = []
        for product_line in cr.dictfetchall():
            #replace the None the dictionary by False, because falsy values are tested later on
            for key, value in product_line.items():
                if not value:
                    product_line[key] = False
            product_line['location_id'] = inventory.location_id.id
            product_line['inventory_id'] = inventory.id
            product_line['theoretical_qty'] = product_line['product_qty']
            product_line['product_qty'] = 0
            insert_product = False
            if product_line['product_id']:
                product = product_obj.browse(cr, uid, product_line['product_id'], context=context)
                product_line['product_uom_id'] = product.uom_id.id
                if inventory.category_id:
                    if (product.categ_id.parent_left >= inventory.category_id.parent_left and
                            product.categ_id.parent_right <= inventory.category_id.parent_right):
                        insert_product = True
                else:
                    insert_product = True
            if insert_product:
                vals.append(product_line)
        return vals

    def action_consolidate_count_3(self, cr, uid, ids, context=None):
        """ To consolidate counts 1 and 2 into count 3
        @param self: The object pointer.
        @param cr: A database cursor
        @param uid: ID of the user currently logged in
        @param ids: the ID or list of IDs if we want more than one
        @param context: A standard dictionary
        @return:
        """
        if context is None:
            context = {}
        inventory_line_pool = self.pool.get('stock.inventory.line')
        count_1_2_pool = self.pool.get('stock.inventory.counts_1_2')
        count3_pool = self.pool.get('stock.inventory.count_3')
        if ids:
            count3_ids = count3_pool.search(cr, uid, [('inventory_id', 'in', ids)])
            count3_pool.unlink(cr, uid, count3_ids, context=context)
            domain = ' l.inventory_id in %s'
            args = (tuple(ids),)
            cr.execute('''
                Select l.company_id, l.inventory_id, l.location_id, l.product_id, c.sector, coalesce(c.default_code, '') as default_code,
                  Max(Case When c.count_number = 1 then coalesce(c.product_qty, 0) Else 0 End) As product_qty_1,
                  Max(Case When c.count_number = 1 then 0 Else coalesce(c.product_qty, 0) End) As product_qty_2,
                  Max(Case When c.count_number = 1 then coalesce(c.responsible, '') Else '' End) As responsible_1,
                  Max(Case When c.count_number = 1 then '' Else coalesce(c.responsible, '') End) As responsible_2,
                  0 as final_product_qty,
                  Max(Case When c.count_number = 1 then coalesce(c.product_qty, 0) Else 0 End)
                  - Max(Case When c.count_number = 1 then 0 Else coalesce(c.product_qty, 0) End) As difference
                From stock_inventory_line l
                Join stock_inventory_counts_1_2 c
                On c.company_id = l.company_id
                And c.inventory_id = l.inventory_id
                And c.location_id = l.location_id
                And c.product_id = l.product_id
                Where''' + domain + '''
                Group By l.company_id, l.inventory_id, l.location_id, l.product_id, c.sector, coalesce(c.default_code, '')
                Order By l.company_id, l.inventory_id, l.location_id, c.sector, l.product_id
            ''', args)
            for line in cr.dictfetchall():
                sector = line['sector']
                data = {
                    'company_id': line['company_id'],
                    'inventory_id': line['inventory_id'],
                    'location_id': line['location_id'],
                    'product_id': line['product_id'],
                    'sector': line['sector'],
                    'default_code': line['default_code'],
                    'product_qty_1': line['product_qty_1'],
                    'product_qty_2': line['product_qty_2'],
                    'responsible_1': line['responsible_1'],
                    'responsible_2': line['responsible_2'],
                    'final_product_qty': line['final_product_qty'],
                    'difference': line['difference']
                }
                count3_pool.create(cr, uid, data, context=context)
            for inv in self.browse(cr, uid, ids, context=context):
                self.write(cr, uid, [inv.id], {'state': 'count_3_consolidate'})

    def action_generate_count_4(self, cr, uid, ids, context=None):
        """ To generate count 4 based on selected count
        @param self: The object pointer.
        @param cr: A database cursor
        @param uid: ID of the user currently logged in
        @param ids: the ID or list of IDs if we want more than one
        @param context: A standard dictionary
        @return:
        """
        if context is None:
            context = {}
        inventory_pool = self.pool.get('stock.inventory')
        inventory_line_pool = self.pool.get('stock.inventory.line')
        count3_pool = self.pool.get('stock.inventory.count_3')
        count4_pool = self.pool.get('stock.inventory.count_4')
        product_pool = self.pool.get('product.product')
        if ids:
            count4_ids = count4_pool.search(cr, uid, [('inventory_id', 'in', ids)])
            count4_pool.unlink(cr, uid, count4_ids, context=context)
            #count3_ids = count3_pool.search(cr, uid, [('inventory_id', 'in', ids)])
            #for count in count3_pool.browse(cr, uid, count3_ids, context=context):
            # domain = ' l.inventory_id in %s'
            # args = (tuple(ids),)
            # cr.execute('''
            #    SELECT l.company_id, l.inventory_id, l.location_id, l.product_id, SUM(Coalesce(c.final_product_qty, 0)) as final_product_qty
            #    FROM stock_inventory_line l
            #    LEFT JOIN stock_inventory_count_3 c
            #    On c.company_id = l.company_id
            #    And c.inventory_id = l.inventory_id
            #    And c.location_id = l.location_id
            #    And c.product_id = l.product_id
            #    WHERE''' + domain + '''
            #    GROUP BY l.company_id, l.inventory_id, l.location_id, l.product_id
            # ''', args)
            domain = ' l.inventory_id in %s'
            args = (tuple(ids),)
            cr.execute('''
               SELECT l.company_id, l.inventory_id, l.location_id, l.product_id, Coalesce(c.final_product_qty, 0) as final_product_qty, SUM(Coalesce(s.qty, 0)) AS product_qty, COALESCE(pph.cost, 0) AS cost
               FROM stock_inventory_line l
               JOIN product_product p
               ON p.id = l.product_id
               LEFT JOIN stock_inventory_count_3 c
               On c.company_id = l.company_id
               And c.inventory_id = l.inventory_id
               And c.location_id = l.location_id
               And c.product_id = l.product_id
               LEFT JOIN stock_quant s
               On s.company_id = l.company_id
               And s.location_id = l.location_id
               And s.product_id = l.product_id
               LEFT JOIN product_price_history pph on (pph.id = (
                   SELECT pph1.id FROM product_price_history pph1
                       WHERE pph1.product_template_id = p.product_tmpl_id
                       ORDER BY pph1.datetime DESC
                       LIMIT 1)
               )
               WHERE l.inventory_id in %s
               GROUP BY l.company_id, l.inventory_id, l.location_id, l.product_id, Coalesce(c.final_product_qty, 0), COALESCE(pph.cost, 0)
               ORDER BY l.company_id, l.inventory_id, l.location_id, l.product_id
            ''', args)
            cr_count = cr.dictfetchall()
            for count in cr_count:
                company_id = count['company_id']
                inventory_id = count['inventory_id']
                location_id = count['location_id']
                product_id = count['product_id']
                product_qty = count['final_product_qty']
                theoretical_qty = count['product_qty']
                # theoretical_qty = 0
                theoretical_value = 0
                product_cost = 0

                # domain = ' company_id = %s'
                # args = (company_id,)
                # domain += ' and location_id = %s'
                # args += (location_id,)
                # domain += ' and product_id = %s'
                # args += (product_id,)
                # cr.execute('''
                #    SELECT Coalesce(sum(qty), 0) as product_qty
                #    FROM stock_quant s
                #    WHERE''' + domain
                # , args)
                # for theoretical in cr.dictfetchall():
                #     theoretical_qty = theoretical['product_qty']
                # if not theoretical_qty:
                #     theoretical_qty = 0

                #product_cost = count.product_id.product_tmpl_id.standard_price
                #product_ids = product_pool.search(cr, uid, [('id', '=', product_id)])
                # product = product_pool.browse(cr, uid, product_id, context=context)
                # product_cost = product.product_tmpl_id.standard_price
                product_cost = count['cost']
                product_value = product_qty * product_cost
                difference_qty = 0
                difference_value = 0
                final_product_qty = product_qty
                final_product_value = product_value

                #inventory_line_ids = inventory_line_pool.search(cr, uid, [('company_id', '=', company_id),
                #                                                          ('inventory_id', '=', inventory_id),
                #                                                          ('location_id', '=', location_id),
                #                                                          ('product_id', '=', product_id)])
                #for inventory_line in inventory_line_pool.browse(cr, uid, inventory_line_ids, context=context):
                #    theoretical_qty = inventory_line.theoretical_qty

                theoretical_value = theoretical_qty * product_cost
                difference_qty = product_qty - theoretical_qty
                difference_value = difference_qty * product_value
                product_value = product_cost * product_qty
                difference_value = product_value - theoretical_value
                data = {
                    'company_id': company_id,
                    'inventory_id': inventory_id,
                    'location_id': location_id,
                    'product_id': product_id,
                    'product_cost': product_cost,
                    'theoretical_qty': theoretical_qty,
                    'theoretical_value': theoretical_value,
                    'product_qty': product_qty,
                    'product_value': product_value,
                    'difference_qty': difference_qty,
                    'difference_value': difference_value,
                    'final_product_qty': final_product_qty,
                    'final_product_value': final_product_value
                }
                count4_pool.create(cr, uid, data, context=context)
            for inv in self.browse(cr, uid, ids, context=context):
                self.write(cr, uid, [inv.id], {'state': 'count_4_generate'})

    def action_load_count(self, cr, uid, ids, context=None):
        """ To generate count 4 based on selected count
        @param self: The object pointer.
        @param cr: A database cursor
        @param uid: ID of the user currently logged in
        @param ids: the ID or list of IDs if we want more than one
        @param context: A standard dictionary
        @return:
        """
        if context is None:
            context = {}
        inventory_pool = self.pool.get('stock.inventory')
        inventory_line_pool = self.pool.get('stock.inventory.line')
        count4_pool = self.pool.get('stock.inventory.count_4')
        if ids:
            count4_ids = count4_pool.search(cr, uid, [('inventory_id', 'in', ids)])
            for count in count4_pool.browse(cr, uid, count4_ids, context=context):
                inventory_line_ids = inventory_line_pool.search(cr, uid, [('company_id', '=', count.company_id.id),
                                                               ('inventory_id', '=',
                                                                count.inventory_id.id),
                                                               ('location_id', '=', count.location_id.id),
                                                               ('product_id', '=', count.product_id.id)])
                for inventory_line in inventory_line_pool.browse(cr, uid, inventory_line_ids, context=context):
                    inventory_line_pool.write(cr, uid, inventory_line.id, {'product_qty': count.final_product_qty,
                                                                           'theoretical_qty': count.theoretical_qty},
                                              context=context)
            for inv in self.browse(cr, uid, ids, context=context):
                self.write(cr, uid, [inv.id], {'state': 'count_loaded'})

    def action_return_to_confirm(self, cr, uid, ids, context=None):
        """ To consolidate counts 1 and 2 into count 3
        @param self: The object pointer.
        @param cr: A database cursor
        @param uid: ID of the user currently logged in
        @param ids: the ID or list of IDs if we want more than one
        @param context: A standard dictionary
        @return:
        """
        if context is None:
            context = {}
        for inv in self.browse(cr, uid, ids, context=context):
            self.write(cr, uid, [inv.id], {'state': 'confirm'})

class stock_inventory_counts_1_2(osv.osv):
    _name = "stock.inventory.counts_1_2"
    _description = "Inventory Counts 1 and 2"
    _rec_name = "inventory_id"
    _order = "inventory_id desc"
    _columns = {
        'company_id': fields.related('inventory_id', 'company_id', type='many2one', relation='res.company',
                                     string='Company', store=True, select=True, readonly=True),
        'inventory_id': fields.many2one('stock.inventory', 'Inventory', ondelete='cascade', select=True),
        'location_id': fields.many2one('stock.location', 'Location', required=True),
        'count_number': fields.integer('Count number'),
        'sector': fields.char('Sector', size=100),
        'responsible': fields.char('Responsible', size=100),
        'default_code': fields.char('Default code', size=64),
        'product_id': fields.many2one('product.product', 'Product', required=True, select=True),
        'product_qty': fields.float('Quantity', digits_compute=dp.get_precision('Product Unit of Measure')),
    }


class stock_inventory_count_3(osv.osv):
    _name = "stock.inventory.count_3"
    _description = "Inventory Count 3"
    _rec_name = "inventory_id"
    _order = "inventory_id desc"

    def _get_inventory_status(self, cr, uid, ids, field_name, arg, context):
        res = []
        for i in ids:
            #get the status of the inventory
            sql_req= """
            SELECT i.status AS inventory_status
            FROM stock_inventory i, stock_inventory_count_3 c
            WHERE i.id = c.inventory_id
            And c.id = %d
            """ % (i,)

            cr.execute(sql_req)
            sql_res = cr.dictfetchone()

            if sql_res:
                res[i] = sql_res['status']
            else:
                res[i] = False
        return res

    _columns = {
        'company_id': fields.related('inventory_id', 'company_id', type='many2one', relation='res.company',
                                     string='Company', store=True, select=True, readonly=True),
        'inventory_id': fields.many2one('stock.inventory', 'Inventory', ondelete='cascade', select=True),
        'inventory_name': fields.related('inventory_id', 'name', type='char', string='Inventory name'),
        'location_id': fields.many2one('stock.location', 'Location', required=True),
        'sector': fields.char('Sector', size=100),
        'product_id': fields.many2one('product.product', 'Product', required=True, select=True),
        'product_code': fields.related('product_id', 'code', type='char', string='Product code'),
        'product_ean13': fields.related('product_id', 'ean13', type='char', string='Product barcode'),
        'default_code': fields.char('Default code', size=64),
        'responsible_1': fields.char('Responsible 1', size=100),
        'product_qty_1': fields.float('Quantity 1', digits_compute=dp.get_precision('Product Unit of Measure')),
        'responsible_2': fields.char('Responsible 2', size=100),
        'product_qty_2': fields.float('Quantity 2', digits_compute=dp.get_precision('Product Unit of Measure')),
        'difference': fields.float('Difference', digits_compute=dp.get_precision('Product Unit of Measure')),
        'final_product_qty': fields.float('Final quantity', digits_compute=dp.get_precision('Product Unit of Measure')),
        'inventory_state': fields.function(_get_inventory_status, type='many2one', obj="stock.inventory", method=True, string='Inventory state'),
    }

class stock_inventory_count_4(osv.osv):
    _name = "stock.inventory.count_4"
    _description = "Inventory Count 4"
    _rec_name = "inventory_id"
    _order = "inventory_id desc"

    def _get_inventory_status(self, cr, uid, ids, field_name, arg, context):
        res = []
        for i in ids:
            #get the status of the inventory
            sql_req= """
            SELECT i.status AS inventory_status
            FROM stock_inventory i, stock_inventory_count_3 c
            WHERE i.id = c.inventory_id
            And c.id = %d
            """ % (i,)

            cr.execute(sql_req)
            sql_res = cr.dictfetchone()

            if sql_res:
                res[i] = sql_res['status']
            else:
                res[i] = False
        return res

    _columns = {
        'company_id': fields.related('inventory_id', 'company_id', type='many2one', relation='res.company',
                                     string='Company', store=True, select=True, readonly=True),
        'inventory_id': fields.many2one('stock.inventory', 'Inventory', ondelete='cascade', select=True),
        'location_id': fields.many2one('stock.location', 'Location', required=True),
        'product_id': fields.many2one('product.product', 'Product', required=True, select=True),
        'product_cost': fields.float('Cost'),
        'theoretical_qty': fields.float('Theoretical quantity', digits_compute=dp.get_precision('Product Unit of Measure')),
        'theoretical_value': fields.float('Theoretical value'),
        'product_qty': fields.float('Quantity', digits_compute=dp.get_precision('Product Unit of Measure')),
        'product_value': fields.float('Product value'),
        'difference_qty': fields.float('Difference', digits_compute=dp.get_precision('Product Unit of Measure')),
        'difference_value': fields.float('Product difference'),
        'final_product_qty': fields.float('Final quantity', digits_compute=dp.get_precision('Product Unit of Measure')),
        'final_product_value': fields.float('Final product difference'),
        'inventory_state': fields.function(_get_inventory_status, type='many2one', obj="stock.inventory", method=True, string='Inventory state'),
    }

class stock_inventory_wizard_count_3_final_qty(osv.osv_memory):
    _name = "stock.inventory.wizard_count_3_final_qty"
    _description = "Apply count 3 final quantity"
    _columns = {
        'count_number': fields.selection([('1', 'Count 1'), ('2', 'Count 2')], 'Select count to apply to final quantity of count 3')
    }

    def action_wizard_count_3_final_qty(self, cr, uid, ids, context=None):
        """ To generate count 4 based on selected count
        @param self: The object pointer.
        @param cr: A database cursor
        @param uid: ID of the user currently logged in
        @param ids: the ID or list of IDs if we want more than one
        @param context: A standard dictionary
        @return:
        """
        if context is None:
            context = {}
        if ids:
            inventory_id = context.get('active_id', False)
            form = self.browse(cr, uid, ids, context=context)
            cr.execute('''Update stock_inventory_count_3 set final_product_qty = product_qty_''' + form.count_number
                       + ''' Where inventory_id = ''' + str(inventory_id))
            inventory_pool = self.pool.get('stock.inventory')
            inventory_pool.write(cr, uid, inventory_id, {'state': 'count_3_select'}, context=context)
        return {'type': 'ir.actions.act_window_close'}
