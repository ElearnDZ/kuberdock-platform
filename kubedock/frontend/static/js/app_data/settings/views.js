import App from 'app_data/app';
import * as utils from 'app_data/utils';
import settingsLayoutTpl from 'app_data/settings/templates/settings_layout.tpl';
import userEditTpl from 'app_data/settings/templates/user_edit.tpl';
import generalSettingsTpl from 'app_data/settings/templates/general_settings.tpl';
import generalSettingsItemTpl from 'app_data/settings/templates/general_settings_item.tpl';
import licenseTpl from 'app_data/settings/templates/license.tpl';

import 'bootstrap-select';
import 'bootstrap-editable';
import 'tooltip';

export const GeneralItemView = Marionette.ItemView.extend({
    template: generalSettingsItemTpl,
    tagName: 'div',

    className: function(){
        var className = 'link-wrapper',
            billing = this.model.collection.findWhere({name: 'billing_type'}).get('value'),
            dnsSystem = this.model.collection.findWhere(
                {name: 'dns_management_system'}).get('value'),
            name = this.model.get('name');

        if (billing === 'No billing' && _.contains(
                ['billing_url', 'billing_username', 'billing_password'], name)) {
            className += ' hidden';
        } else if (dnsSystem === 'No provider' && _.contains(
                ['dns_management_cpanel_dnsonly_host',
                 'dns_management_cpanel_dnsonly_user',
                 'dns_management_cpanel_dnsonly_token',
                 'dns_management_aws_route53_id',
                 'dns_management_aws_route53_secret',
                 'dns_management_cloudflare_email',
                 'dns_management_cloudflare_token'], name)) {
            className += ' hidden';
        } else if (dnsSystem === 'cpanel_dnsonly' && _.contains(
                ['dns_management_aws_route53_id',
                 'dns_management_aws_route53_secret',
                 'dns_management_cloudflare_email',
                 'dns_management_cloudflare_token'], name)) {
            className += ' hidden';
        } else if (dnsSystem === 'aws_route53' && _.contains(
                ['dns_management_cpanel_dnsonly_host',
                 'dns_management_cpanel_dnsonly_user',
                 'dns_management_cpanel_dnsonly_token',
                 'dns_management_cloudflare_email',
                 'dns_management_cloudflare_token'], name)) {
            className += ' hidden';
        } else if (dnsSystem === 'cloudflare' && _.contains(
                ['dns_management_cpanel_dnsonly_host',
                 'dns_management_cpanel_dnsonly_user',
                 'dns_management_cpanel_dnsonly_token',
                 'dns_management_aws_route53_id',
                 'dns_management_aws_route53_secret'], name)) {
            className += ' hidden';
        }
        return className;
    },

    ui: {
        itemField: '.settings-item',
    },

    events: {
        'change @ui.itemField': 'fieldChange'
    },

    fieldChange: function(evt){
        evt.stopPropagation();
        var trimmedValue,
            tgt = $(evt.target),
            value = tgt.val();

        if (this.model.get('options')){
            value = this.model.get('options')[+value];
        }
        trimmedValue = value.trim();

        // Strip dangling spaces for all fields except password
        if (trimmedValue !== value && !_.contains(['billing_type', 'billing_password'],
                                                 this.model.get('name'))) {
            tgt.val(trimmedValue);
            this.model.set({value: trimmedValue});
        } else {
            var that = this,
                modelName = this.model.get('name'),
                modelValue = this.model.get('value');

            if ((modelName === 'memory_multiplier' && Number(value) < Number(modelValue)) ||
                (modelName === 'cpu_multiplier' && Number(value) < Number(modelValue))) {
                tgt.val(modelValue);
                utils.modalDialogDelete({
                    title: "Change settings?",
                    body: "Decreasing multipliers will affect all nodes " +
                          "and users pods that can fail in case there is" +
                          " no resources for it to run",
                    small: true,
                    show: true,
                    footer: {
                        buttonOk: function(){
                            tgt.val(value);
                            that.model.set({value: value});
                        },
                        buttonOkText: 'Confirm',
                        buttonCancel: true
                    }
                });
            } else {
                this.model.set({value: value});
            }
        }

        // toggle billing settings, depending on selected billing type
        if (this.model.get('name') === 'billing_type'){
            $('#billing_url, #billing_username, #billing_password').parent()
                .toggleClass('hidden', this.model.get('value') === 'No billing');
        }

        if (this.model.get('name') === 'dns_management_system'){
            $('#dns_management_cpanel_dnsonly_host,' +
              '#dns_management_cpanel_dnsonly_user, #dns_management_cpanel_dnsonly_token').parent()
                .toggleClass('hidden', this.model.get('value') !== 'cpanel_dnsonly');
            $('#dns_management_aws_route53_id, #dns_management_aws_route53_secret').parent()
                .toggleClass('hidden', this.model.get('value') !== 'aws_route53');
            $('#dns_management_cloudflare_email,' +
              '#dns_management_cloudflare_token').parent()
                .toggleClass('hidden', this.model.get('value') !== 'cloudflare');
        }
    },

    onRender: function() {
        var options = this.model.get('options');
        if (options) {
            this.ui.itemField.selectpicker();
            this.ui.itemField.selectpicker(
                'val', options.indexOf(this.model.get('value')));
        }
    },
});

