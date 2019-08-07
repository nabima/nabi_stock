# -*- coding: utf-8 -*-

from openerp.osv import osv,fields
from openerp.exceptions import  Warning
from openerp.models import NewId
from openerp import tools
from openerp import api, models
class demande_appro_line(osv.osv):
    _name = 'demande.appro.line'
    """
    Lignes Demande d'approvisionnement destinée au commerciaux
    
    """
    _columns = {
        'date':             fields.date('Date'), 
        'destination_id':   fields.many2one('stock.warehouse',u'Dépôt destination'),
        'type':             fields.selection([('transfert','Transfert'),('achat','Achat'),('importation','Importation'),('new','Nouveau article')],string=u'Type d''appro.'),
        'origin':           fields.selection([('sale','Bon de commande'),('stock','Stock'),('sample','Echantillon'),('showroom','Showroom')],string=u'Origine de la demande'),
        'priority':         fields.selection([(0,'Urgente'),(1,'haute'),(2,'Normale'),(3,'basse')],string=u'Priorité'),
        'source_id':        fields.many2one('stock.warehouse',u'Dépôt source'),
        'sale_order':       fields.many2one('sale.order','bon de commande'),
        'product_id':       fields.many2one('product.product','Article'),
        'parent':           fields.many2one('demande.appro','Parent')  ,      
        'state':            fields.selection([('draft','Nouveau'),('confirm',u'Confirmé'),('done',u'Terminée'),('cancel',u'Annulée')],string=u'Etat'),
        'product_qty':      fields.float(u'Quantité'),
    }
class demande_appro(osv.osv):
    _name = 'demande.appro'
    """ 
    Demande d'approvisionnement destinée au commerciaux
    
    """
    _columns = {
        'name':             fields.char('Demande No:', default='/'),
        'lines':            fields.one2many('demande.appro.line','parent','Lignes'),
        'state':            fields.selection([('draft','Nouveau'),('confirm',u'Confirmé'),('done',u'Terminée'),('cancel',u'Annulée')],string=u'Etat'),
    }    
    
    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        if vals.get('name', '/') == '/':
            vals['name'] = self.pool.get('ir.sequence').get(cr, 1, 'demande.appro', context=context) or '/'
        new_id = super(demande_appro, self).create(cr, uid, vals, context=context)
        return new_id
        
class ordre_transfert_line(osv.osv):
    _name = 'ordre.transfert.line'
    """
    Ordre de transfert entre site
    
    """
    def stock_dispo(self,cr,uid,ids,name,arg,context=None):
        res = {}
        for o in self.browse(cr,uid,ids):
            stock = self.pool['stock.quant'].search_read(cr,1,[('location_id.usage','=','internal'),('product_id','=',o.product_id.id),('reservation_id','=',False),('location_id.warehouse_id','=',o.parent.source_id.id)])
            res[o.id] = stock and sum([x['qty'] for x in stock]) or False
        return res
            
            
    _columns = {
        'parent':           fields.many2one('ordre.transfert','Parent'),
        'origin':           fields.char(string=u'Origine de la demande'),
        'product_id':       fields.many2one('product.product',u'Article'),
        'picking_out_id':   fields.many2one('stock.picking',u'Bon de sortie'),
        'picking_in_id':    fields.many2one('stock.picking',u"Bon d''entrée"),        
        'state':            fields.selection([('draft','Nouveau'),('confirm',u'Confirmé'),('done',u'Terminée'),('cancel',u'Annulée')],string=u'Etat', default="draft"),
        'product_qty':      fields.float(u'Quantité'),
        'stock':            fields.function(stock_dispo,string="Stock disponible",type="float"),
    }    
                

