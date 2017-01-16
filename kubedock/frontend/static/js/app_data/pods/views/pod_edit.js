import App from 'app_data/app';
import Model from 'app_data/model';
import * as utils from 'app_data/utils';

import layoutWizardTpl from 'app_data/pods/templates/layout_wizard.tpl';

import wizardSetContainerPendingBasicSettingsTpl from
    'app_data/pods/templates/wizard_set_container_pending_basic_settings.tpl';
import publicAccessControlsTpl from 'app_data/pods/templates/public_access_controls.tpl';
import portListTpl from 'app_data/pods/templates/editable_ports/list.tpl';
import portListItemTpl from 'app_data/pods/templates/editable_ports/item.tpl';
import portListEmptyTpl from 'app_data/pods/templates/editable_ports/empty.tpl';
import volumeMountListTpl from 'app_data/pods/templates/editable_volume_mounts/list.tpl';
import volumeMountListItemTpl from 'app_data/pods/templates/editable_volume_mounts/item.tpl';
import volumeMountListEmptyTpl from 'app_data/pods/templates/editable_volume_mounts/empty.tpl';

import wizardSetContainerEnvTpl from 'app_data/pods/templates/wizard_set_container_env.tpl';
import editableEnvVarTpl from 'app_data/pods/templates/editable_env_vars/item.tpl';

import wizardContainerCollectionItemTpl from
    'app_data/pods/templates/wizard_container_collection_item.tpl';
import wizardSetContainerCompleteTpl from
    'app_data/pods/templates/wizard_set_container_complete.tpl';

// search list
import searchYamlItemTpl from 'app_data/pods/templates/search_lists/yaml/item.tpl';
import searchYamlListTpl from 'app_data/pods/templates/search_lists/yaml/list.tpl';
import searchImageItemTpl from 'app_data/pods/templates/search_lists/image/item.tpl';
import searchImageListTpl from 'app_data/pods/templates/search_lists/image/list.tpl';
import searchLayoutTpl from 'app_data/pods/templates/search_lists/layout.tpl';

import 'bootstrap-editable';
import 'tooltip';
import 'bootstrap-select';
import BBCodeParser from 'bbcode-parser';

export const PodWizardLayout = Backbone.Marionette.LayoutView.extend({
    template: layoutWizardTpl,
    regions: {
        // TODO: 1) move menu and breadcrumbs regions into App;
        //       2) pull common parts out of "steps" into separate regions;
        nav    : '#navbar-steps',
        header : '#header-steps',
        steps  : '#steps',
    },
    onBeforeShow: utils.preloader.show,
    onShow: utils.preloader.hide,
    initialize(){
        this.listenTo(this.steps, 'show', function(view){
            _(['pod:save_changes', 'pod:pay_and_apply']).each(function(event){
                this.listenTo(view, event, _.bind(this.trigger, this, event));
            }, this);
        });
    },
});

export const ImageListItemView = Backbone.Marionette.ItemView.extend({
    template: searchImageItemTpl,
    tagName: 'div',
    className: 'item clearfix',
    triggers: { 'click .add-item': 'image:selected' }
});

export const AppListItemView = Backbone.Marionette.ItemView.extend({
    template: searchYamlItemTpl,
    tagName: 'div',
    className: 'item clearfix',

    bbParser: new BBCodeParser(BBCodeParser.defaultTags()),

    triggers: {
        'click .add-item': 'app:selected'
    },
    templateHelpers: function () {
        var that = this;
        return {
            'description': function () {
                if (this.filled_template && this.filled_template.kuberdock &&
                    this.filled_template.kuberdock.preDescription) {
                    var description = this.filled_template.kuberdock.preDescription;
                    return that.bbParser.parseString(description);
                }
            }
        };
    }
});

export const AppSearchView = Backbone.Marionette.CompositeView.extend({
    template: searchYamlListTpl,
    childViewContainer: '#yamls-list',
    childView: AppListItemView,
    collectionEvents: { 'update reset' : 'render' },
    templateHelpers: function(){
        return {
            colLenght : this.collection.length
        };
    }
});

export const ImageSearchView = Backbone.Marionette.CompositeView.extend({
    template: searchImageListTpl,
    childViewContainer: '#images-list',
    childView: ImageListItemView,
    collectionEvents: { 'update reset' : 'render' },
    templateHelpers: function(){
        return {
            colLenght : this.collection.length
        };
    }
});