export const GeneralView = Marionette.CompositeView.extend({
    template: generalSettingsTpl,
    childView: GeneralItemView,
    childViewContainer: 'div#settings-list',

    events: {
        'click [type="submit"]': 'submitSettings'
    },

    validate: function(){
        var allNonEmpty = true,
            billing = this.collection.findWhere({name: 'billing_type'}),
            dnsSystem = this.collection.findWhere({name: 'dns_management_system'});

        if (billing) billing = billing.get('value');
        if (dnsSystem) dnsSystem = dnsSystem.get('value');

        if (billing === 'WHMCS'){
            allNonEmpty = this.collection.chain().filter(function(model){
                    return _.contains(['billing_url', 'billing_username', 'billing_password'],
                    model.get('name'));
                }).map(function(model){ return model.get('value'); }).all().value();
        }

        if (dnsSystem === 'cpanel_dnsonly'){
            allNonEmpty = this.collection.chain().filter(function(model){
                    return _.contains(['dns_management_cpanel_dnsonly_host',
                                       'dns_management_cpanel_dnsonly_user',
                                       'dns_management_cpanel_dnsonly_token'],
                                        model.get('name'));
                }).map(function(model){ return model.get('value'); }).all().value();
        }

        if (dnsSystem === 'aws_route53'){
            allNonEmpty = this.collection.chain().filter(function(model){
                    return _.contains(['dns_management_aws_route53_id',
                                       'dns_management_aws_route53_secret'],
                                        model.get('name'));
                }).map(function(model){ return model.get('value'); }).all().value();
        }

        if (dnsSystem === 'cloudflare'){
            allNonEmpty = this.collection.chain().filter(function(model){
                    return _.contains(['dns_management_cloudflare_email',
                                       'dns_management_cloudflare_token'],
                                        model.get('name'));
                }).map(function(model){ return model.get('value'); }).all().value();
        }

        if (!allNonEmpty) {
            allNonEmpty = false;
            utils.notifyWindow('All fields are required');
        }
        return allNonEmpty;
    },

    submitSettings: function(){
        if (!this.validate()) return false;
        var changed = this.collection.filter(function(m){ return m.hasChanged('value'); });
        if (changed.length) {
            _.each(changed, function(m){
                m.save(null, {wait: true})
                    .fail(utils.notifyWindow)
                    .done(function(){
                        var msg = (m.get('name') === 'billing_type'
                                    ? 'Billing system changed successfully'
                                    : m.get('label') + ' changed successfully');
                        utils.notifyWindow(msg, 'success');
                    });
            });
        } else {
            utils.notifyWindow('Data has not been changed.', 'success');
        }
    }
});

