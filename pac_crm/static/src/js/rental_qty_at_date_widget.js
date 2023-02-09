odoo.define('pac_crm.QtyAtDateWidget', function (require) {
    "use strict";
    
    const core = require('web.core');
    const QWeb = core.qweb;
    
    const Context = require('web.Context');
    const data_manager = require('web.data_manager');
    const time = require('web.time');
    
    const QtyAtDateWidget = require('sale_stock.QtyAtDateWidget');
    
    QtyAtDateWidget.include({
    
        /**
         * Redirect to the product gantt view.
         *
         * @private
         * @param {MouseEvent} event
         * @returns {Promise} action loaded
         */
        _getContent() {
            if (!this.data.is_rental) {
                return this._super();
            }
            const $content = $(QWeb.render('sale_stock_renting.QtyDetailPopOver', {
                data: this.data,
            }));
            $content.on('click', '.action_open_renting', this._onRentalGanttView.bind(this));
    
            return $content;
        },
    
    });
    
    });
    