class ordre_transfert(osv.osv):
    _name = 'ordre.transfert'
    """
    Ordre de transfert entre site
        
    """
    
    
    _columns = {
        'name':             fields.char('Demande No:',default='/'),
        'state':            fields.selection([('draft','Nouveau'),('confirm',u'Confirmé'),('done',u'Terminée'),('cancel',u'Annulée')],string=u'Etat',default="draft"),
        'date':             fields.date('Date'), 
        'date_min':         fields.date(u'Date souhaité'), 
        'origin':           fields.char(string=u'Origine de la demande'),
        'source_id':        fields.many2one('stock.warehouse',u'Dépôt source'),
        'destination_id':   fields.many2one('stock.warehouse',u'Dépôt destination'),
        'location_id':      fields.many2one('stock.location','Emplacement source'),
        'location_dest_id': fields.many2one('stock.location','Emplacement de destination'),
        'lines':            fields.one2many('ordre.transfert.line','parent','Lignes'),
        'product_id': fields.related('lines', 'product_id', type='many2one', relation='product.product', string='Product'),
    }
    def eunlink(self, cr,uid,ids,context=None) :
        
        
        o = self.browse(cr,uid,ids)
        if o.state == 'draft':
            o.state='cancel'
            return True
            
        elif o.state == 'cancel' :
            return True
        
        elif  o.lines and (o.lines[0].picking_out_id.state != 'draft' or o.lines[0].picking_in_id.state != 'draft'):
            raise Warning(u"Suppression impossible",u"Au moins un bon de transfert lié est validé! ")
        
        elif o.lines and o.state in ('confirm','done'):
            o.lines[0].picking_out_id.action_cancel()
            o.lines[0].picking_in_id.action_cancel()
            o.state='cancel'
            return True
        
        else:
            raise Warning(u'Opération non autorisé',u"Seulement les OT dans l'état 'Nouveau' qui peuvent être supprimés !")
        
            
            
            
            
            
            
    
    
    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        if vals.get('name', '/') == '/':
            vals['name'] = self.pool.get('ir.sequence').get(cr, 1, 'ordre.transfert', context=context) or '/'
        new_id = super(ordre_transfert, self).create(cr, uid, vals, context=context)
        return new_id
    
    def order_confirm(self,cr,uid,ids,context=None):
        """
        0- Vérifier les disponibilités.
        1- Reserver les articles
        2- Créer les opération de picking
            2-1- dereserver les articles.
            2-2- Livrer vers l'emplacemet marchandise en route
            2-3- Réceptionner de l'emplacement MER
        3- changer les status
        """
        sp = self.pool['stock.picking']
        
        for o in self.browse(cr,uid,ids):
            """ Vérifier les emplacement"""
            if o.source_id == o.destination_id and (not o.location_id or not o.location_dest_id ):
                raise Warning(u"Erreur de saisie !", u"Dans le même dépôt il faut entrer les emplacements source et destination")
                
            if  o.location_id == o.location_dest_id != False:
                raise Warning(u"Erreur de saisie !", u"l'emplacement source doit être différent de l'emplacement de destination")
            
            """ Vérifier les disponibilités """
            for l in o.lines:
                if l.stock < l.product_qty:
                    raise Warning(u"L'article (%s - %s) n'est pas Disponible !" % (l.product_id.default_code ,l.product_id.name),
                                  u"Le stock sur l'emplacement source (%s) est de : %s\n %s" % (o.source_id.name, l.stock, l.product_qty))

            """ Créer opération de SORTIE"""
            picking_type_out_id  = self.pool['stock.picking.type'].search_read(cr,1,[('warehouse_id','=',o.source_id.id),('code','=','internal')])
            picking_type_in_id   = self.pool['stock.picking.type'].search_read(cr,1,[('warehouse_id','=',o.destination_id.id),('code','=','internal')])
            
            if not (picking_type_out_id and picking_type_in_id) : 
                raise Warning(u"Erreur de paramètrage !",u"Vérifiez les types d'opérations")
                        
            if picking_type_out_id:
                vals = {
                        'date':         o.date,
                        'date_min':     o.date_min,
                        'origine':      o.name,
                        'company_id':   o.source_id.company_id.id,
                        'picking_type_id':  picking_type_out_id[0]['id']
                        }
                picking_out  = sp.create(cr,1,vals)
                #picking_out.message_post(type="notification",body=u"Ce Transfert est créé et validé par %s" % o.create_uid.name)
            
            if not picking_type_out_id : 
                raise Warning(u"Erreur création !",u"Le bon de sortie ne peut pas être créé !")
            
            if picking_type_in_id:
                vals = {
                        'date':         o.date,
                        'date_min':     o.date_min,
                        'origine':      o.name,
                        'company_id':   o.destination_id.company_id.id,
                        'picking_type_id':  picking_type_in_id[0]['id']
                        }
                picking_in  = sp.create(cr,1,vals)
                #picking_in.message_post(type="notification",body=u"Ce Transfert est créé et validé par %s" % o.create_uid.name)

            if not picking_type_in_id : 
                raise Warning(u"Erreur création !",u"Le bon d'entrée ne peut pas être créé !")    
            
            if not o.location_id:
                emp_src  =  [x.id for x in o.source_id.location_ids      if x.principal == True]
                if not emp_src  : 
                    raise Warning(u"Erreur de paramètrage !",u"Il faut paramétrer l'emplacement principal dans l'entrepôt  (%s) ! " % o.source_id.name)
                
            if not o.location_dest_id:
                emp_dest = [x.id for x in o.destination_id.location_ids if x.principal == True]
                if not emp_dest : 
                    raise Warning(u"Erreur de paramètrage !",u"Il faut paramétrer l'emplacement principal dans l'entrepôt  (%s) !" % o.destination_id.name)
            
            emp_mer  = 491
            
            
            
            vals = []
            vals2 = []
            for l in o.lines:
                
                if not l.picking_out_id:
                    vals = vals  + [(0,0,{
                            'date':                 o.date,
                            'date_min':             o.date_min,
                            'product_id' :          l.product_id.id,
                            'product_uom_qty' :     l.product_qty,
                            'product_uom':          l.product_id.uom_id.id,
                            'name':                 l.product_id.name,
                            'location_id':          o.location_id.id or emp_src[0],
                            'location_dest_id':     emp_mer,
                            'company_id':           o.source_id.company_id.id  ,                      
                        })]
                if not l.picking_in_id:
                    vals2 += [(0,0,{
                            'date':                 o.date,
                            'date_min':             o.date_min,
                            'product_id' :          l.product_id.id,
                            'product_uom_qty' :     l.product_qty,
                            'product_uom':          l.product_id.uom_id.id,
                            'name':                 l.product_id.name,
                            'location_id':          emp_mer,
                            'location_dest_id':     o.location_dest_id.id or emp_dest[0],  
                            'company_id':           o.destination_id.company_id.id,                   
                        })]
                l.picking_out_id  = picking_out
                l.picking_in_id   = picking_in
            
                
            
            
            if vals and picking_out and picking_in:
                
                sp.write(cr,uid,[picking_out],{'move_lines':vals})
                sp.write(cr,uid,[picking_in],{'move_lines':vals2})
            
            
            
            for l in o.lines:
                
                
                l.picking_out_id.action_confirm()  
                l.picking_out_id.action_assign()
                
                l.picking_in_id.action_confirm()  
                l.picking_in_id.action_assign()                       
                                            
            o.state  = 'confirm'    
        return True
    

