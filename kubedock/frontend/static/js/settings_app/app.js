define(['marionette', 'utils'],
       function (Marionette, utils) {

    var SettingsApp = new Marionette.Application({
        regions: {
            contents: '#contents'
        }
    });

    SettingsApp.module('Data', function(Data, App, Backbone, Marionette, $, _){

        Data.CurrentUserModel = utils.BaseModel.extend({
            url: function(){ return '/api/users/editself' }
        });

        Data.PermissionModel = utils.BaseModel.extend({
            urlRoot: '/api/settings/permissions'
        });

        Data.PermissionsCollection = utils.BaseCollection.extend({
            url: '/api/settings/permissions',
            model: Data.PermissionModel
        });

        Data.NotificationModel = utils.BaseModel.extend({
            urlRoot: '/api/settings/notifications'
        });

        Data.NotificationsCollection = utils.BaseCollection.extend({
            url: '/api/settings/notifications',
            model: Data.NotificationModel
        });

    });


    SettingsApp.module('Views', function(Views, App, Backbone, Marionette, $, _){

        Views.GeneralView = Marionette.CompositeView.extend({
            template: '#general-settings-template',

            ui: {
                'timezone': '#timezone'
            },

            events: {
                'click [type="submit"]': 'submitSettings'
            },

            onRender: function(){
                var that = this;
                this.ui.timezone.typeahead({
                    autoSelect: false,
                    source: function(query, process){
                        $.ajax({
                            url: '/api/settings/timezone',
                            data: {'s': that.ui.timezone.val()},
                            cache: false,
                            success: function(responce){
                                process(responce.data);
                            }
                        })
                    }
                });
            },

            submitSettings: function(){
                var data = {
                    timezone: this.ui.timezone.val()
                };
                $.ajax({
                    url: '/api/settings/timezone',
                    dataType: 'JSON',
                    data: data,
                    type: 'PUT',
                    cache: false,
                    success: function(rs){
                        if(rs.status == 'OK')
                            $.notify('Settings changed successfully', {
                                autoHideDelay: 10000,
                                globalPosition: 'top center',
                                className: 'success'
                        });
                    }
                })

            }
        });

        Views.NotificationCreateView = Backbone.Marionette.ItemView.extend({
            template: '#notification-create-template',

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
                App.router.navigate('/notifications/', {trigger: true});
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
                        App.router.navigate('/notifications', {trigger: true})
                    }
                });
            },

            onSelectEvent: function(){
                var curEventKeys = eventsKeysList[this.ui.event.val()];
                this.ui.event_keys.html(curEventKeys.join('<br/>'));
            }
        });

        Views.NotificationEditView = Views.NotificationCreateView.extend({

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
                        App.router.navigate('/notifications', {trigger: true})
                    }
                });
            }

        });

        Views.NotificationItemView = Marionette.ItemView.extend({
            template: '#notification-item-template',

            events: {
                'click span': 'editTemplate'
            },

            onRender: function(){
            },

            editTemplate: function(){
                App.router.navigate('/notifications/edit/' + this.model.id + '/', {trigger: true});
            }
        });

        Views.NotificationsView = Marionette.CompositeView.extend({
            template: '#notifications-settings-template',
            childViewContainer: '#notification-templates',
            childView: Views.NotificationItemView
        });
        /* Public IPs Views */
        Views.PublicIPsView = Marionette.CompositeView.extend({
            template: '#publicIPs-template',
        });

        /* Persistent volumes Views */
        Views.PersistentVolumesView = Marionette.CompositeView.extend({
            template: '#persistent-volumes-template',
        });
        /* Profile edit volumes Views */
        Views.ProfileEditView = Backbone.Marionette.ItemView.extend({
            template: '#user-edit-template',

            ui: {
                'first_name'      : 'input#firstname',
                'last_name'       : 'input#lastname',
                'middle_initials' : 'input#middle_initials',
                'password'        : 'input#password',
                'password_again'  : 'input#password-again',
                'email'           : 'input#email',
                'save'            : 'button#template-save-btn',
                'back'            : 'button#template-back-btn',
                'generalBtn'      : '#general-btn',
            },

            events: {
                'click @ui.back'       : 'back',
                'click @ui.save'       : 'onSave',
                'click @ui.generalBtn' : 'back',
            },

            onRender: function(){
                this.ui.first_name.val(this.model.get('first_name'));
                this.ui.last_name.val(this.model.get('last_name'));
                this.ui.middle_initials.val(this.model.get('middle_initials'));
                this.ui.email.val(this.model.get('email'));
            },

            back: function(){
                App.router.navigate('/', {trigger: true});
            },

            onSave: function(){
                var data = {
                    'first_name': this.ui.first_name.val(),
                    'last_name': this.ui.last_name.val(),
                    'middle_initials': this.ui.middle_initials.val(),
                    'email': this.ui.email.val()
                };

                pass1 = this.ui.password.val();
                pass2 = this.ui.password_again.val();
                // temp validation
                if (pass1 != '') {
                    if (pass1 != pass2) {
                        alert("Passwords are not equal");
                        return
                    }
                    data.password = pass1
                }

                this.model.set(data);

                this.model.save(undefined, {
                    wait: true,
                    success: function(){
                        App.router.navigate('', {trigger: true})
                    }
                });
            }
        });

        Views.PermissionItemView = Marionette.ItemView.extend({
            template: '#permission-item-template',
            tagName: 'tr',

            onRender: function(){
                console.log(this.model)
            }
        });

        Views.PermissionsListView = Marionette.CompositeView.extend({
            template: '#permissions-template',
            childView: Views.PermissionItemView,
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
                    dataType: 'JSON',
                    type: 'PUT',
                    data: {'allow': checked},
                    success: function(rs){
                        $.notify('Permission changed successfully', {
                            autoHideDelay: 10000,
                            globalPosition: 'top right',
                            className: 'success'
                        });
                    }
                });
            }
        });

        Views.SettingsLayout = Marionette.LayoutView.extend({
            template: '#settings-layout-template',
            regions: {
                main: 'div#details_content'
            },
            ui: {
                profileBtn           : '#profile-btn',
                generalBtn           : '#general-btn',
                publicIPsBtn         : '#publicIPs-btn',
                permissionsBtn       : '#permissions-btn',
                notificationsBtn     : '#notifications-btn',
                persistentVolumesBtn : '#persistent-volumes-btn',
            },
            events: {
                'click @ui.generalBtn'           : 'redirectToGeneral',
                'click @ui.profileBtn'           : 'redirectToProfile',
                'click @ui.permissionsBtn'       : 'redirectToPermissions',
                'click @ui.publicIPsBtn'         : 'redirectToPublicIPs',
                'click @ui.notificationsBtn'     : 'redirectToNotifications',
                'click @ui.persistentVolumesBtn' : 'redirectToPersistentVolumes',
            },
            redirectToGeneral: function(evt){
                App.router.navigate('/', {trigger: true});
            },
            redirectToProfile: function(evt){
                App.router.navigate('/profile/', {trigger: true});
            },
            redirectToPermissions: function(evt){
                App.router.navigate('/permissions/', {trigger: true});
            },
            redirectToNotifications: function(evt){
                App.router.navigate('/notifications/', {trigger: true});
            },
            redirectToPublicIPs: function(evt){
                App.router.navigate('/publicIPs/', {trigger: true});
            },
            redirectToPersistentVolumes: function(){
                App.router.navigate('/persistent-volumes/', {trigger: true});
            }
        });
    });

    SettingsApp.module('SettingsCRUD', function(
        SettingsCRUD, App, Backbone, Marionette, $, _){

        SettingsCRUD.Controller = Marionette.Controller.extend({
            showSettings: function(){
                var layout_view = new App.Views.SettingsLayout();
                this.listenTo(layout_view, 'show', function(){
                    layout_view.main.show();
                });
                App.contents.show(layout_view);
            },

            showPermissions: function(){
                var layout_view = new App.Views.SettingsLayout();
                var permissions_view = new App.Views.PermissionsListView({
                    collection: SettingsApp.Data.permissions
                });
                this.listenTo(layout_view, 'show', function(){
                    layout_view.main.show(permissions_view);
                });
                App.contents.show(layout_view);
            },

            showNotifications: function(){
                var layout_view = new App.Views.SettingsLayout();
                var notifications_view = new App.Views.NotificationsView({
                    collection: SettingsApp.Data.notifications
                });
                this.listenTo(layout_view, 'show', function(){
                    layout_view.main.show(notifications_view);
                });
                App.contents.show(layout_view);
            },

            addNotifications: function(){
                var layout_view = new App.Views.SettingsLayout();
                var notifications_create_view = new App.Views.NotificationCreateView();
                this.listenTo(layout_view, 'show', function(){
                    layout_view.main.show(notifications_create_view);
                });
                App.contents.show(layout_view);
            },

            editNotifications: function(nid){
                var layout_view = new App.Views.SettingsLayout();
                var notifications_edit_view = new App.Views.NotificationEditView({
                    model: SettingsApp.Data.notifications.get(parseInt(nid))
                });
                this.listenTo(layout_view, 'show', function(){
                    layout_view.main.show(notifications_edit_view);
                });
                App.contents.show(layout_view);
            },

            editProfile: function(){
                var layout_view = new App.Views.SettingsLayout();
                var profile_edit_view = new App.Views.ProfileEditView({
                    model: SettingsApp.Data.this_user
                });
                this.listenTo(layout_view, 'show', function(){
                    layout_view.main.show(profile_edit_view);
                });
                App.contents.show(layout_view);
            },

            showGeneral: function(){
                var layout_view = new App.Views.SettingsLayout();
                var general_view = new App.Views.GeneralView();
                this.listenTo(layout_view, 'show', function(){
                    layout_view.main.show(general_view);
                });
                App.contents.show(layout_view);
            },

            showIPs: function(){
                var layout_view = new App.Views.SettingsLayout();
                var public_ips_view = new App.Views.PublicIPsView();
                this.listenTo(layout_view, 'show', function(){
                    layout_view.main.show(public_ips_view);
                });
                App.contents.show(layout_view);
            },

            showPersistentVolumes: function(){
                var layout_view = new App.Views.SettingsLayout();
                var persistent_volumes_view = new App.Views.PersistentVolumesView();
                this.listenTo(layout_view, 'show', function(){
                    layout_view.main.show(persistent_volumes_view);
                });
                App.contents.show(layout_view);
            },
        });

        SettingsCRUD.addInitializer(function(){
            var controller = new SettingsCRUD.Controller();
            App.router = new Marionette.AppRouter({
                controller: controller,
                appRoutes: {
                    ''                        : 'showGeneral',
                    'general/'                : 'showGeneral',
                    'profile/'                : 'editProfile',
                    'publicIPs/'              : 'showIPs',
                    'permissions/'            : 'showPermissions',
                    'notifications/'          : 'showNotifications',
                    'notifications/add/'      : 'addNotifications',
                    'persistent-volumes/'     : 'showPersistentVolumes',
                    'notifications/edit/:id/' : 'editNotifications',
                }
            });
        });

    });

    SettingsApp.on('start', function(){
        if (Backbone.history) {
            Backbone.history.start({root: '/settings/', pushState: true});
        }
    });

    return SettingsApp;
});
