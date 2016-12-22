<div class="container" id="add-image">
    <div class="col-md-3 col-sm-12 sidebar no-padding">
        <ul class="nav nav-sidebar">
            <li role="presentation" class="success">Choose image</li>
            <li role="presentation" class="success">Set up image</li>
            <li role="presentation" class="success">Environment variables</li>
            <li role="presentation" class="active">Final setup</li>
        </ul>
    </div>
    <div id="details_content" class="col-md-9 col-sm-12 set-up-image no-padding">
        <div id="tab-content" class="clearfix complete">
            <div class="col-md-6 no-padding left">
                <div class="row policy">
                    <div class="col-xs-12">
                        <label>Restart policy</label>
                    </div>
                    <div class="col-xs-<%= containers.length > 1 ? '11' : '12 no-padding-right' %>">
                        <select class="restart-policy selectpicker"<%= containers.length > 1 ? ' disabled' : '' %>>
                            <% _.each(restart_policies, function(value, key) {%>
                            <option value="<%- key %>"<%= key === restart_policy ? ' selected' : '' %>><%- value %></option>
                            <% }) %>
                        </select>
                    </div>
                    <div class="col-xs-12 edit-polycy-description">Type will apply for each container</div>
                    <% if (containers.length > 1){ %>
                    <div class="col-xs-1 no-padding edit-policy" data-toggle="tooltip"
                        data-placement="left" title="Edit restart policy"></div>
                    <% } %>
                </div>
                <div class="row kube-type-wrapper">
                    <% if (containers.length > 1){ %>
                    <label class="col-xs-11">Kube Type</label>
                    <div class="col-xs-11">
                        <select class="kube_type selectpicker" id="extra-options" disabled>
                    <% } else { %>
                    <div class="col-xs-12 no-padding-right">
                        <label>Kube Type</label>
                        <select class="kube_type selectpicker" id="extra-options">
                    <% } %>
                            <% kubeTypes.each(function(kubeType){ %>
                            <option value="<%- kubeType.id %>" <%= kubeType.disabled ? '' : 'disabled'%>>
                                <%- kubeType.formattedName %>
                            </option>
                            <% }) %>
                        </select>
                    </div>
                    <% if (containers.length > 1){ %>
                    <div class="col-xs-1 no-padding edit-kube-type" data-toggle="tooltip"
                    data-placement="left" title="Edit pod kube type"></div>
                    <% } %>
                    <div class="col-xs-12 edit-kube-type-description">Type will apply for each container</div>
                </div>
            </div>
            <div class="col-md-5 col-md-offset-1 col-sm-offset-0  servers">
                <div>CPU: <span id="total_cpu"><%- limits.cpu %></span></div>
                <div>RAM: <span id="total_ram"><%- limits.ram %></span></div>
                <div>HDD: <span id="hdd_data"><%- limits.hdd %></span></div>
            </div>
            <div class="col-md-12 total-wrapper">
                <table id="pod-payment-table">
                    <thead>
                       <tr>
                           <th class="col-xs-5 no-padding">Container name</th>
                           <th class="col-xs-4 no-padding">Number of Kubes</th>
                           <th class="col-xs-2 no-padding">Price / <%- pkg.get('period') %></th>
                           <th class="col-xs-1 no-padding"></th>
                       </tr>
                    </thead>
                    <tbody class="wizard-containers-list"></tbody>
                </table>
                <% if (isPerSorage) { %>
                    <table>
                        <thead>
                           <tr>
                               <th class="col-xs-5 no-padding">Storage name</th>
                               <th class="col-xs-4 no-padding">Size</th>
                               <th class="col-xs-2 no-padding"></th>
                               <th class="col-xs-1 no-padding"></th>
                           </tr>
                        </thead>
                        <tbody>
                            <% _.each(persistentDrives, function(pd){ %>
                                <tr>
                                    <td><b><%- pd.get('name') %></b></td>
                                    <td><%- pd.get('size') %> GB</td>
                                    <td>
                                        <span class="pstorage_price"><%= formatPrice( pkg.get('price_pstorage') * pd.get('size')) %></span>
                                    </td>
                                    <td class="actions text-right">
                                        <% if (pd.get('size') !== 1) { %>
                                            <span class="help" data-toggle="tooltip" data-placement="left" title="<%= formatPrice( pkg.get('price_pstorage') ) %> per 1 GB"></span>
                                        <% } %>
                                    </td>
                                </tr>
                            <% }) %>
                        </tbody>
                    </table>
                <% } %>
                <% if (isPublic && (typeof domain == 'undefined' || domain == null)) { %>
                    <table>
                        <thead>
                           <tr>
                               <th class="col-xs-5 no-padding">Public IP`s</th>
                               <th class="col-xs-4 no-padding">Quantity</th>
                               <th class="col-xs-2 no-padding"></th>
                               <th class="col-xs-1 no-padding"></th>
                           </tr>
                        </thead>
                        <tbody>
                            <% if (isPublic) { %>
                                <tr>
                                    <td><b>IPv4 public IP</b></td>
                                    <td>1</td>
                                    <td><span id="ipaddress_price"><%= formatPrice( pkg.get('price_ip') ) %></td>
                                    <td></td>
                                </tr>
                            <% } %>
                        </tbody>
                    </table>
                <% } %>
            </div>
            <div class="col-md-12 payment-summary no-padding text-right">
                <% if (edited && diffTotalPrice > 0){ %>
                    <div class="upgrade-total-price">
                        <p>Additional costs: <span id="total_price"><%- formatPrice(diffTotalPrice) %> / <%- pkg.get('period') %></span></p>
                    </div>
                    <div class="upgrade-diff-price">
                        New total price: <span id="total_price"><%- formatPrice(totalPrice) %> / <%- pkg.get('period') %></span>
                    </div>
                <% } else { %>
                    <div class="upgrade-diff-price">
                        Total price: <span id="total_price"><%- formatPrice(totalPrice) %> / <%- pkg.get('period') %></span>
                    </div>
                <% } %>
            </div>
            <div class="buttons col-md-12 no-padding text-right">
                <% if (edited){ %>
                    <button class="cancel-edit gray">Cancel</button>
                <% } %>
                <% if (wizardState.container){ %>
                    <button class="prev-step gray">Back</button>
                <% } %>
                <button class="add-more blue">Add more containers</button>
                <% if (!edited){ %>
                    <button class="save-container blue">Save</button>
                    <% if (hasBilling && !payg){ %>
                        <button class="pay-and-run-container blue">Pay and Run</button>
                    <% } %>
                <% } else { %>
                    <% if (hasBilling && !payg && diffTotalPrice > 0){ %>
                        <button class="save-changes gray">Save for later</button>
                        <button class="pay-and-apply-changes blue">Pay and Apply changes *</button>
                    <% } else { %>
                        <button class="save-changes blue">Save</button>
                    <% } %>
                <% } %>
            </div>
            <% if (edited && hasBilling && !payg && diffTotalPrice > 0){ %>
                <div class="col-md-12 no-padding text-right">
                    <span class="edit-pod-note" style="clear: both; font-size: 12px">
                        * Pod will be restarted
                    </span>
                </div>
            <% } %>
        </div>
    </div>
</div>