class stock_location(osv.osv):
    _inherit="stock.location"
    _columns = {
        'warehouse_id' :    fields.many2one('stock.warehouse',u'Entrepôts'),
        'reservation':      fields.boolean(u'Emplacement pour réservation'),
        'principal':       fields.boolean(u'Emplacement principal'),
    }

class stock_warehouse(osv.osv):
    _inherit="stock.warehouse"
    _columns = {
        'location_ids' : fields.one2many('stock.location','warehouse_id' ,'Emplacements')

    }
    
class stock_picking(osv.osv):
    _inherit = "stock.picking"

    def action_confirm(self,cr,uid,ids,context=None):

        todo = []
        todo_force_assign = []
        
        for picking in self.browse(cr, uid, ids, context=context):
            print "################# %s" % picking.location_id.usage
            if picking.location_id.usage in ('supplier', 'inventory', 'production'):
                todo_force_assign.append(picking.id)
            for r in picking.move_lines:
                if r.state == 'draft':
                    todo.append(r.id)
        if len(todo):
            self.pool.get('stock.move').action_confirm(cr, uid, todo, context=context)

        if todo_force_assign:
            self.force_assign(cr, uid, todo_force_assign, context=context)
        return True
    
#TODO: Etat de rupture avec button action
#TODO: Etat de

