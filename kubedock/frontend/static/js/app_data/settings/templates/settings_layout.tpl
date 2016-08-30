<div id="nav"></div>
<div>
    <div class="breadcrumbs-wrapper">
        <div class="container breadcrumbs" id="breadcrumbs">
            <ul class="breadcrumb">
                <li class="active">
                    <div>Settings</div>
                </li>
            </ul>
        </div>
    </div>
    <div class="container">
        <div class="row">
            <div class="col-sm-12 col-md-2 sidebar">
                <ul class="nav nav-sidebar list-unstyled" >
                    <% if(user.get('rolename')  === 'Admin') { %>
                        <li class="general"><span>General</span></li>
                        <li class="license"><span>License</span></li>
                        <li class="domain"><span>DNS provider</span></li>
                        <li class="billing"><span>Billing</span></li>
                    <% } %>
                    <li class="profile"><span>Profile</span></li>
                </ul>
            </div>
            <div id="details_content" class="col-sm-12 col-md-10">
                <div class="row placeholders">
                </div>
            </div>
        </div>
    </div>
</div>