export const GetImageView = Backbone.Marionette.LayoutView.extend({
    template: searchLayoutTpl,

    initialize(options){ this.pod = options.pod; },

    templateHelpers(){
        return {
            showPaginator: !!this.options.imageSearchListView.collection.length,
        };
    },
    regions: {
        appList: "#predefined-app-list",
        imageList: "#data-collection",
    },
    ui: {
        username          : '#username',
        cancel            : '.podsList',
        password          : '#password',
        moreImage         : '.btn-more',
        privateWrapper    : '.private',
        loginPrivateUres  : '.login-user',
        selectImage       : '.select-image',
        imageSource       : '.image-source',
        selectpicker      : '.selectpicker',
        searchImageButton : '.search-image',
        loader            : 'div#load-control',
        searchControl     : 'div.search-control',
        privateField      : '#private-image-field',
        input             : 'input#search-image-field',
        label             : 'label.placeholder'
    },

    events: {
        'click @ui.selectImage'       : 'selectImage',
        'click @ui.moreImage'         : 'loadNextPage',
        'click @ui.cancel'            : 'cancel',
        'click @ui.searchImageButton' : 'onSearchClick',
        'keypress @ui.input'          : 'onInputKeypress',
        'keypress @ui.privateField'   : 'selectImageByEnterKey',
        'keypress @ui.username'       : 'selectImageByEnterKey',
        'keypress @ui.password'       : 'selectImageByEnterKey',
        'change @ui.imageSource'      : 'imageSourceOnChange',
    },

    childEvents: {
        'image:selected' : 'childImageSelected',
        'app:selected' : 'childAppSelected',
    },

    onDomRefresh: function(){
        this.appList.show(this.options.appsListView);
        this.imageList.show(this.options.imageSearchListView);
    },

    onRender(){ this.ui.selectpicker.selectpicker(); },

    selectImageByEnterKey(evt){
        if (evt.which === utils.KEY_CODES.enter){
            evt.stopPropagation();
            this.selectImage();
        }
    },

    // image was selected directly by image url
    selectImage(){
        var image = this.ui.privateField.val(),
            auth;

        if (image.length === 0) {
            this.ui.privateField.focus();
            utils.notifyWindow('Please, enter image url');
            return;
        }
        if (this.ui.username.val() && this.ui.password.val()) {
            auth = {username: this.ui.username.val(),
                    password: this.ui.password.val()};
        }
        this.trigger('image:selected', image, auth);
    },

    imageSourceOnChange(){
        var val = this.ui.imageSource.val();
        if (val === 'DOCKERHUB_SEARCH'){
            this.ui.input.parent().show();
            this.ui.privateWrapper.hide();
            this.ui.loginPrivateUres.slideUp();
            this.ui.searchImageButton.parent().show();
            this.ui.label.text('Search images in DockerHub');
        } else if (val === 'OTHER_REGISTRIES'){
            this.ui.input.parent().hide();
            this.ui.privateWrapper.show();
            this.ui.loginPrivateUres.slideDown();
            this.ui.searchImageButton.parent().hide();
            this.ui.privateField.attr('placeholder', 'registry/namespace/image');
            this.ui.privateField.addClass('private-registry');
            this.ui.label.text('Select image from any registry');
        } else if (val === 'PRIVATE_REPOS') {
            this.ui.input.parent().hide();
            this.ui.privateWrapper.show();
            this.ui.loginPrivateUres.slideDown();
            this.ui.searchImageButton.parent().hide();
            this.ui.privateField.attr('placeholder', 'namespace/image');
            this.ui.privateField.removeClass('private-registry');
            this.ui.label.text('Select image from DockerHub');
        }
    },

    loadMoreButtonSpin(){
        this.fetching = true;
        this.ui.moreImage.show().addClass('animation').children().text('Loading...');
    },
    loadMoreButtonWait(){
        this.fetching = false;
        this.ui.moreImage.show().removeClass('animation').children().text('Load more');
    },
    loadMoreButtonHide(){
        this.fetching = false;
        this.ui.moreImage.hide();
    },

    onInputKeypress(evt){
        evt.stopPropagation();
        if (evt.which === utils.KEY_CODES.enter)
            this.search();
    },
    onSearchClick(evt){
        evt.stopPropagation();
        this.search();
    },
    search(){
        var query = this.ui.input.val().trim();
        if (query.length !== 0){
            this.loadMoreButtonSpin();
            this.model.set('query', query);
            this.trigger('image:searchsubmit');
        } else {
            this.ui.input.focus();
            utils.notifyWindow('First enter image name or part of image name to search');
        }
    },

    onShow(){
        this.ui.input.focus();  // FIXME: AC-3020
    },

    cancel(){
        var containers = this.pod.get('containers');
        if (this.pod.wizardState.addContainerFlow) {
            containers.remove(this.pod.wizardState.container);
            if (!containers.length) {
                App.navigate('pods', {trigger: true});
                return;
            }
            this.pod.wizardState.addContainerFlow = false;
        }
        this.trigger('step:complete');
    },

    // image was selected from search results
    childImageSelected(data){
        this.trigger('image:selected', data.model.get('name'));
    },

    childAppSelected: function(data){
        this.trigger('app:selected', data.model.get('id'));
    },

    loadNextPage(){
        if (this.fetching) return;
        this.loadMoreButtonSpin();
        this.trigger('image:getnextpage');
    }
});

export const PublicAccessControls = Backbone.Marionette.ItemView.extend({
    template: publicAccessControlsTpl,
    tagName: 'div',
    className(){
        return 'row domains-wrapper' + (
            this.model.wizardState.flow === 'CREATE_POD' ? '' : ' disabled');
    },

    initialize(options){
        this.domains = options.domains;
        this.isAWS = options.isAWS;
    },

    templateHelpers(){
        return {
            domains : this.domains,
            flow : this.model.wizardState.flow,
            isAWS : this.isAWS,
        };
    },

    ui: {
        chooseDomainSelect : '.choose-domain-select',
        publicAccessType   : '.public-access-type',
        domainsWrapper     : '.select-domain-wrapper',
        domainName         : '#public-access-type-domain',
        publicIpType       : '#public-access-type-ip',
        tooltip            : '[data-toggle="tooltip"]'
    },

    events: {
        'change @ui.publicAccessType' : 'toggleAccessType',
        'change @ui.chooseDomainSelect' : 'changeDomain',
    },

    modelEvents: {
        'change-public-access-need' : 'togglePublic',
    },

    onRender(){
        this.ui.chooseDomainSelect.selectpicker({
            title: 'Select from the list',
            dropupAuto: false,
        });
        var podDomain = this.model.get('domain'),
            selectedDomain = podDomain
                ? this.domains.findWhere({'name': podDomain}) ||
                    this.domains.find(domain => podDomain.endsWith(domain.get('name')))
                : this.domains.at(0);
        this.ui.chooseDomainSelect.selectpicker(
            'val', selectedDomain && selectedDomain.get('name'));
        this.ui.tooltip.tooltip();
    },

    onShow(){ this.togglePublic(); },

    togglePublic(){
        if (this.model.countPublicPorts()){
            this.$el.slideDown();
            if (this.model.get('domain') != null)
                this.ui.domainsWrapper.slideDown();
            else
                this.ui.domainsWrapper.slideUp();
        } else {
            this.$el.slideUp();
        }
    },
    toggleAccessType(){
        if (this.ui.publicAccessType.filter(':checked').val() === 'ip'){
            this.ui.domainsWrapper.slideUp();
            this.model.unset('domain');
        } else {
            this.ui.domainsWrapper.slideDown();
            this.changeDomain();
        }
    },
    changeDomain(){ this.model.set('domain', this.ui.chooseDomainSelect.val()); },
});

