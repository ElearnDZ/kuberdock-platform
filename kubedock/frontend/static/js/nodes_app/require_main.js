requirejs.config({
    waitSeconds: 200,
    baseUrl: '/static/js',
    urlArgs: "bust=" + (new Date()).getTime(),
    paths: {
        backbone               : 'lib/backbone',
        "backbone-paginator"   : "lib/backbone.paginator",
        jquery                 : 'lib/jquery',
        'jquery-ui'            : 'lib/jquery-ui',
        "jquery-spin"          : "lib/jquery.spin",
        spin                   : "lib/spin.min",
        underscore             : 'lib/underscore-min',
        marionette             : 'lib/backbone.marionette',
        bootstrap              : 'lib/bootstrap',
        'bootstrap3-typeahead' : 'lib/bootstrap3-typeahead.min',
        moment                 : 'lib/moment.min',
        'moment-timezone'      : 'lib/moment-timezone-with-data.min',
        paginator              : 'lib/backbone.paginator',
        tpl                    : 'lib/tpl',
        text                   : 'lib/text',
        notify                 : 'lib/notify.min',
        mask                   : 'lib/jquery.mask',
        utils                  : 'utils',
        selectpicker           : 'lib/bootstrap-select.min',
        mousewheel             : 'lib/jquery.mousewheel',
        jscrollpane            : 'lib/jquery.jscrollpane.min'
    },
    shim: {
        jquery: {
            exports: "$"
        },
        underscore: {
            exports: "_"
        },
        backbone: {
            deps: ['jquery', 'underscore'],
            exports: 'Backbone'
        },
        'backbone-paginator' : ['backbone'],
        marionette: ['backbone'],
        bootstrap: {
            deps: ['jquery']
        },
        'bootstrap-editable': ['bootstrap'],
        'jquery-spin': ['spin'],
        tpl: ['text'],
        'jqplot-axis-renderer': ['jqplot'],
        selectpicker: {
            deps: ['jquery', 'bootstrap']
        },
        notify: {
            deps: ["jquery"],
            exports: 'jQuery.fn.notify'
        },
        utils: {
            deps: ['backbone', 'jquery']
        },
        mousewheel: {
            deps: ["jquery"]
        }
    },
    config: {
        moment: {
            noGlobal: true
        }
    }
});
require(['nodes_app/app'], function(Nodes) {
    Nodes.start();
});