class purchase_stats_historique(osv.osv):
    _name="purchase.stats.historique"
    _columns = {
    
        'partner_id':   fields.many2one('res.partner','Fournisseur'),
        'ref':          fields.related('partner_id','ref',type="char",string="code"),
        'currency_id':  fields.related('partner_id','currency_id',type="char",string="Devise"),   
        'year':         fields.integer(u'Année'),
        'month':         fields.integer(u'Mois'),
        'amount':       fields.float(u"Chiffre d'affaire"),
        'taux':         fields.float(u"%Evolution"),
    }

class purchase_stats_cumul(osv.osv):
    _name="purchase.stats.cumul"
    _auto = False
    _columns = {
        'id':           fields.integer('id'),
        'partner_id':   fields.many2one('res.partner','Fournisseur'),
        'ref':          fields.related('partner_id','ref',type="char",string="code"),
        'currency_id':  fields.related('partner_id','currency_id',type="char",string="Devise"),   
        'year':         fields.integer(u'Année'),
        'month':        fields.integer(u'Mois'),     
        'amount':       fields.float(u"Chiffre d'affaire"),
          
    }
    
    
    def init(self, cr):
        tools.sql.drop_view_if_exists(cr, 'purchase_stats_cumul')
        cr.execute("""
            CREATE OR REPLACE VIEW purchase_stats_cumul AS (
                    select 
                        row_number() OVER () as id,
                        rp.id as partner_id,
                        rp.ref,
                        rp.currency_id,
                        sum(po.amount_total) amount,
                        extract(year from date_order) as year, 
                        extract(month from date_order) as month
                    from purchase_order po, res_partner rp
                    where rp.id = po.partner_id
                    group by rp.id, rp.ref,rp.currency_id,extract(year from date_order) , extract(month from date_order)
                    
                    union
                    select id,partner_id,null,null,amount,year, month
                    from purchase_stats_historique
                )
                """)

class purchase_stats(osv.osv):
    _name="purchase.stats"
    _auto = False
    _columns = {
        'id':           fields.integer('id'),
        'partner_id':   fields.many2one('res.partner','Fournisseur'),
        'ref':          fields.related('partner_id','ref',type="char",string="code"),
        'currency_id':  fields.related('partner_id','currency_id',relation="res.currency",type="many2one",string="Devise"),   
        'n_4':       fields.float(u"n-4"),
        'n_3':       fields.float(u"n-3"),
        'n_2':       fields.float(u"n-2"),
        'n_1':       fields.float(u"n-1"),
        'n':         fields.float(u"n"),
        'p_3':       fields.float(u"p-3"),
        'p_2':       fields.float(u"p-2"),
        'p_1':       fields.float(u"p-1"),
        'p':         fields.float(u"p"),
    }
    
    def init(self, cr):
        tools.sql.drop_view_if_exists(cr, 'purchase_stats')
        cr.execute("""CREATE OR REPLACE VIEW purchase_stats AS (
                   with a as (select partner_id, year, sum(amount) as amount , 
                                    nth_value(sum(amount),5) over (partition by partner_id order by year desc) as n_4,
                                    nth_value(sum(amount),4) over (partition by partner_id order by year desc) as n_3,
                                    nth_value(sum(amount),3) over (partition by partner_id order by year desc) as n_2,
                                    nth_value(sum(amount),2) over (partition by partner_id order by year desc) as n_1,
                                    nth_value(sum(amount),1) over (partition by partner_id order by year desc) as n
                                from purchase_stats_historique
                                group by partner_id,year)
                    select 
                        row_number() over() as id,
                        partner_id, null as ref,null as currency_id,
                        max(n_4) as n_4, 
                        max(n_3) as n_3, 
                        max(n_2) as n_2, 
                        max(n_1) as n_1, 
                        max(n) as n,
                        100* max(n_3)/ nullif(max(n_4) ,0) as p_3, 
                        100* max(n_2)/ nullif(max(n_3) ,0) as p_2, 
                        100* max(n_1)/ nullif(max(n_2) ,0) as p_1, 
                        100* max(n)  / nullif(max(n_1) ,0) as p
                    from   a
                    group by partner_id        )""")
                            
