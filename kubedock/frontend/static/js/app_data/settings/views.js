define(['app_data/app', 'marionette',
        'tpl!app_data/settings/templates/settings_layout.tpl',
        'tpl!app_data/settings/templates/permissions.tpl',
        'tpl!app_data/settings/templates/permission_item.tpl',
        'tpl!app_data/settings/templates/user_edit.tpl',
        'tpl!app_data/settings/templates/notification_settings.tpl',
        'tpl!app_data/settings/templates/notification_item.tpl',
        'tpl!app_data/settings/templates/notification_create.tpl',
        'tpl!app_data/settings/templates/general_settings.tpl',
        'tpl!app_data/settings/templates/general_settings_item.tpl',
        'tpl!app_data/settings/templates/license.tpl',
        'app_data/utils', 'bootstrap', 'bootstrap-editable', 'selectpicker'],
       function(App, Marionette,
                settingsLayoutTpl, permissionsTpl, permissionItemTpl,
                userEditTpl, notificationSettingsTpl, notificationItemTpl,
                notificationCreateTpl, generalSettingsTpl, generalSettingsItemTpl,
                licenseTpl, utils){

    var views = {},
        defaultHideDelay = 4000;

    views.GeneralItemView = Marionette.ItemView.extend({
        template: generalSettingsItemTpl,
        tagName: 'div',
        className: 'link-wrapper',

        ui: {
            itemField: 'input.settings-item'
        },

        events: {
            'change @ui.itemField': 'fieldChange'
        },

        fieldChange: function(evt){
            evt.stopPropagation();
            this.model.set({value: $(evt.target).val()});
        }
    });

    views.GeneralView = Marionette.CompositeView.extend({
        template: generalSettingsTpl,
        childView: views.GeneralItemView,
        childViewContainer: 'div#settings-list',

        events: {
            'click [type="submit"]': 'submitSettings'
        },

        submitSettings: function(){
            var changed = this.collection.filter(function(m){ return m.hasChanged('value') });
            if (changed.length) {
                _.each(changed, function(m){
                    m.save(null, {wait: true})
                        .fail(utils.notifyWindow)
                        .done(function(){
                            utils.notifyWindow(m.get('label') + ' changed successfully',
                                               'success');
                        });
                });
            }
            else {
                utils.notifyWindow('Data has not been changed.', 'success');
            }
        }
    });

    views.LicenseView = Marionette.ItemView.extend({
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

        checkLimits: function(){
            var results,
                that = this,
                data = this.model.get('data');

            _.each(data, function(item){
                !that.comparison(item[0],item[1])
                    ? item[3] = true
                    : item[3] = false;
            });

            results = _.any(data, function(item){ return !that.comparison(item[0],item[1])});
            this.model.set('attention', results);
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
                    $.notify('Statistics has updated', {
                        autoHideDelay: 5000,
                        clickToHide: true,
                        globalPosition: 'bottom left',
                        className: 'success',
                    });
                    that.render();
                },
                error: function(){
                    that.ui.updateStats.removeClass('start-atimation');
                    console.log('Could not fetch statistics');
                }
            });
        },

        comparison: function(a, b){
            if (a == 'unlimited' || a == 0) a = Infinity;
            return a > b ? true : false;
        },

        ui: {
            peditable : '.peditable',
            updateStats: '.check-for-update'
        },

        events: {
            'click @ui.updateStats': 'updateStatistics'
        },

        onRender: function(){
            var that = this;
            this.ui.peditable.editable({
                type: 'text',
                mode: 'inline',
                pk: 1,
                name: 'installationID',
                url: '/api/pricing/license/installation_id',
                validate: function(newValue) {
                    if (!newValue.trim()) {
                        utils.notifyWindow('Empty installation ID is not allowed.');
                        return ' ';  // return string - means validation not passed
                    }
                },
                success: function(response, newValue) {
                    that.model.set({name: newValue});
                    utils.notifyWindow('New instalattion ID "' + newValue + '" is saved',
                                       'success');
                },
                error: function(response, newValue) {
                    that.model.set({name: newValue});
                    console.log(response);
                    utils.notifyWindow(response.responseJSON.data);
                },
            });
        }
    });

    views.NotificationCreateView = Backbone.Marionette.ItemView.extend({
        template: notificationCreateTpl,

        ui: {
            'label'      : 'label[for="id_event"]',
            'event'      : 'select#id_event',
            'text_plain' : 'textarea#id_text_plain',
            'text_html'  : 'textarea#id_text_html',
            'as_html'    : 'input#id_as_html',
            'event_keys' : '#event_keys',
            'save'       : 'button#template-add-btn',
            'back'       : 'button#template-back-btn'
        },

        events: {
            'click @ui.save'         : 'onSave',
            'click @ui.back'         : 'back',
            'change select#id_event' : 'onSelectEvent'
        },

        onRender: function() {
            var curEventKeys = eventsKeysList[this.ui.event.val()];
            this.ui.event_keys.html(curEventKeys.join('<br/>'));
            this.ui.event.show();
            this.ui.label.text("Event");
        },

        back: function(){
            App.navigate('/notifications/', {trigger: true});
        },

        onSave: function(){
            // temp validation
            App.Data.templates.create({
                'event': this.ui.event.val(),
                'text_plain': this.ui.text_plain.val(),
                'text_html': this.ui.text_html.val(),
                'as_html': this.ui.as_html.prop('checked')
            }, {
                wait: true,
                success: function(){
                    App.navigate('/notifications', {trigger: true})
                }
            });
        },

        onSelectEvent: function(){
            var curEventKeys = eventsKeysList[this.ui.event.val()];
            this.ui.event_keys.html(curEventKeys.join('<br/>'));
        }
    });

    views.NotificationEditView = views.NotificationCreateView.extend({
        onRender: function(){
            var curEventKeys = eventsKeysList[this.ui.event.val()];
            this.ui.event_keys.html(curEventKeys.join('<br/>'));
            this.ui.event.hide();
            this.ui.label.text("Event: " + this.model.get('event').name);
            this.ui.text_plain.val(this.model.get('text_plain'));
            this.ui.text_html.val(this.model.get('text_html'));
            this.ui.as_html.prop('checked', this.model.get('as_html'));
        },

        onSave: function(){
            // temp validation
            var data = {
                'event': this.ui.event.val(),
                'text_plain': this.ui.text_plain.text(),
                'text_html': this.ui.text_html.text(),
                'as_html': this.ui.as_html.prop('checked')
            };

            this.model.set(data);

            this.model.save(undefined, {
                wait: true,
                success: function(){
                    App.navigate('/notifications', {trigger: true})
                }
            });
        }
    });

    views.NotificationItemView = Marionette.ItemView.extend({
        template: notificationItemTpl,

        events: {
            'click span': 'editTemplate'
        },

        editTemplate: function(){
            App.navigate('/notifications/edit/' + this.model.id + '/', {trigger: true});
        }
    });

    views.NotificationsView = Marionette.CompositeView.extend({
        template: notificationSettingsTpl,
        childViewContainer: '#notification-templates',
        childView: views.NotificationItemView
    });

    /* Profile edit volumes Views */
    views.ProfileEditView = Backbone.Marionette.ItemView.extend({
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
            /*'deleteBtn'        : '#template-remove-btn'*/
        },

        events: {
            'click @ui.back'       : 'back',
            'click @ui.save'       : 'onSave',
            'click @ui.editBtn'    : 'editTemplate',
            'change @ui.input'     : 'changeValue',
            'change @ui.timezone'  : 'changeValue',
            'focus @ui.input'      : 'removeError',
            /*'click @ui.deleteBtn'  : 'deleteProfile',*/
        },

        templateHelpers: function(){
            var timezones = this.timezones;
            return {
                edit: this.model.in_edit,
                first_name: this.model.get('first_name'),
                last_name: this.model.get('last_name'),
                middle_initials: this.model.get('middle_initials'),
                email: this.model.get('email'),
                timezone: this.model.get('timezone'),
                timezones : timezones
            }
        },

        onRender: function(){
            var that = this;
            this.ui.first_name.val(this.model.get('first_name'));
            this.ui.last_name.val(this.model.get('last_name'));
            this.ui.middle_initials.val(this.model.get('middle_initials'));
            this.ui.email.val(this.model.get('email'));
            this.ui.timezone.val(this.model.get('timezone'));
            this.ui.timezone.selectpicker();
        },

        changeValue: function(){
            var equal,
            oldData = {
                'first_name'      : this.model.get('first_name'),
                'last_name'       : this.model.get('last_name'),
                'middle_initials' : this.model.get('middle_initials'),
                'email'           : this.model.get('email'),
                'password'        : '',
                'timezone'        : this.model.get('timezone').split(' (', 1)[0],
            },
            newData = {
                'first_name'      : this.ui.first_name.val(),
                'last_name'       : this.ui.last_name.val(),
                'middle_initials' : this.ui.middle_initials.val(),
                'email'           : this.ui.email.val(),
                'password'        : this.ui.password.val(),
                'timezone'        : this.ui.timezone.val().split(' (', 1)[0],
            };

            equal = _.isEqual(oldData, newData)
            equal === false ? this.ui.save.show() : this.ui.save.hide();
        },

        back: function(){
            this.model.in_edit = false;
            this.render();
        },

        editTemplate: function(){
            this.model.in_edit = true;
            this.render();
        },

        /*deleteProfile: function(){
            var that = this;
            utils.modalDialogDelete({
                title: "Terminate account?",
                body: "Are you sure you want to terminate your account ?",
                small: true,
                show: true,
                footer: {
                    buttonOk: function(){
                        that.model.destroy(undefined, {
                            wait: true,
                            success: function(){
                                that.model.in_edit = false;
                                that.render();
                            },
                        })
                    },
                    buttonCancel: true
                }
            });
        },*/

        removeError: function(evt){
            var target = $(evt.target);
            if (target.hasClass('error')) target.removeClass('error');
        },

        onSave: function(){
            var data = {
                    'first_name': this.ui.first_name.val(),
                    'last_name': this.ui.last_name.val(),
                    'middle_initials': this.ui.middle_initials.val(),
                    'email': this.ui.email.val(),
                    'timezone': this.ui.timezone.val(),
                },
                pattern = /^("\S+"|[a-z0-9_\.+-]+)@(([a-z0-9-]+\.)+[a-z0-9-]+|\[[a-f0-9:\.]+\])$/i;

            if (data.email == '') {
                utils.scrollTo(this.ui.email);
                this.ui.email.addClass('error');
                this.ui.email.notify("empty E-mail");
                return
            } else if (!pattern.test(data.email)) {
                utils.scrollTo(this.ui.email);
                this.ui.email.addClass('error');
                this.ui.email.notify("E-mail must be correct");
                return
            }
            if (this.ui.password.val() !== this.ui.password_again.val()) {
                utils.scrollTo(this.ui.password);
                this.ui.password.addClass('error');
                this.ui.password_again.addClass('error');
                this.ui.password_again.notify("passwords don't match");
                return
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

    views.PermissionItemView = Marionette.ItemView.extend({
        template: permissionItemTpl,
        tagName: 'tr',
    });

    views.PermissionsListView = Marionette.CompositeView.extend({
        template: permissionsTpl,
        childView: views.PermissionItemView,
        childViewContainer: "tbody",

        ui: {
            permTable: '#permissions-table',
            permToggle: '.perm-toggle'
        },

        events: {
            'change input.perm-toggle': 'togglePerm'
        },

        onRender: function(){
            var that = this,
                tr = this.ui.permTable.find('thead').append('<tr>')
                    .find('tr').append('<th>');
            $.each(roles, function(id, itm){
                tr.append($('<th>').text(itm.rolename));
            });
        },

        togglePerm: function(evt){
            var $el = $(evt.target),
                pid = $el.data('pid'),
                checked = $el.is(':checked');
            $.ajax({
                url: '/api/settings/permissions/' + pid,
                type: 'PUT',
                data: {'allow': checked},
                success: function(rs){
                    utils.notifyWindow('Permission changed successfully', 'success');
                },
                error: utils.notifyWindow,
            });
        }
    });

    views.SettingsLayout = Marionette.LayoutView.extend({
        template: settingsLayoutTpl,
        regions: {
            nav: 'div#nav',
            main: 'div#details_content'
        },

        ui: {
            tabButton : 'ul.nav-sidebar li',
            general   : 'li.general'
        },

        events: {
            'click @ui.tabButton' : 'changeTab'
        },

        onBeforeShow: function(){
            utils.preloader.show();
        },

        onShow: function(){
            utils.preloader.hide();
        },

        changeTab: function (evt) {
            evt.preventDefault();
            var tgt = $(evt.target);
            if (tgt.hasClass('general')) App.navigate('settings/general', {trigger: true});
            if (tgt.hasClass('license')) App.navigate('settings/license', {trigger: true});
            else if (tgt.hasClass('profile')) App.navigate('settings/profile', {trigger: true});
            else if (tgt.hasClass('permissions')) App.navigate('settings/permissions', {trigger: true});
            else if (tgt.hasClass('notifications')) App.navigate('settings/notifications', {trigger: true});
        },

        onRender: function(){
            var href = window.location.pathname.split('/'),
                tabs = this.ui.tabButton,
                that = this;

            $('#page-preloader').hide();

            href = href[href.length - 2];

            _.each(tabs, function(item){
                if (item.className == href) {
                    $(item).addClass('active');
                } else if (href == 'settings') {
                    that.ui.general.addClass('active');
                }
                else {
                    $(item).removeClass('active')
                }
            });
        }
    });

    return views;
});
