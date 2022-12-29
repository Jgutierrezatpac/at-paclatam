# -*- coding: utf-8 -*-

def migrate(cr, version):
    cr.execute(
        """
        UPDATE ir_module_module 
        SET state = 'uninstalled'
        WHERE name = 'rental_billind_pac'
        """
    )
    