export const PortListItem = Backbone.Marionette.ItemView.extend({
    template : portListItemTpl,
    tagName : 'tr',

    ui: {
        podPort        : '.hostPort .ieditable',
        publicIp       : 'input.public',
        iseditable     : '.iseditable',  // TODO: rename (it's protocol)
        removePort     : '.remove-port',
        containerPort  : '.containerPort .ieditable',
    },

    events: {
        'click @ui.removePort' : 'removePortEntry',
        'click @ui.publicIp'   : 'togglePublic',
    },

    removePortEntry: function(evt){
        evt.stopPropagation();
        this.model.collection.remove(this.model);
    },
    togglePublic: function(evt){
        evt.stopPropagation();
        this.model.set('isPublic', !this.model.get('isPublic'));
    },

    onRender: function(){
        var that = this;

        var validatePort = function(newValue) {
            newValue = parseInt(newValue, 10);
            if (isNaN(newValue) || newValue < 1 || newValue > 65535) {
                utils.notifyWindow('Port must be a number in range 1-65535.');
                return ' ';  // return string - means validation not passed
            }
            return {newValue: newValue};
        };

        var checkUniqueness = function(newAttrs) {
            if (!newAttrs.containerPort)
                return;
            var dublicate = _(that.model.collection.where(
                    _.pick(newAttrs, 'containerPort', 'protocol')
                )).without(that.model)[0];
            if (dublicate) {
                utils.notifyWindow('Port ' + newAttrs.containerPort +
                                   '/' + newAttrs.protocol +
                                   ' already exists in this container.');
                return true;
            }
        };

        this.ui.podPort.editable({
            type: 'text',
            mode: 'inline',
            validate: function(newValue) {
                if (newValue === '') return;  // host port accepts empty value
                return validatePort(newValue);
            },
            success: function(response, newValue) {
                that.model.set('hostPort', newValue === '' ? null : newValue);
            },
        });

        this.ui.containerPort.editable({
            type: 'text',
            mode: 'inline',
            validate: validatePort,
            success: function(response, newValue) {
                if (checkUniqueness(_.extend({}, that.model.toJSON(),
                    {containerPort: newValue}))) return ' ';
                that.model.set('containerPort', newValue);
            },
        });

        this.ui.iseditable.editable({
            type: 'select',
            value: that.model.get('protocol'),
            source: [{value: 'tcp', text: 'tcp'}, {value: 'udp', text: 'udp'}],
            mode: 'inline',
            showbuttons: false,
            success: function(response, newValue) {
                if (checkUniqueness(_.extend({}, that.model.toJSON(), {protocol: newValue})))
                    return ' ';
                that.model.set('protocol', newValue);
            },
        });
    },
});

export const PortCollection = Backbone.Marionette.CompositeView.extend({
    template: portListTpl,
    tagName: 'div',
    className: 'row',
    childViewContainer: 'tbody',
    childView: PortListItem,
    emptyView: Backbone.Marionette.ItemView.extend({
        template : portListEmptyTpl,
        tagName  : 'tr',
    }),

    ui: {
        containerPort : '.containerPort .ieditable',
        podPort       : '.hostPort .ieditable',
        addPort       : '.add-port',
    },

    events: {
        'click @ui.addPort'         : 'addItem',
        'click @ui.publicAccessType': 'visibleDomainControl',
    },

    addItem(evt){ this.collection.add(new Model.Port()); },
});

