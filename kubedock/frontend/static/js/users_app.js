define(['marionette', 'paginator'],
       function (Marionette, PageableCollection) {

    var UsersApp = new Marionette.Application({
        regions: {
            contents: '#contents'
        }
    });

    UsersApp.module('Data', function(Data, App, Backbone, Marionette, $, _){

        var unwrapper = function(response) {
            if (response.hasOwnProperty('data'))
                return response['data'];
            return response;
        };

        Data.UserModel = Backbone.Model.extend({
            urlRoot: '/api/users/',
            parse: unwrapper
        });
        Data.UsersCollection = Backbone.Collection.extend({
            url: '/api/users/',
            model: Data.UserModel
        });

        Data.UserActivitiesModel = Backbone.Model.extend({
            urlRoot: '/api/users/a/:id/',
            parse: unwrapper
        });

        Data.UsersPageableCollection = PageableCollection.extend({
            url: '/api/users/',
            model: Data.UserModel,
            parse: unwrapper,
            mode: 'client',
            state: {
                pageSize: 5
            }
        });

        Data.ActivitiesCollection = PageableCollection.extend({
            url: '/api/users/a/:id/',
            model: Data.UserActivitiesModel,
            parse: unwrapper,
            mode: 'client',
            state: {
                pageSize: 15
            }
        });
    });

    UsersApp.module('Views', function(Views, App, Backbone, Marionette, $, _){

        //=================Copy from app.js ====================================
        Views.PaginatorView = Backbone.Marionette.ItemView.extend({
            template: '#paginator-template',
            initialize: function(options) {
                this.model = new Backbone.Model({
                    v: options.view,
                    c: options.view.collection
                });
                this.listenTo(this.model.get('c'), 'remove', function(){
                    this.render();
                });
            },
            events: {
                'click li.pseudo-link': 'paginateIt'
            },
            paginateIt: function(evt){
                evt.stopPropagation();
                var tgt = $(evt.target);
                if (tgt.hasClass('paginatorFirst')) this.model.get('c').getFirstPage();
                else if (tgt.hasClass('paginatorPrev')) this.model.get('c').getPreviousPage();
                else if (tgt.hasClass('paginatorNext')) this.model.get('c').getNextPage();
                else if (tgt.hasClass('paginatorLast')) this.model.get('c').getLastPage();
                this.render();
            }
        });
        //======================================================================

        Views.UserItem = Backbone.Marionette.ItemView.extend({
            template: '#user-item-template',
            tagName: 'tr',

            events: {
                'click button#deleteUser': 'deleteUser_btn',
                'click button#editUser' : 'editUser_btn'
            },

            deleteUser_btn: function(){
                this.model.destroy({wait: true});
            },

            editUser_btn: function(){
                App.router.navigate('/edit/' + this.model.id + '/', {trigger: true});
            }

        });

        Views.OnlineUserItem = Marionette.ItemView.extend({
            template: '#online-user-item-template',
            tagName: 'tr',
            events: {
                'click button#userActivityHistory': 'userActivityHistory_btn'
            },
            userActivityHistory_btn: function(){
                App.router.navigate('/online/' + this.model.id + '/', {trigger: true});
            }
        });

        Views.ActivityItem = Marionette.ItemView.extend({
            template: '#activity-item-template',
            tagName: 'tr'
        });

        Views.UsersListView = Backbone.Marionette.CompositeView.extend({
            template: '#users-list-template',
            childView: Views.UserItem,
            childViewContainer: "tbody",

            events: {
                'click button#create_user' : 'createUser'
            },

            createUser: function(){
                App.router.navigate('/create/', {trigger: true});
            }
        });

        Views.OnlineUsersListView = Marionette.CompositeView.extend({
            template: '#online-users-list-template',
            childView: Views.OnlineUserItem,
            childViewContainer: "tbody"
        });

        Views.UsersActivityView = Marionette.CompositeView.extend({
            template: '#users-activities-template',
            childView: Views.ActivityItem,
            childViewContainer: "tbody"
        });

        Views.UserCreateView = Backbone.Marionette.ItemView.extend({
            template: '#user-create-template',
            tagName: 'div',

            ui: {
                'username': 'input#username',
                'password': 'input#password',
                'password_again': 'input#password-again',
                'email': 'input#email',
                'description': 'input#description',
                'active_chkx': 'input#active-chkx',
                'role_select': 'select#role-select'
            },

            events: {
                'click button#user-add-btn': 'onSave'
            },

            onSave: function(){
                // temp validation
                if (!this.ui.password.val() || (this.ui.password.val() !== this.ui.password_again.val())) {
                    // set error messages to password fields
                    alert("empty password or don't match");
                    return false
                }

                App.Data.users.create({
                    'username': this.ui.username.val(),
                    'password': this.ui.password.val(),
                    'email': this.ui.email.val(),
                    'description': this.ui.description.val(),
                    'active': this.ui.active_chkx.prop('checked'),
                    'rolename': this.ui.role_select.val()
                }, {
                    wait: true,
                    success: function(){
                        App.router.navigate('/', {trigger: true})
                    },
                    error: function(){
                        alert('error while saving! Maybe some fields required.')
                    }
                });
            }

        });

        Views.UsersEditView = Views.UserCreateView.extend({     // inherit

            onRender: function(){
                console.log(this.model)
                this.ui.username.val(this.model.get('username'));
                this.ui.email.val(this.model.get('email'));
                this.ui.description.val(this.model.get('description'));
                this.ui.active_chkx.prop('checked', this.model.get('active'));
                this.ui.role_select.val(this.model.get('rolename'));
            },

            onSave: function(){
                // temp validation
                var data = {
                    'username': this.ui.username.val(),
                    'email': this.ui.email.val(),
                    'description': this.ui.description.val(),
                    'active': this.ui.active_chkx.prop('checked'),
                    'rolename': this.ui.role_select.val()
                };
                if(this.ui.password.val()){
                    if (!this.ui.password.val() || (this.ui.password.val() !== this.ui.password_again.val())) {
                        // set error messages to password fields
                        alert("empty password or don't match");
                        return false
                    }
                    data['password'] = this.ui.password.val();
                }
                if(!data.email){
                    alert('E-mail is required');
                    this.ui.email.focus();
                    return false;
                }
                if(!data.username){
                    alert('Username is required');
                    this.ui.username.focus();
                    return false;
                }
                if(!data.rolename){
                    alert('Username is required');
                    this.ui.role_select.focus();
                    return false;
                }


                this.model.set(data);

                this.model.save(undefined, {
                    wait: true,
                    success: function(){
                        App.router.navigate('/', {trigger: true})
                    },
                    error: function(){
                        alert('error while updating! Maybe some fields required.')
                    }
                });
            }

        });

        Views.UsersLayout = Marionette.LayoutView.extend({
            template: '#users-layout-template',
            regions: {
                main: 'div#main',
                pager: 'div#pager'
            }
        });
    });


    UsersApp.module('UsersCRUD', function(UsersCRUD, App, Backbone, Marionette, $, _){

        UsersCRUD.Controller = Marionette.Controller.extend({
            showOnlineUsers: function(){
                var layout_view = new App.Views.UsersLayout(),
                    t = this;
                $.ajax({
                    url: '/api/users/online/',
                    success: function(rs){
                        UsersApp.Data.users = new UsersApp.Data.UsersPageableCollection(rs.data);
                        var users_list_view = new App.Views.OnlineUsersListView({
                            collection: App.Data.users});
                        var user_list_pager = new App.Views.PaginatorView({
                            view: users_list_view});
                        t.listenTo(layout_view, 'show', function(){
                            layout_view.main.show(users_list_view);
                            layout_view.pager.show(user_list_pager);
                        });
                        App.contents.show(layout_view);
                    }
                });
            },
            showUserActivity: function(user_id){
                var layout_view = new App.Views.UsersLayout(),
                    t = this;

                $.ajax({
                    'url': '/api/users/a/' + user_id + '/',
                    success: function(rs){
                        UsersApp.Data.activities = new UsersApp.Data.ActivitiesCollection(rs.data);
                        var activities_view = new App.Views.UsersActivityView({
                            collection: UsersApp.Data.activities});
                        var activities_list_pager = new App.Views.PaginatorView({
                            view: activities_view});
                        t.listenTo(layout_view, 'show', function(){
                            layout_view.main.show(activities_view);
                            layout_view.pager.show(activities_list_pager);
                        });
                        App.contents.show(layout_view);
                    }
                });
            },
            showUsers: function(){
                var layout_view = new App.Views.UsersLayout(),
                    t = this;
                $.ajax({
                    url: '/api/users/',
                    success: function(rs){
                        var users_list_view = new App.Views.UsersListView({
                            collection: new App.Data.UsersPageableCollection(rs.data)});
                        var user_list_pager = new App.Views.PaginatorView({
                            view: users_list_view});
                        t.listenTo(layout_view, 'show', function(){
                            layout_view.main.show(users_list_view);
                            layout_view.pager.show(user_list_pager);
                        });
                        App.contents.show(layout_view);
                    }
                });
            },

            showCreateUser: function(){
                var layout_view = new App.Views.UsersLayout();
                var user_create_view = new App.Views.UserCreateView();

                this.listenTo(layout_view, 'show', function(){
                    layout_view.main.show(user_create_view);
                });

                App.contents.show(layout_view);
            },

            showEditUser: function(user_id){
                var layout_view = new App.Views.UsersLayout();
                var user_edit_view = new App.Views.UsersEditView({
                    model: App.Data.users.get(parseInt(user_id))
                });
                this.listenTo(layout_view, 'show', function () {
                    layout_view.main.show(user_edit_view);
                    $('#pager').hide();
                    $('#user-header h2').text('Edit');

                });
                App.contents.show(layout_view);
            }
        });

        UsersCRUD.addInitializer(function(){
            var controller = new UsersCRUD.Controller();
            App.router = new Marionette.AppRouter({
                controller: controller,
                appRoutes: {
                    'online/': 'showOnlineUsers',
                    'online/:id/': 'showUserActivity',
                    '': 'showUsers',
                    'create/': 'showCreateUser',
                    'edit/:id/': 'showEditUser'
                }
            });
        });

    });

    UsersApp.on('start', function(){
        if (Backbone.history) {
            Backbone.history.start({root: '/users/', pushState: true});
        }
    });
    return UsersApp;
});