export const LicenseView = Marionette.ItemView.extend({
    template: licenseTpl,
    templateHelpers: {
        formatDate: function(dt) {
            if (dt) {
                return App.currentUser.localizeDatetime(dt);
            }
            return 'unknown';
        }
    },

    initialize: function(){
        this.checkLimits();
    },

    modelEvents: {
        'change' : 'modelChanged'
    },

    modelChanged: function(evt){
        this.checkLimits();
        this.render();
    },

    checkLimits: function(){
        var results,
            that = this,
            data = this.model.get('data');

        _.each(data, function(item){
            if (!that.comparison(item[0], item[1])){
                item[3] = true;
            } else {
                item[3] = false;
            }
        });

        results = _.any(data, function(item){ return !that.comparison(item[0], item[1]); });
        this.model.set({attention: results}, {silent: true});
    },

    updateStatistics: function(evt){
        evt.stopPropagation();
        var that = this;
        this.ui.updateStats.addClass('start-atimation');
        this.model.fetch({
            wait: true,
            data: {force: true},
            success: function(model, resp, opts){
                that.ui.updateStats.removeClass('start-atimation');
                utils.notifyWindow('Status has been updated', 'success');
            },
            error: function(){
                that.ui.updateStats.removeClass('start-atimation');
                utils.notifyWindow('Could not fetch statistics', 'error');
            }
        });
    },

    comparison: function(a, b){
        if (a === 'unlimited' || a === 0) a = Infinity;
        return a > b;
    },

    ui: {
        peditable   : '.peditable',
        updateStats : '.check-for-update',
        tooltip     : '[data-toggle="tooltip"]'
    },

    events: {
        'click @ui.updateStats' : 'updateStatistics'
    },

    onRender: function(){
        var that = this;
        this.ui.tooltip.tooltip();
        this.ui.peditable.editable({
            type: 'text',
            mode: 'inline',
            pk: 1,
            name: 'installationID',
            ajaxOptions: {authWrap: true},
            url: '/api/pricing/license/installation_id',
            validate: function(newValue) {
                if (!newValue.trim()) {
                    utils.notifyWindow('Empty installation ID is not allowed.');
                    return ' ';  // return string - means validation not passed
                }
                if (newValue.trim().length > 32){
                    utils.notifyWindow('Maximum length is 32 symbols');
                    return ' ';
                }
            },
            success: function(response, newValue) {
                that.model.set(_.has(response, 'data') ? response.data : response);
                utils.notifyWindow('New instalattion ID "' + newValue + '" is saved',
                                   'success');
            },
            error: function(response, newValue) {
                that.model.set({name: newValue});
                utils.notifyWindow(response);
            },
        });
    }
});