export const VolumeMountListItem = Backbone.Marionette.ItemView.extend({
    template : volumeMountListItemTpl,
    tagName : 'tr',

    ui: {
        mountPath      : '.mountPath.ieditable',
        pdSelect       : '.pd-select',
        pdSelectSearch : '.pd-select .bs-searchbox input',
        persistent     : '.persistent',
        removeVolume   : '.remove-volume',
        pdName         : '.pd-name',
        pdSize         : '.pd-size',
    },
    events: {
        'input @ui.pdSelectSearch'      : 'searchPD',
        'hide.bs.select @ui.pdSelect'   : 'selectPD',
        'change @ui.pdSize'             : 'changeSize',
        'keyup @ui.pdSize'              : 'changeSize',
        'click @ui.persistent'          : 'togglePersistent',
        'click @ui.removeVolume'        : 'removeVolumeEntry',
    },

    templateHelpers(){
        return {
            isPersistent: !!this.volume.persistentDisk,
            persistentDisk: this.getPDModel(),
            persistentDrives: this.pod.persistentDrives,
            pdSizeLimit: this.pod.pdSizeLimit,
            pod: this.pod,
        };
    },

    initialize(options){
        this.container = this.model.getContainer();
        this.pod = this.container.getPod();
        var volumes = this.pod.get('volumes');
        this.volume = _.findWhere(volumes, {name: this.model.get('name')});
        if (this.volume === undefined) {
            this.volume = {name: this.model.get('name')};
            volumes.push(this.volume);
        } else if (this.volume.persistentDisk){
            this.listenTo(this.pod.persistentDrives, 'refreshSelects', this.render);
        }
    },

    getPDModel(name){
        name = name || (this.volume.persistentDisk || {}).pdName;
        if (!name || !this.pod.persistentDrives) return;
        return this.pod.persistentDrives.findWhere({name: name});
    },

    nameFormat: /^[a-z]+[\w-]*$/i,

    searchPD(evt){
        var name = evt.target.value = evt.target.value.trim(),
            pd = this.getPDModel(name);
        this.ui.pdSelect.find('.add-new-pd, .invalid-name-pd').remove();

        if (name){
            var error = !this.nameFormat.test(name)
                ? 'Only "-", "_" and alphanumeric symbols are allowed.'
                : name.length > 36 ? 'Maximum length is 36 symbols.'
                : null;
            if (error){
                this.ui.pdSelect.prepend($('<option disabled/>')
                    .addClass('invalid-name-pd').val(name).text(error)
                    // also add name, so selectpicker won't hide this "option"
                    .append($('<span class="hidden"/>').text(name))
                );
                this.ui.pdSelect.selectpicker('refresh');
                $(evt.target).addClass('error');
                return;
            }
            if (pd === undefined){  // add option "create new pd" in select
                this.ui.pdSelect.prepend($('<option/>')
                    .val(name).text(name + ' (new)').addClass('add-new-pd')
                );
            }
        }
        this.ui.pdSelect.selectpicker('refresh');
    },

    selectPD(){
        // if there was an error message, remove it
        this.ui.pdSelect.find('.invalid-name-pd').remove();
        this.ui.pdSelect.selectpicker('refresh');

        var name = (this.ui.pdSelect.val() || '').trim();
        if (!name || !this.nameFormat.test(name)) {
            var current = this.getPDModel();
            if (current != null)
                this.ui.pdSelect.val(current.get('name')).selectpicker('render');
            return;
        }

        this.releasePersistentDisk();
        var pd = this.getPDModel(name);
        this.ui.pdSize.prop('disabled', pd !== undefined);
        if (pd === undefined){  // new pd
            pd = new Model.PersistentStorageModel({name: name});
            pd.isNewPD = true;
            pd = this.pod.persistentDrives.add(pd);
        }
        pd.set('in_use', true);
        this.volume.persistentDisk.pdName = name;
        this.volume.persistentDisk.pdSize = pd.get('size');
        this.ui.pdSize.val(pd.get('size'));

        var conflicts = pd.conflictsWith(this.pod);
        if (conflicts.length){
            utils.notifyWindow('Persistent Disk ' + name + ' conflicts with ' +
                                conflicts.pluck('name').join(', ') +
                                '. All disks must be on the same node. ' +
                                'You need to eliminate this conflict to save the pod.');
        }

        this.pod.persistentDrives.trigger('refreshSelects');
    },

    changeSize(evt){
        evt.stopPropagation();
        // TODO: wants rethinking.
        var size = parseInt(evt.target.value, 10);
        if (_.isNaN(size)){
            this.ui.pdSize.addClass('error');
        } else if (size < 1 || this.pdSizeLimit !== undefined && size > this.pdSizeLimit) {
            this.ui.pdSize.addClass('error');
            utils.notifyWindow('Max size of persistent volume should be ' +
                               'more than zero and less than ' +
                               this.pdSizeLimit + ' GB');
        } else {
            this.ui.pdSize.removeClass('error');
            this.getPDModel().set('size', size);
            this.volume.persistentDisk.pdSize = size;
        }
    },

    togglePersistent(evt){
        evt.stopPropagation();
        var that = this;

        if (!this.model.get('mountPath')){
            utils.notifyWindow('Mount path must be set!');
            this.ui.mountPath.click();
            return false;
        } else {
            if (this.pod.persistentDrives === undefined) {
                var persistentDrives = new Model.PersistentStorageCollection();
                utils.preloader.show();
                $.when(persistentDrives.fetch({wait: true}),
                       App.getSystemSettingsCollection())
                    .always(utils.preloader.hide)
                    .fail(utils.notifyWindow)
                    .done(function(drives, settings){
                        var conf = settings.byName('persitent_disk_max_size');
                        that.pod.pdSizeLimit = conf == null
                            ? 10 : parseInt(conf.get('value'), 10);
                        that.pod.persistentDrives = persistentDrives;
                        that.toggleVolumeEntry();
                        that.render();
                        that.ui.pdSelect.selectpicker('toggle');
                    });
            } else {
                that.toggleVolumeEntry();
                that.render();
                that.ui.pdSelect.selectpicker('toggle');
            }
        }
    },

    toggleVolumeEntry(){
        if (this.volume.persistentDisk) {
            this.releasePersistentDisk();
            delete this.volume.persistentDisk;
            this.stopListening(this.pod.persistentDrives, 'refreshSelects', this.render);
            this.pod.persistentDrives.trigger('refreshSelects');
        } else {
            this.listenTo(this.pod.persistentDrives, 'refreshSelects', this.render);
            this.volume.persistentDisk = {pdName: null, pdSize: null};
        }
    },

    // If volume uses PD, release it. If this PD is new, remove it.
    releasePersistentDisk(){
        if (!_.has(this.volume, 'persistentDisk') ||
            this.pod.persistentDrives === undefined) return;
        var disk = this.getPDModel();
        if (disk === undefined) return;
        if (disk.isNewPD){
            this.pod.persistentDrives.remove(disk);
            return;
        }
        disk.set('in_use', false);
    },

    removeVolumeEntry(evt){
        evt.stopPropagation();
        this.releasePersistentDisk();
        this.model.collection.remove(this.model);
        var volumes = this.pod.get('volumes');
        volumes.splice(volumes.indexOf(this.volume), 1);
        if (this.volume.persistentDisk)
            this.pod.persistentDrives.trigger('refreshSelects');
    },

    onRender(){
        var that = this;

        this.ui.mountPath.editable({
            type: 'text',
            mode: 'inline',
            validate: function(newValue){
                var value = newValue.trim(),
                    dublicate = _(that.model.collection.where({mountPath: value}))
                        .without(that.model)[0],
                    error = dublicate
                        ? 'Path must be unique.'
                        : Model.Container.validateMountPath(value);

                // TODO: style for editable validation errors
                // if (error) return error;
                if (error) {
                    utils.notifyWindow(error);
                    return ' ';
                }

                return {newValue: value};
            },
            success: function(response, newValue) {
                that.model.set('mountPath', newValue);
            }
        });
        this.ui.pdSelect.selectpicker({
            liveSearch: true,
            title: 'Select Persistent Disk',
            liveSearchPlaceholder: 'Enter the name',
            dropupAuto: false,
        });
        this.ui.pdSelect.selectpicker('val', (this.volume.persistentDisk || {}).pdName);
    }
});

export const VolumeMountCollection = Backbone.Marionette.CompositeView.extend({
    template: volumeMountListTpl,
    tagName: 'div',
    className: 'row',
    childViewContainer: 'tbody',
    childView: VolumeMountListItem,
    emptyView: Backbone.Marionette.ItemView.extend({
        template : volumeMountListEmptyTpl,
        tagName  : 'tr',
    }),

    ui: { addVolume : '.add-volume' },
    events: { 'click @ui.addVolume' : 'addVolume' },
    addVolume(evt){ this.collection.add(new Model.VolumeMount()); },
});

