# -*- coding: utf-8 -*-
{
    'name': 'Integración Nextbyn',
    'version': '18.0.2.0.0',
    'category': 'Integration',
    'summary': 'Integración con portal Nextbyn - Generación de CSVs según documentación oficial',
    'description': """
        Integración Nextbyn - MundoLimpio
        ==================================
        
        Módulo que genera archivos CSV para el portal Nextbyn según
        la documentación oficial "Manual de implementación de interfases".
        
        Características principales:
        * Generación de archivos CSV con formato oficial Nextbyn
        * Nombres de archivo con timestamp: {Entidad}EEEEEEAAAAMMDDHHMMSS.csv
        * Separador punto y coma (;)
        * Primera fila con headers
        * 7 entidades soportadas:
          - Articulos
          - Clientes
          - Comprobantes
          - PersonalComercial
          - ClientesRuta
          - RutasDeVenta
          - StockFisico
        * Formatos de booleanos según especificación (0/1, SI/NO, YES/NO)
        * Formatos de fecha según especificación (yyyy/MM/dd, dd/MM/yyyy)
        * Configuración flexible de empresa (código 6 dígitos)
        * Mapeos de canales/subcanales
        * Trazabilidad completa de exportaciones
        * Programación automática (cron) o ejecución manual
        * Logs detallados por archivo y corrida
        
        Documentación base: Manual de implementación de interfases Nextbyn
        
        Autor: MundoLimpio
        Fecha: 2025
    """,
    'author': 'Aftermoves',
    'website': 'https://aftermoves.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'product',
        'stock',
        'account',
        'sale',
        'l10n_ar',  # Localización Argentina (CUIT, tipos contribuyente)
        'hr',  # Para personal comercial/vendedores
    ],
    'data': [
        # Seguridad
        'security/security.xml',
        'security/ir.model.access.csv',
        
        # Datos maestros
        'data/softys_canal_data.xml',
        'data/softys_subcanal_data.xml',
        'data/softys_mapping_data.xml',
        
        # Vistas - Menús (primero para que las acciones puedan referenciarlos)
        'views/menu.xml',
        
        # Vistas - Productos y Almacenes
        'views/product_views.xml',
        
        # Vistas - Configuración
        'views/softys_connector_views.xml',
        'views/softys_export_views.xml',
        
        # Vistas - Configuración Dinámica CSVs
        'views/nextbyn_entity_views.xml',
        'views/nextbyn_cron_views.xml',
        
        # Wizards
        'views/softys_export_wizard_views.xml',
        
        # Datos de entidades preconfiguradas
        'data/nextbyn_entity_data.xml',
        'data/nextbyn_cron_data.xml',
    ],
    'demo': [
        # 'demo/demo_data.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