export const ProfileEditView = Backbone.Marionette.ItemView.extend({
    template: userEditTpl,

    initialize: function(options){
        this.timezones = options.timezones;
    },

    ui: {
        'first_name'       : 'input#firstname',
        'last_name'        : 'input#lastname',
        'middle_initials'  : 'input#middle_initials',
        'password'         : 'input#password',
        'password_again'   : 'input#password-again',
        'email'            : 'input#email',
        'timezone'         : 'select#timezone',
        'save'             : 'button#template-save-btn',
        'back'             : 'button#template-back-btn',
        'editBtn'          : '#template-edit-btn',
        'input'            : 'input',
    },

    events: {
        'click @ui.save'       : 'onSave',
        'click @ui.back'       : 'toggleShowEditTemplate',
        'click @ui.editBtn'    : 'toggleShowEditTemplate',
        'change @ui.input'     : 'toggleShowSaveButton',
        'keyup @ui.input'      : 'toggleShowSaveButton',
        'change @ui.timezone'  : 'toggleShowSaveButton',
        'focus @ui.input'      : 'removeError',
    },

    templateHelpers: function(){
        return {
            edit: this.model.in_edit,
            first_name: this.model.get('first_name'),
            last_name: this.model.get('last_name'),
            middle_initials: this.model.get('middle_initials'),
            email: this.model.get('email'),
            timezone: this.model.get('timezone'),
            timezones: this.timezones,
        };
    },

    onRender: function(){
        this.ui.first_name.val(this.model.get('first_name'));
        this.ui.last_name.val(this.model.get('last_name'));
        this.ui.middle_initials.val(this.model.get('middle_initials'));
        this.ui.email.val(this.model.get('email'));
        this.ui.timezone.val(this.model.get('timezone'));
        this.ui.timezone.selectpicker({ size: 7 });
    },

    isEqual: function(){
        let oldData = {
            'first_name'      : this.model.get('first_name'),
            'last_name'       : this.model.get('last_name'),
            'middle_initials' : this.model.get('middle_initials'),
            'email'           : this.model.get('email'),
            'password'        : '',
            'password_again'  : '',
            'timezone'        : this.model.get('timezone').split(' (', 1)[0],
        },
        newData = {
            'first_name'      : this.ui.first_name.val(),
            'last_name'       : this.ui.last_name.val(),
            'middle_initials' : this.ui.middle_initials.val(),
            'email'           : this.ui.email.val(),
            'password'        : this.ui.password.val(),
            'password_again'  : this.ui.password_again.val(),
            'timezone'        : this.ui.timezone.val().split(' (', 1)[0],
        };

        return _.isEqual(oldData, newData);
    },

    toggleShowSaveButton(){
        if (this.isEqual()){
            this.ui.save.hide();
        } else {
            this.ui.save.show();
        }
    },

    toggleShowEditTemplate: function(){
        this.model.in_edit = !this.model.in_edit;
        this.render();
    },

    removeError: function(evt){ utils.removeError($(evt.target)); },

    onSave: function(){
        var firtsName = this.ui.first_name.val(),
            lastName = this.ui.last_name.val(),
            middleInitials = this.ui.middle_initials.val(),
            spaces = /\s/g,
            numbers = /\d/g,
            symbols = /[!"#$%&'()*+,\-.\/\\:;<=>?@[\]^_`{\|}~]/g,
            pattern = /^("\S+"|[a-z0-9_\.+-]+)@(([a-z0-9-]+\.)+[a-z0-9-]+|\[[a-f0-9:\.]+\])$/i;

        this.ui.first_name
            .val(firtsName.replace(symbols, '').replace(spaces, '').replace(numbers, ''));
        this.ui.last_name
            .val(lastName.replace(symbols, '').replace(spaces, '').replace(numbers, ''));
        this.ui.middle_initials
            .val(middleInitials.replace(symbols, '').replace(spaces, '').replace(numbers, ''));

        var data = {
                'first_name': this.ui.first_name.val(),
                'last_name': this.ui.last_name.val(),
                'middle_initials': this.ui.middle_initials.val(),
                'email': this.ui.email.val(),
                'timezone': this.ui.timezone.val(),
            };

        if (data.email === '') {
            utils.scrollTo(this.ui.email);
            utils.notifyInline('Empty E-mail', this.ui.email);
            return;
        } else if (!pattern.test(data.email)) {
            utils.scrollTo(this.ui.email);
            utils.notifyInline('E-mail must be correct', this.ui.email);
            return;
        }
        if (this.ui.password.val() !== this.ui.password_again.val()) {
            utils.scrollTo(this.ui.password);
            this.ui.password.addClass('error');
            utils.notifyInline("Passwords don't match", this.ui.password_again);
            return;
        }
        if (this.ui.password.val())  // update only if specified
            data.password = this.ui.password.val();

        this.model.save(data, {wait: true, patch: true, context: this})
            .fail(utils.notifyWindow)
            .done(function(){
                this.model.in_edit = false;
                this.render();
                utils.notifyWindow('Profile changed successfully', 'success');
            });
    }
});

export const SettingsLayout = Marionette.LayoutView.extend({
    template: settingsLayoutTpl,
    regions: {
        main: 'div#details_content'
    },

    ui: {
        tabButton : 'ul.nav-sidebar li',
        general   : 'li.general'
    },

    templateHelpers: function(){ return {user: App.currentUser}; },
    onBeforeShow: function(){ utils.preloader.show(); },
    onShow: function(){ utils.preloader.hide(); },

    onRender: function(){
        var that = this,
            tabs = that.ui.tabButton,
            href = window.location.hash.split('/')[1];

        utils.preloader.hide();

        _.each(tabs, function(item){
            if (item.className === href) {
                $(item).addClass('active');
            } else if (!href) {
                that.ui.general.addClass('active');
            } else {
                $(item).removeClass('active');
            }
        });
    }
});
