odoo.define('pac_crm.rental_config', function (require) {
    var core = require('web.core');
    var ProductConfiguratorWidget = require('sale_renting.rental_configurator');

    var _t = core._t;


    ProductConfiguratorWidget.include({
         /**
         * Opens the rental configurator in 'edit' mode.
         *
         * @override
         * @private
         */
        _onEditLineConfiguration: function () {
            if (this.recordData.is_rental) {// and in rental app ? (this.nodeOptions.rent)
                return
            } else {
                return
            }
        },

        _checkIfRentable: function (productId, dataPointID) {
            return
        }
    })
    return ProductConfiguratorWidget;
})