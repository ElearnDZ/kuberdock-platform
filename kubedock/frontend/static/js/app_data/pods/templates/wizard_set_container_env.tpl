<div class="container" id="add-image">
    <div class="col-md-3 col-sm-12 sidebar">
        <ul class="nav nav-sidebar">
            <li role="presentation" class="success">Choose image</li>
            <li role="presentation" class="success">Set up image</li>
            <li role="presentation" class="active">Environment variables</li>
            <li role="presentation">Final setup</li>
        </ul>
    </div>
    <div id="details_content" class="col-md-9 col-sm-12 set-up-image clearfix no-padding">
        <div id="tab-content" class="environment clearfix">
            <div class="image-name-wrapper">
                <%- image %>
                <% if (sourceUrl !== undefined) { %>
                    <a class="pull-right image-link" href="<%- /^https?:\/\//.test(sourceUrl) ? sourceUrl : 'http://' + sourceUrl %>" target="blank"><span>Learn more about variables for this image</span></a>
                <% } %>
            </div>
            <% if (env.length != 0){ %>
            <div class="row no-padding">
                <div class="col-md-12">
                    <table class="environment-set-up">
                        <thead>
                            <tr class="col-sm-12 no-padding">
                                <th>Name</th>
                                <th>Value</th>
                                <th></th>
                            </tr>
                        </thead>
                        <tbody>
                            <% _.each(env, function(e, index){ %>
                            <tr class="col-sm-12 no-padding">
                                <td class="col-sm-4 no-padding">
                                    <input class="name change-input" type="text" value="<%- e.name ? e.name : '' %>" placeholder="Enter variable name">
                                </td>
                                <td  class="col-sm-4 col-sm-offset-2 no-padding">
                                    <input class="value change-input" type="text" value="<%- e.value ? e.value : '' %>" placeholder="Enter value">
                                </td>
                                <td>
                                    <div class="remove-env"></div>
                                </td>
                            </tr>
                            <% }) %>
                        </tbody>
                    </table>
                </div>
            </div>
            <% } %>
            <div class="col-sm-12 no-padding">
                <button type="button" class="add-env">Add fields</button>
            </div>
            <% if (env.length != 0){ %>
            <div class="col-sm-12 no-padding reset">
                <button type="button" class="reset-button">Reset values</button>
            </div>
            <% } %>
        </div>
    </div>
</div>
<div class="container nav-buttons">
    <div class="buttons pull-right ">
        <button class="go-to-ports gray">Back</button>
        <button class="next-step">Next</button>
    </div>
</div>
