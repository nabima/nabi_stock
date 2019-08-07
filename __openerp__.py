# -*- coding: utf-8 -*-
{
    'name': 'Extension de gestion de stock',
    'version': '1.1',
    'category': 'Stock',
    'description': """
    Extension de gestion de stock
    """,
    'author': 'N.A.B.I sarl',
    'depends': ['stock'],
    'data': [ 
        'views/stock.xml',
        'data/stock_sequence.xml',
        'data/stock.location.csv',
        'workflow/workflow.csv',
        'workflow/workflow.activity.csv',
        'workflow/workflow.transition.csv',
    ],
    'installable': True,
    'auto_install': False,
}

