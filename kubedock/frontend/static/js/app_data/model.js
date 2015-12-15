define(['app_data/app', 'backbone', 'app_data/utils',
        'backbone-paginator', 'backbone-associations', 'notify'], function(App, Backbone, utils){
    'use strict';

    var data = {},
        unwrapper = function(response) {
            var data = response.hasOwnProperty('data') ? response['data'] : response
            if (response.hasOwnProperty('status')) {
                if(response.status == 'error' || response.status == 'warning') {
                    var err = data;
                    if(typeof data !== 'string') err = JSON.stringify(data);
                    $.notify(err, {
                        autoHideDelay: 5000,
                        globalPosition: 'top center',
                        className: response.status == 'error' ? 'danger' : 'warning'
                    });
                }
            }
            return data;
        };

    data.Container = Backbone.Model.extend({
        idAttribute: 'name',
        defaults: function(){
            return {
                image: null,
                name: _.random(Math.pow(36, 8)).toString(36),
                workingDir: null,
                ports: [],
                volumeMounts: [],
                env: [],
                args: [],
                kubes: 1,
                terminationMessagePath: null,
                sourceUrl: null,
                logs: [],
                logsError: null,
            };
        },
        getPod: function(){
            return ((this.collection || {}).parents || [])[0];
        },
        checkForUpdate: function(){
            return $.ajax({
                url: this.getPod().url() + '/' + this.id + '/update',
                context: this,
            }).done(function(rs){ this.updateIsAvailable = rs.data; });
        },
        update: function(){
            return $.ajax({
                url: this.getPod().url() + '/' + this.id + '/update',
                type: 'POST',
                context: this,
            }).done(function(){ this.updateIsAvailable = undefined; });
        },
        getLogs: function(size){
            size = size || 100;
            return $.ajax({
                url: '/api/logs/container/' + this.get('name') + '?size=' + size,
                context: this,
                success: function(data){
                    var seriesByTime = _.indexBy(this.get('logs'), 'start');
                    _.each(data.data.reverse(), function(serie) {
                        var lines = serie.hits.reverse(),
                            oldSerie = seriesByTime[serie.start];
                        if (lines.length && oldSerie && oldSerie.hits.length) {
                            // if we have some logs, append only new lines
                            var first = lines[0],
                                index = _.sortedIndex(oldSerie.hits, first, 'time_nano');
                            lines.unshift.apply(lines, _.first(oldSerie.hits, index));
                        }
                    });
                    this.set('logs', data.data);
                    this.set('logsError', null);
                },
                error: function(xhr) {
                    var data = xhr.responseJSON;
                    if (data && data.data !== undefined)
                        this.set('logsError', data.data);
                },
            });
        },
    }, {  // Class Methods
        fromImage: function(image){
            var _data = _.clone(image instanceof data.Image ? image.attributes : image);
            _data.ports = _.map(_data.ports || [], function(port){
                return {
                    containerPort: port.number,
                    protocol: port.protocol,
                    hostPort: null,
                    isPublic: false
                };
            });
            _data.volumeMounts = _.map(_data.volumeMounts || [], function(vm){
                return {name: null, mountPath: vm};
            });
            return new this(_data);
        }
    });

    data.Pod = Backbone.AssociatedModel.extend({
        urlRoot: '/api/podapi/',
        relations: [{
              type: Backbone.Many,
              key: 'containers',
              relatedModel: data.Container,
        }],

        defaults: function(){
            return {
                name: 'Nameless',
                containers: [],
                volumes: [],
                replicas: 1,
                restartPolicy: "Always",
                node: null,
            };
        },

        parse: unwrapper,

        command: function(cmd, options){
            return this.save({command: cmd}, options);
        },

        // delete specified volumes from pod model, release Persistent Disks
        deleteVolumes: function(names){
            var volumes = this.get('volumes');
            this.set('volumes', _.filter(volumes, function(volume) {
                if (!_.contains(names, volume.name))
                    return true;  // leave this volume

                if (_.has(volume, 'persistentDisk')) {  // release PD
                    _.chain(this.persistentDrives || [])
                        .where({pdName: volume.persistentDisk.pdName})
                        .each(function(disk) { disk.used = false; });
                }
                return false;  // remove this volume
            }, this));
        },

        getKubes: function(){
            return this.get('containers').reduce(
                function(sum, c){ return sum + c.get('kubes'); }, 0);
        },

        recalcInfo: function(pkg) {
            var containers = this.get('containers'),
                volumes = this.get('volumes'),
                kube = _.findWhere(backendData.kubeTypes, {id: this.get('kube_type')}),
                kubePrice = _.findWhere(backendData.packageKubes,
                    {package_id: pkg.id, kube_id: kube.id}).kube_price,
                totalKubes = this.getKubes();

            this.limits = {
                cpu: (totalKubes * kube.cpu).toFixed(2) + ' ' + kube.cpu_units,
                ram: totalKubes * kube.memory + ' ' + kube.memory_units,
                hdd: totalKubes * kube.disk_space + ' ' + kube.disk_space_units,
            };

            var allPorts = _.flatten(containers.pluck('ports'), true),
                allPersistentVolumes = _.filter(_.pluck(volumes, 'persistentDisk')),
                total_size = _.reduce(allPersistentVolumes,
                    function(sum, v) { return sum + v.pdSize; }, 0);
            this.isPublic = _.any(_.pluck(allPorts, 'isPublic'));
            this.isPerSorage = !!allPersistentVolumes.length;

            var rawContainerPrices = containers.map(
                function(c) { return kubePrice * c.get('kubes'); });
            this.containerPrices = _.map(rawContainerPrices,
                function(price) { return utils.getFormattedPrice(pkg, price); });

            var totalPrice = _.reduce(rawContainerPrices,
                function(sum, p) { return sum + p; });
            if (this.isPublic)
                totalPrice += pkg.price_ip;
            if (this.isPerSorage)
                totalPrice += pkg.price_pstorage * total_size;
            this.totalPrice = utils.getFormattedPrice(pkg, totalPrice);
        },

        save: function(attrs, options){
            attrs || (attrs = _.clone(this.attributes));

            if (attrs.containers){
                attrs.containers = attrs.containers.toJSON();
                _.each(attrs.containers, function(container){
                    delete container.logs;
                    delete container.logsError;
                });
            }

            return Backbone.Model.prototype.save.call(this, attrs, options);
        },
    });

    data.Image = Backbone.Model.extend({

        defaults: {
            image: 'Imageless'
        },

        parse: unwrapper
    });

    data.Stat = Backbone.Model.extend({
        parse: unwrapper
    });

    data.PodCollection = Backbone.PageableCollection.extend({
        url: '/api/podapi/',
        model: data.Pod,
        parse: unwrapper,
        mode: 'client',
        state: {
            pageSize: 8
        },

        searchIn: function(val){
            return this.fullCollection.models.filter(function(i){
                return i.get('name').indexOf(val) === 0;
            });
        },
    });

    data.ImageCollection = Backbone.Collection.extend({
        url: '/api/images/',
        model: data.Image,
        parse: unwrapper
    });

    data.ImagePageableCollection = Backbone.PageableCollection.extend({
        url: '/api/images/',
        model: data.Image,
        parse: unwrapper,
        mode: 'infinite',
        state: {
            pageSize: 10
        }
    });

    data.NodeModel = Backbone.Model.extend({
        logsLimit: 5000,  // max number of line in logs
        urlRoot: '/api/nodes/',
        parse: unwrapper,
        defaults: function() {
            return {
                'ip': '',
                'logs': [],
                'logsError': null,
            };
        },
        getLogs: function(size){
            size = size || 100;
            return $.ajax({
                url: '/api/logs/node/' + this.get('hostname') + '?size=' + size,
                context: this,
                success: function(data) {
                    var oldLines = this.get('logs'),
                        lines = data.data.hits.reverse();

                    if (lines.length && oldLines.length) {
                        // if we have some logs, append only new lines
                        var first = lines[0],
                            index_to = _.sortedIndex(oldLines, first, 'time_nano'),
                            index_from = Math.max(0, index_to + lines.length - this.logsLimit);
                        lines.unshift.apply(lines, oldLines.slice(index_from, index_to));
                    }

                    this.set('logs', lines);
                    this.set('logsError', null);
                },
                error: function(xhr) {
                    var data = xhr.responseJSON;
                    if (data && data.data !== undefined)
                        this.set('logsError', data.data);
                },
                statusCode: null,
            });
        },
        appendLogs: function(data){
            this.set('install_log', this.get('install_log') + data + '\n');
            this.trigger('update_install_log');
        }
    });

    data.NodeCollection = Backbone.PageableCollection.extend({
        url: '/api/nodes/',
        model: data.NodeModel,
        parse: unwrapper,
        mode: 'client',
        state: {
            pageSize: 10
        }
    });

    data.StatsCollection = Backbone.Collection.extend({
        url: '/api/stats',
        model: data.Stat,
        parse: unwrapper
    });

    // TODO: Fixed code duplication by moving models from settings_app to a common file
    data.PersistentStorageModel = Backbone.Model.extend({
        defaults: {
            name   : 'Nameless',
            size   : 0,
            in_use : false,
            pod    : ''
        },
        parse: unwrapper
    });

    // TODO: Fixed code duplication by moving models from settings_app to a common file
    data.PersistentStorageCollection = Backbone.Collection.extend({
        url: '/api/pstorage',
        model: data.PersistentStorageModel,
        parse: unwrapper
    });

    data.UserModel = Backbone.Model.extend({
        urlRoot: '/api/users/full',
        parse: unwrapper,

        deleteUserConfirmDialog: function(options, text, force){
            var that = this;
            text = text || ('Are you sure want to delete user "' +
                            this.get('username') + '"?');

            utils.modalDialog({
                title: 'Delete ' + this.get('username') + '?',
                body: text,
                small: true,
                show: true,
                type: force ? 'deleteAnyway' : 'delete' ,
                footer: {
                    buttonOk: function(){ that.deleteUser(options, force); },
                    buttonCancel: true
                }
            });
        },
        deleteUser: function(options, force){
            var that = this;
            utils.preloader.show();
            return this.destroy(_.extend({
                wait:true,
                data: JSON.stringify({force: !!force}),
                contentType: 'application/json; charset=utf-8',
                statusCode: {400: null},  // prevent default error message
            }, options))
            .always(function(){ utils.preloader.hide(); })
            .fail(function(response){
                var responseData = response.responseJSON || {};
                if (!force && responseData.type === 'ResourceReleaseError') {
                    // initiate force delete dialog
                    var message = responseData.data + ' You can try again ' +
                                  'later or delete ignoring these problems."';
                    that.deleteUserConfirmDialog(options, message, true);
                } else {
                    utils.notifyWindow(response);
                }
            });
        },
    });

    data.UsersCollection = Backbone.Collection.extend({
        url: '/api/users/full',
        model: data.UserModel,
        parse: unwrapper
    });

    data.UserActivitiesModel = Backbone.Model.extend({
        urlRoot: '/api/users/a/:id',
        parse: unwrapper
    });

    data.UsersPageableCollection = Backbone.PageableCollection.extend({
        url: '/api/users/full',
        model: data.UserModel,
        parse: unwrapper,
        mode: 'client',
        state: {
            pageSize: 100
        }
    });

    data.ActivitiesCollection = Backbone.PageableCollection.extend({
        url: '/api/users/a/:id',
        model: data.UserActivitiesModel,
        parse: unwrapper,
        mode: 'client',
        state: {
            pageSize: 100
        }
    });

    data.NodeStatsModel = Backbone.Model.extend({
        parse: unwrapper,
    });

    data.NodeStatsCollection = Backbone.Collection.extend({
        url: '/api/stats/',
        model: data.NodeStatsModel,
        parse: unwrapper
    });

    data.AppModel = Backbone.Model.extend({
        defaults: {
            name: '',
            template: '',
            qualifier: ''
        },
        urlRoot: '/api/predefined-apps',
        parse: unwrapper
    });

    data.AppCollection = Backbone.PageableCollection.extend({
        url: '/api/predefined-apps',
        model: data.AppModel,
        parse: unwrapper,
        mode: 'client',
        state: {
            pageSize: 10
        },
    });

    data.CurrentUserModel = Backbone.Model.extend({
        url: function(){ return '/api/users/editself' },
        parse: unwrapper
    });

    data.PermissionModel = Backbone.Model.extend({
        urlRoot: '/api/settings/permissions',
        parse: unwrapper
    });

    data.PermissionsCollection = Backbone.Collection.extend({
        url: '/api/settings/permissions',
        model: data.PermissionModel,
        parse: unwrapper
    });

    data.NotificationModel = Backbone.Model.extend({
        urlRoot: '/api/settings/notifications',
        parse: unwrapper
    });

    data.NotificationsCollection = Backbone.Collection.extend({
        url: '/api/settings/notifications',
        model: data.NotificationModel,
        parse: unwrapper
    });

    data.SettingsModel = Backbone.Model.extend({
        urlRoot: '/api/settings/sysapi',
        parse: unwrapper
    });

    data.SettingsCollection = Backbone.Collection.extend({
        url: '/api/settings/sysapi',
        model: data.SettingsModel,
        parse: unwrapper
    });

    data.NetworkModel = Backbone.Model.extend({
        urlRoot: '/api/ippool/',
        parse: unwrapper
    });

    data.NetworkCollection = Backbone.Collection.extend({
        url: '/api/ippool/',
        model: data.NetworkModel,
        parse: unwrapper
    });

    data.PersistentStorageModel = Backbone.Model.extend({
        defaults: {
            name   : 'Nameless',
            size   : 0,
            in_use : false,
            pod    : ''
        },
        parse: unwrapper
    });

    data.PersistentStorageCollection = Backbone.Collection.extend({
        url: '/api/pstorage',
        model: data.PersistentStorageModel,
        parse: unwrapper
    });

    data.UserAddressModel = Backbone.Model.extend({
        defaults: {
            pod    : ''
        },
        parse: unwrapper
    });

    data.UserAddressCollection = Backbone.Collection.extend({
        url: '/api/ippool/userstat',
        model: data.UserAddressModel,
        parse: unwrapper
    });

    data.MenuModel = Backbone.Model.extend({
        defaults: function(){
            return { children: [], path: '#' }
        }
    });

    data.MenuCollection = Backbone.Collection.extend({
        model: data.MenuModel
    });

    return data;
});