export const WizardPortsSubView = Backbone.Marionette.LayoutView.extend({
    tagName: 'div',
    regions: {
        ports: '#editable-ports-list',
        publicAccessControls: '#public-access-controls',
        volumeMounts: '#editable-vm-list',
    },
    template: wizardSetContainerPendingBasicSettingsTpl,
    className: 'container',
    id: 'add-image',

    ui: {
        input               : 'input',
        nextStep            : '.next-step',
        prevStep            : '.prev-step',
        input_command       : 'input.command',
        publicAccessTypeNote: '#public-access-type-note',
        cancelEdit          : '.cancel-edit',
        editEntirePod       : '.edit-entire-pod',
        saveChanges         : '.save-changes',
    },

    events: {
        'focus @ui.input'          : 'removeError',
        'click @ui.prevStep'       : 'goBack',
        'click @ui.nextStep'       : 'goNext',
        'change @ui.input_command' : 'changeCommand',
        'click @ui.cancelEdit'   : 'cancelEdit',
        'click @ui.editEntirePod': 'editEntirePod',
        'click @ui.saveChanges'  : 'saveChanges',
    },

    initialize(options){
        this.pod = this.model.getPod();
        this.payg = options.payg;
        this.hasBilling = options.hasBilling;
        this.domains = options.domains;
        this.isAWS = options.ipMode === 'aws';
    },

    templateHelpers(){
        return {
            flow : this.pod.wizardState.flow,
            isAWS : this.isAWS
        };
    },

    onBeforeShow(){
        this.ports.show(new PortCollection({
            model: this.model,
            collection: this.model.get('ports')
        }), {replaceElement: true});

        if (this.domains.length){
            this.publicAccessControls.show(new PublicAccessControls({
                model: this.pod,
                domains : this.domains,
                isAWS: this.isAWS,
            }), {replaceElement: true});
        }

        this.volumeMounts.show(new VolumeMountCollection({
            model: this.model,
            collection: this.model.get('volumeMounts'),
        }), {replaceElement: true});

        this.listenTo(this.pod, 'change-public-access-need', function(needs){
            this.ui.publicAccessTypeNote.toggle(needs);
        });
    },

    cancelEdit(){
        var podID = this.pod.editOf().id,
            id = this.model.id;
        utils.modalDialog({
            title: 'Cancel edit?',
            body: 'This will discard all unsaved changes. Are you sure?',
            small: true,
            show: true,
            footer: {
                buttonOk(){
                    App.navigate(`pods/${podID}/container/${id}/general`, {trigger: true});
                },
                buttonCancel: true,
                buttonOkText: 'Yes, discard latest changes',
                buttonCancelText: 'No'
            }
        });
    },

    editEntirePod(evt){
        evt.stopPropagation();
        if (this.validateAndNormalize()){
            this.pod.wizardState.flow = 'EDIT_ENTIRE_POD';
            this.pod.wizardState.container = null;
            App.navigate(`pods/${this.pod.editOf().id}/edit`);
            this.trigger('step:complete');
        }
    },

    saveChanges(evt){
        evt.stopPropagation();
        if (!this.validateAndNormalize())
            return;
        if (this.hasBilling && !this.payg){
            this.pod.recalcInfo(App.userPackage);
            this.pod.editOf().recalcInfo(App.userPackage);
            if (this.pod.rawTotalPrice > this.pod.editOf().rawTotalPrice){
                this.trigger('step:complete');
                return;
            }
        }
        this.trigger('pod:save_changes');
    },

    removeError(evt){
        var target = $(evt.target);
        if (target.hasClass('error')) target.removeClass('error');
    },

    changeCommand(evt){
        evt.stopPropagation();
        var tgt = $(evt.target),
            cmd = tgt.val().trim();
        if (!cmd){
            // Explicitly replace empty command with CMD from image
            // (in case of empty command in container spec, docker will use
            // CMD from image)
            tgt.val(this.filterCommand(this.model.get('args')));
            return;
        }
        this.model.set('args', _.map(
            cmd.match(/(?:[^\s"']+|("|').*?\1)/g),
            function(i){ return i.replace(/^["']|["']$/g, ''); })
        );
    },

    validateAndNormalize(){
        var that = this;

        if (this.pod.wizardState.flow === 'CREATE_POD'){
            if (this.pod.get('domain') && !this.pod.publicPortsShouldContain(80, 443)){
                utils.notifyWindow('Only 80 and 443 ports are allowed');
                return false;
            }
        }

        // remove empty ports and volumeMounts
        this.model.set('ports', this.model.get('ports').filter(
            function(port){ return port.get('containerPort'); }));
        this.model.set('volumeMounts', this.model.get('volumeMounts').filter(
            function(v){
                var path = v.get('mountPath');
                if (!path) that.pod.deleteVolumes([v.name]);
                return path;
            }));

        /* mountPath and persistent disk check */
        var volumes = this.pod.get('volumes'),
            vm = this.model.get('volumeMounts');

        for (var i = 0; i < vm.length; i++) {
            var volumeMount = vm.at(i),
                name = volumeMount.get('name'),
                vol = _.findWhere(volumes, {name: name});

            if (vol.hasOwnProperty('persistentDisk')) {
                var pd = vol.persistentDisk;
                if (!pd.pdSize || !pd.pdName) {
                    utils.notifyWindow('Persistent options must be set!');
                    return;
                } else if (pd.pdSize > that.pod.pdSizeLimit){
                    utils.notifyWindow('A persistent disk size isn\'t expected ' +
                                       'to exceed ' + that.pod.pdSizeLimit + ' GB');
                    return;
                }
            }
        }

        /* check CMD and ENTRYPOINT */
        if (!this.model.get('command')) this.model.set('command', []);
        if (!this.model.get('args')) this.model.set('args', []);
        var originalImage = this.model.originalImage;
        if (!this.model.get('command').length && !this.model.get('args').length &&
                !(originalImage.get('command') && originalImage.get('command').length) &&
                !(originalImage.get('args') && originalImage.get('args').length)){
            utils.notifyWindow('Please, specify value of the Command field.');
            utils.scrollTo(this.ui.input_command);
            return;
        }

        /* check ports */
        var showDublicatePortError = function(dublicatePort){
            var container = dublicatePort.container,
                type = dublicatePort.isPod ? 'pod' : 'container',
                where = container === that.model ? 'this container!'
                    : ' other container (' + container.get('image') + ')!';
            utils.notifyWindow('You have a duplicate ' + type + ' port ' +
                               dublicatePort.port + '/' +
                               dublicatePort.protocol + ' in ' + where);
        };

        try {
            this.model.get('ports').each(function(port, i){
                that.pod.get('containers').each(function(container2){
                    container2.get('ports').each(function(port2, j){
                        if (container2 === that.model && i === j) return;
                        if (port.get('protocol') !== port2.get('protocol')) return;

                        var protocol = port.get('protocol'),
                            containerPort = port.get('containerPort'),
                            containerPort2 = port2.get('containerPort'),
                            hostPort = port.get('hostPort') || containerPort,
                            hostPort2 = port2.get('hostPort') || containerPort2;
                        if (containerPort === containerPort2)
                            throw {container: container2, protocol: protocol,
                                   port: containerPort};
                        if (hostPort === hostPort2)
                            throw {container: container2, protocol: protocol,
                                   port: hostPort, isPod: true};
                    });
                });
            });
        } catch (e) {
            showDublicatePortError(e);
            return;
        }
        return true;
    },

    goNext(evt){
        if (this.validateAndNormalize())
            this.trigger('step:envconf');
    },

    goBack(evt){
        if (this.pod.wizardState.addContainerFlow){
            this.pod.get('containers').remove(this.pod.wizardState.container);
            this.trigger('step:getimage');
        } else {
            this.pod.wizardState.container = null;
            this.trigger('step:complete');
        }
    },

    onRender(){
        this.ui.input_command.val(this.filterCommand(this.model.get('args')));
        this.ui.publicAccessTypeNote.toggle(!!this.pod.countPublicPorts());
    },

    filterCommand(command) {
        command = _.map(command, function(e) {
            return e.indexOf(' ') > 0 ? '"' + e + '"' : e;
        });
        return command.join(' ');
    },
});

export const EnvTableRow = Backbone.Marionette.CompositeView.extend({
    template: editableEnvVarTpl,
    tagName: 'tr',
    className: 'col-sm-12 no-padding',
    ui: {
        removeItem   : '.remove-env',
        input        : '.change-input',
        nameField    : 'input.name',
        valueField   : 'input.value',
    },
    events: {
        'focus @ui.input' : 'removeError',
        'change @ui.nameField': 'onChangeName',
        'change @ui.valueField': 'onChangeValue',
        'click @ui.removeItem': 'removeVariable',
    },

    removeError(evt){ utils.removeError($(evt.target)); },

    onChangeName(evt){
        var name = evt.target.value.trim();
        this.model.set('name', evt.target.value = name);
    },
    onChangeValue(evt){
        var value = evt.target.value.trim();
        this.model.set('value', evt.target.value = value);
    },
    removeVariable(evt){ this.model.collection.remove(this.model); },
    validateAndNormalize(){
        var paternFirstSumbol = /^[a-zA-Z]/,
            paternValidName = /^[a-zA-Z0-9-_\.]*$/;

        var name = this.model.get('name');
        if (!paternFirstSumbol.test(name)){
            utils.notifyInline('First symbol must be letter in variables name',
                               this.ui.nameField);
            return false;
        }
        if (!paternValidName.test(name)){
            utils.notifyInline('Variable name should contain only ' +
            'Latin letters or ".", "_", "-" symbols', this.ui.nameField);
            return false;
        }
        if (name.length > 255){
            utils.notifyInline('Max length is 255 symbols', this.ui.nameField);
            return false;
        }

        var value = this.model.get('value');
        if (!value){
            utils.notifyInline('Variables value must be set', this.ui.valueField);
            return false;
        }
        return true;
    }
});

export const WizardEnvSubView = Backbone.Marionette.CompositeView.extend({
    template: wizardSetContainerEnvTpl,
    tagName: 'div',
    childView: EnvTableRow,
    childViewContainer: '.environment-set-up tbody',

    ui: {
        ieditable    : '.ieditable',
        reset        : '.reset-button',
        envTable     : '.environment-set-up',
        addItem      : '.add-env',
        next         : '.next-step',
        prev         : '.go-to-ports',
        cancelEdit   : '.cancel-edit',
        editEntirePod: '.edit-entire-pod',
        saveChanges  : '.save-changes',
        navButtons   : '.nav-buttons',
    },

    events: {
        'click @ui.addItem'      : 'addItem',
        'click @ui.removeItem'   : 'removeItem',
        'click @ui.reset'        : 'resetFielsdsValue',
        'click @ui.next'         : 'finalStep',
        'click @ui.prev'         : 'prevStep',
        'click @ui.cancelEdit'   : 'cancelEdit',
        'click @ui.editEntirePod': 'editEntirePod',
        'click @ui.saveChanges'  : 'saveChanges',
    },

    modelEvents: { 'change': 'render' },
    collectionEvents: { 'update reset': 'toggleTableVisibility' },
    initialize() { this.collection = this.model.get('env'); },

    templateHelpers(){
        return {
            flow: this.model.getPod().wizardState.flow,
        };
    },

    onDomRefresh(){
        if (utils.hasScroll()) {
            this.ui.navButtons.addClass('fixed');
        } else {
            this.ui.navButtons.removeClass('fixed');
        }
    },

    toggleTableVisibility(){ this.ui.envTable.toggleClass('hidden', this.isEmpty()); },

    validateAndNormalize(){
        var valid = true,
            env = this.model.get('env');

        /* check for duplicates */
        var uniqEnvVars = env.groupBy(function(item){ return item.get('name'); }),
            hasDuplicates = false;

        this.children.each(function(view){
            var group = uniqEnvVars[view.model.get('name')];
            if (group.length > 1){
                hasDuplicates = true;
                utils.notifyInline('Duplicate variable names are not allowed',
                                   view.ui.nameField);
            }
        });
        if (hasDuplicates){
            utils.scrollTo($('input.error').first());
            return false;
        }

        /* get only not empty env from model */
        env.reset(env.filter(function(item){ return item.get('name'); }));

        /* validation */
        this.children.each(function(view){
            valid = valid && view.validateAndNormalize();
        });

        /* scroling to error */
        var invalidFields = $('input.error');
        if (invalidFields.length) utils.scrollTo(invalidFields.first());

        return valid && env;
    },
    finalStep(evt){
        evt.stopPropagation();
        var env = this.validateAndNormalize();
        if (env){
            this.model.set('env', env);
            this.trigger('step:complete');
        }
    },
    prevStep(){ this.trigger('step:portconf'); },

    cancelEdit(){
        var podID = this.model.getPod().editOf().id,
            id = this.model.id;
        utils.modalDialog({
            title: 'Cancel edit?',
            body: 'This will discard all unsaved changes. Are you sure?',
            small: true,
            show: true,
            footer: {
                buttonOk: function(){
                    App.navigate('pods/' + podID + '/container/' + id +
                                 '/env', {trigger: true});
                },
                buttonCancel: true,
                buttonOkText: 'Yes, discard latest changes',
                buttonCancelText: 'No'
            }
        });
    },
    editEntirePod(evt){
        evt.stopPropagation();
        var env = this.validateAndNormalize();
        if (env){
            this.model.set('env', env);
            this.model.getPod().wizardState.flow = 'EDIT_ENTIRE_POD';
            this.model.getPod().wizardState.container = null;
            App.navigate('pods/' + this.model.getPod().editOf().id + '/edit');
            this.trigger('step:complete');
        }
    },
    saveChanges(evt){
        evt.stopPropagation();
        var env = this.validateAndNormalize();
        if (env){
            this.model.set('env', env);
            this.trigger('pod:save_changes');
        }
    },

    addItem(evt){
        evt.stopPropagation();
        this.collection.add({name: null, value: null});
    },

    resetFielsdsValue(){
        this.model.set('env', _.map(this.model.originalImage.get('env'), _.clone));
        this.render();
    },
});

export const ContainerListItemView = Backbone.Marionette.ItemView.extend({
    template: wizardContainerCollectionItemTpl,
    tagName: 'tr',
    className: 'added-containers',

    ui: {
        deleteBtn: '.delete-item',
        editBtn: '.edit-item',
        lessKubeBtn: '.kubes-less',
        moreKubeBtn: '.kubes-more',
        kubes: '.kubes',
        tooltip : '[data-toggle="tooltip"]'
    },
    events: {
        'click @ui.lessKubeBtn': 'removeKube',
        'click @ui.moreKubeBtn': 'addKube',
    },
    triggers: {
        'click @ui.deleteBtn': 'container:delete',
        'click @ui.editBtn': 'container:edit',
        'change @ui.kubes': 'container:kubes:change',
    },
    initialize(options){ _.extend(this, options); },
    templateHelpers(){
        return {
            period: App.userPackage.get('period'),
            price: this.model.price,
            kubesLimit: this.kubesLimit,
            showDelete: !this.model.getPod().editOf() ||  // it's a new pod or...
                        this.model.collection.length > 1,  // there is more then one container
        };
    },
    onRender(){ this.ui.tooltip.tooltip(); },
    addKube(){ this.ui.kubes.val(+this.ui.kubes.val() + 1).change(); },
    removeKube(){ this.ui.kubes.val(+this.ui.kubes.val() - 1).change(); },
});

export const WizardCompleteSubView = Backbone.Marionette.CompositeView.extend({
    template: wizardSetContainerCompleteTpl,
    childView: ContainerListItemView,
    childViewContainer: '.total-wrapper tbody.wizard-containers-list',
    tagName: 'div',
    childViewOptions(){ return _.pick(this, 'pkg', 'kubesLimit'); },

    childEvents: {
        'container:edit': 'editContainer',
        'container:delete': 'deleteContainer',
        'container:kubes:change': 'changeContainerKubes',
    },

    initialize(options){
        this.pkg = App.userPackage;
        this.collection = this.model.get('containers');
        this.model.recalcInfo(this.pkg);
        if (this.model.editOf())
            this.model.editOf().recalcInfo(this.pkg);
        this.hasBilling = options.hasBilling;
        this.payg = options.payg;
        this.kubesLimit = options.kubesLimit;

        // TODO: package change, package-kube relationship change
        this.listenTo(App.kubeTypeCollection, 'change update reset', this.pricingChanged);
        this.on('show', function(){ this.checkKubeTypes(/*ensureSelected*/false); });
    },

    templateHelpers() {
        var kubeTypes = this.pkg.getKubeTypes();
        kubeTypes.each(function(kt){
            var conflicts = kt.conflicts.pluck('name').join(', ');

            kt.formattedName = kt.get('name') + ' ' + (kt.conflicts.length
                ? '(conflict with disk ' + conflicts + ')'
                : '');

            kt.disabled = !kt.conflicts.length;
        });

        kubeTypes.reset(kubeTypes.filter(function(kt){ return kt.get('available'); }));

        var edited = this.model.editOf();

        this.model.recalcInfo(this.pkg);
        if (edited)
            edited.recalcInfo(this.pkg);

        return {
            wizardState      : this.model.wizardState,
            formatPrice      : _.bind(this.pkg.getFormattedPrice, this.pkg),
            edited           : edited,
            diffTotalPrice   : edited && this.model.rawTotalPrice - edited.rawTotalPrice,
            isPublic         : this.model.isPublic,
            isPerSorage      : this.model.isPerSorage,
            limits           : this.model.limits,
            totalPrice       : this.model.rawTotalPrice,
            kubeTypes        : kubeTypes,
            kubesLimit       : this.kubesLimit,
            restart_policies : {'Always': 'Always', 'Never': 'Never',
                                'OnFailure': 'On Failure'},
            restart_policy   : this.model.get('restartPolicy'),
            pkg              : this.pkg,
            hasBilling       : this.hasBilling,
            persistentDrives : _.chain(this.model.get('volumes'))
                .map(function(vol){
                    return vol.persistentDisk && vol.persistentDisk.pdName &&
                           this.model.persistentDrives.findWhere(
                               {name: vol.persistentDisk.pdName}
                           );
                }, this).filter(_.identity).value(),
            payg             : this.payg    // Pay-As-You-Go billing method
        };
    },

    ui: {
        'policy'                  : 'select.restart-policy',
        'kubeTypes'               : 'select.kube_type',
        'editPolicy'              : '.edit-policy',
        'editPolycyDescription'   : '.edit-polycy-description',
        'editKubeType'            : '.edit-kube-type',
        'editKubeTypeDescription' : '.edit-kube-type-description',
        'selectpicker'            : '.selectpicker',
        'tooltip'                 : '[data-toggle="tooltip"]'
    },

    events: {
        'click .prev-step'       : 'goBack',
        'click .add-more'        : 'addItem',
        'click .node'            : 'toggleNode',
        'change .replicas'       : 'changeReplicas',
        'change @ui.kubeTypes'   : 'changeKubeType',
        'change @ui.policy'      : 'changePolicy',
        'click @ui.editPolicy'   : 'editPolicy',
        'click @ui.editKubeType' : 'editKubeType',
        'click .save-container'       : 'save',
        'click .pay-and-run-container': 'payAndRun',
        'click .pay-and-apply-changes': 'payAndApply',
        'click .save-changes'         : 'saveChanges',
        'click .cancel-edit'          : 'cancelEdit',
    },

    save(){
        if (!this.checkKubeTypes(/*ensureSelected*/true))
            this.trigger('pod:save');
    },
    payAndRun(){
        if (!this.checkKubeTypes(/*ensureSelected*/true))
            this.trigger('pod:pay_and_run');
    },
    payAndApply(){
        if (!this.checkKubeTypes(/*ensureSelected*/true))
            this.trigger('pod:pay_and_apply');
    },
    saveChanges(){
        if (!this.checkKubeTypes(/*ensureSelected*/true))
            this.trigger('pod:save_changes');
    },
    cancelEdit(){
        var that = this;
        utils.modalDialog({
            title: 'Cancel edit?',
            body: 'This will discard all unsaved changes. Are you sure?',
            small: true,
            show: true,
            footer: {
                buttonOk: function(){
                    App.navigate('pods/' + that.model.editOf().id, {trigger: true});
                },
                buttonCancel: true,
                buttonOkText: 'Yes, discard latest changes',
                buttonCancelText: 'No'
            }
        });
    },

    checkKubeTypes(ensureSelected){
        if (this.model.get('kube_type') === Model.KubeType.noAvailableKubeTypes.id){
            if (_.any(App.userPackage.getKubeTypes().pluck('available')))
                Model.KubeType.noAvailableKubeTypes.notifyConflict();
            else
                Model.KubeType.noAvailableKubeTypes.notify();
            return true;
        } else if (ensureSelected && this.model.get('kube_type') === undefined){
            utils.notifyWindow('Please, select kube type.');
            return true;
        }
    },

    changeContainerKubes(childView){
        var kubes = Math.max(1, Math.min(this.kubesLimit, +childView.ui.kubes.val()));
        childView.ui.kubes.val(kubes);
        childView.model.set('kubes', kubes);
        this.render();
    },

    deleteContainer(childView){
        var container = childView.model;
        if (this.model.get('containers').length >= 2) {
            this.model.get('containers').remove(container);
            var wizardState = this.model.wizardState;
            if (wizardState.container === container) {
                wizardState.addContainerFlow = false;
                wizardState.container = null;
            }
            this.model.solveKubeTypeConflicts();
            this.render();
        } else {
            utils.modalDialogDelete({
                title: "Delete",
                body: "After deleting the last container, you will go " +
                      "back to the main page. Delete this container?",
                small: true,
                show: true,
                footer: {
                    buttonOk: function(){
                        App.navigate('pods', {trigger: true});
                    },
                    buttonCancel: true
                }
            });
        }
    },

    editContainer(childView){
        this.model.wizardState.container = childView.model;
        this.model.wizardState.addContainerFlow = false;
        this.trigger('step:portconf');
    },

    addItem(evt){
        evt.stopPropagation();
        this.model.wizardState.container = null;
        this.model.wizardState.addContainerFlow = true;
        this.trigger('step:getimage');
    },

    // edit env vars of the last edited container
    goBack(evt){
        evt.stopPropagation();
        this.trigger('step:envconf');
    },

    toggleNode(evt){
        evt.stopPropagation();
        var tgt = $(evt.target),
            node = tgt.closest('td').next('td').text().trim();
        this.model.set('node', node);
        this.render();
    },

    changeReplicas(evt){
        evt.stopPropagation();
        this.model.set('replicas', parseInt($(evt.target).val().trim(), 10));
    },

    changeKubeType(evt){
        evt.stopPropagation();
        var kubeID = parseInt(evt.target.value, 10);
        this.model.set('kube_type', kubeID);
        this.render();
    },

    changePolicy(evt){
        evt.stopPropagation();
        var restartPolicy = $(evt.target).val();
        this.model.set('restartPolicy', restartPolicy);
    },

    /**
     * Got "change" event for package or kube types
     */
    pricingChanged(){
        if (!this.model.getKubeType().get('available'))
            this.model.unset('kube_type');  // no longer available
        this.render();
    },

    onRender() {
        var noAvailableKubeTypes = Model.KubeType.noAvailableKubeTypes;

        this.ui.selectpicker.selectpicker();
        this.ui.tooltip.tooltip();
        this.ui.kubeTypes.selectpicker({
            noneSelectedText: this.model.get('kube_type') === noAvailableKubeTypes
                ? 'No available kube types' : 'Select kube type',
        });
        if (this.model.get('kube_type') === undefined)
            this.ui.kubeTypes.val('').selectpicker('render');  // unselect
        else
            this.ui.kubeTypes.selectpicker('val', this.model.get('kube_type'));
    },

    editPolicy(){
        this.ui.editPolicy.hide();
        this.ui.editPolycyDescription.hide();
        this.ui.policy.attr('disabled', false);
        this.$('.policy .disabled').removeClass('disabled');
    },

    editKubeType(){
        this.ui.editKubeType.hide();
        this.ui.editKubeTypeDescription.hide();
        this.ui.kubeTypes.attr('disabled', false);
        this.ui.kubeTypes.removeClass('disabled');
        this.$('.kube-type-wrapper button.disabled').removeClass('disabled');
    },
});
