import json
from datetime import datetime
from flask import render_template_string
from flask.ext.login import current_user
from sqlalchemy.ext.orderinglist import ordering_list

from ..core import db
from ..rbac import get_user_role
from ..models_mixin import BaseModelMixin
from .utils import slugify


class Menu(BaseModelMixin, db.Model):
    __tablename__ = 'menus'

    REGION_NAVBAR, REGION_FOOTER = 1, 2
    REGIONS = (
        (REGION_NAVBAR, 'navbar'),
        (REGION_FOOTER, 'footer'),
    )

    id = db.Column(
        db.Integer, primary_key=True, autoincrement=True, nullable=False)
    ts = db.Column(db.DateTime, default=datetime.now)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    region = db.Column(db.Integer, default=REGION_NAVBAR, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    items = db.relationship('MenuItem', backref=db.backref("menu"))
    is_active = db.Column(db.Boolean, default=True)

    def __unicode__(self):
        return self.name

    @classmethod
    def get_active(cls):
        menu_list = cls.filter_by(is_active=True)
        menus = dict([(m.region_repr, m) for m in menu_list])
        return menus

    @classmethod
    def get_active_json(cls):
        objects_list = [m.to_dict() for m in cls.filter_by(is_active=True)]
        return json.dumps(objects_list)

    def get_items(self, admin=None):
        items = MenuItem.filter_by(
            menu_id=self.id, parent_id=None).order_by(MenuItem.ordering).all()
        if not admin:
            role = get_user_role()
            items = [item for item in items if item.validate_role(role)]
        return items

    @classmethod
    def get_dynatree_list(cls):
        menu_list = cls.filter_by(is_active=True)
        menus = dict([(m.region_repr, m.to_dynatree()) for m in menu_list])
        return menus

    @property
    def region_repr(self):
        return dict(self.REGIONS)[self.region]

    def to_dict(self, include=None, exclude=None):
        return dict(
            id=self.id,
            ts=self.ts.isoformat(sep=' ')[:19],
            created_by_id=self.created_by_id,
            region=self.region,
            name=self.name,
            items=[item.to_dict(include=include, exclude=exclude)
                   for item in self.items]
        )

    def to_dynatree(self):
        return dict(
            key=self.id,
            title=self.name,
            children=[item.to_dynatree()
                      for item in self.get_items(admin=True)],
            unselectable=True,
            # href='menu/%s/' % self.id,
            data=dict(
                id=self.id,
                ts=self.ts.isoformat(sep=' ')[:19],
                name=self.name,
                created_by_id=self.created_by_id,
                region=self.region,
                t='menu',
                is_active=self.is_active
            )
        )

    def form_render(self):
        context = dict(
            regions=[dict(id=r[0], name=r[1]) for r in Menu.REGIONS],
            menu=self
        )
        return render_template_string('menus/inc/menu_form.html', **context)


class MenuItem(BaseModelMixin, db.Model):
    __tablename__ = 'menus_items'

    id = db.Column(
        db.Integer, primary_key=True, autoincrement=True, nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('menus_items.id'))
    children = db.relationship(
        'MenuItem', cascade="all",
        collection_class=ordering_list('ordering'),
        backref=db.backref("parent", remote_side='MenuItem.id'),
        order_by="MenuItem.ordering",)
    ts = db.Column(db.DateTime, default=datetime.now)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    path = db.Column(db.String(1000), nullable=True)
    menu_id = db.Column(db.Integer, db.ForeignKey('menus.id'))
    name = db.Column(db.String(255), nullable=False)
    page_id = db.Column(db.Integer, db.ForeignKey('pages.id'))
    ordering = db.Column(db.Integer, default=0)
    is_group_label = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    is_public = db.Column(db.Boolean, default=True)
    roles = db.Column(db.String)

    def __repr__(self):
        return "MenuItem(name=%r, id=%r, parent_id=%r)" % (
            self.name, self.id, self.parent_id)

    def parent_path(self):
        if self.parent_id is None:
            return
        return self.parent.get_absolute_url()

    def get_absolute_url(self):
        if self.page_id:
            return '/page/{0}'.format(self.page.slug)
        path = self.path
        if path is not None:
            if path.startswith('/'):
                return path
            elif self.parent_id:
                if self.parent.page:
                    return '{0}/{1}'.format(self.parent.get_absolute_url(), path)
                return path
        return '#'

    def get_roles(self):
        roles = json.loads(self.roles or "[]")
        return roles

    def validate_role(self, role):
        roles = self.get_roles()
        if not roles:
            return True
        return role in roles

    def get_children(self):
        role = get_user_role()
        return [item for item in self.children if item.validate_role(role)]

    def to_dict(self, include=None, exclude=None):
        page = self.page
        return dict(
            id=self.id,
            parent_id=self.parent_id,
            ts=self.ts.isoformat(sep=' ')[:19],
            created_by_id=self.created_by_id,
            parent_path=self.parent_path(),
            path=self.path,
            absolute_url=self.get_absolute_url(),
            menu_id=self.menu_id,
            name=self.name,
            page=page.id if page else None,
            ordering=self.ordering,
            is_group_label=self.is_group_label,
            is_active=self.is_active,
            roles=self.get_roles(),
            children=[(item.id, item.to_dict(include=include, exclude=None))
                      for item in self.children]
        )

    def to_dynatree(self):
        page = self.page
        return dict(
            key=self.id,
            # href='item/%s/' % self.id,
            title=self.name,
            children=[item.to_dynatree() for item in self.children],
            data=dict(
                id=self.id,
                name=self.name,
                parent_id=self.parent_id,
                ts=self.ts.isoformat(sep=' ')[:19],
                created_by_id=self.created_by_id,
                parent_path=self.parent_path(),
                path=self.path,
                absolute_url=self.get_absolute_url(),
                menu_id=self.menu_id,
                region=self.menu.region,
                region_repr=self.menu.region_repr,
                page=page.id if page else None,
                ordering=self.ordering,
                is_group_label=self.is_group_label,
                is_active=self.is_active,
                roles=self.get_roles(),
                t='item',
            )
        )

    def get_path(self):
        path = self.path or '#'
        return path

    def update(self, data, user_id):
        path = data.get('path')
        # if path:
        #     path = '/'.join([p for p in path.split('/') if p.strip()])
        name = data.get('name', '').strip()
        assign_page = data.get('assign_page') == 'true'
        unbind_page = data.get('unbind_page') == 'true'
        is_active = data.get('is_active') and data['is_active'] == 'true'
        if path != self.path:
            self.path = path
        if name and name != self.name:
            self.name = name
        roles = [role for role in data.get('roles', '').split(',') if role]
        self.roles = json.dumps(roles) if roles else None
        self.is_active = is_active
        self.save()

        # Update page
        if unbind_page and self.page_id:
            self.page.delete()
            self.page_id = None
            self.save()
        if assign_page or self.page_id:
            page_title = data.get('page_title', '').strip()
            page_slug = slugify(data.get('page_slug', '').strip())
            page_content = data.get('page_content', '').strip()
            if not page_title:
                raise ValueError('Page title is required')
            if not page_slug:
                raise ValueError('Page slug is required')
            if not page_content:
                raise ValueError('Page content is required')
            page = None
            if not self.page_id:
                page = Page.create(
                    created_by_id=user_id, slug=page_slug, title=page_title,
                    content=page_content)
            elif self.page_id:
                page = self.page
                is_page_modified = False
                if page_slug != page.slug:
                    page.slug = page_slug
                    is_page_modified = True
                if page_title != page.title:
                    page.title = page_title
                    is_page_modified = True
                if page_content != page.content:
                    page.content = page_content
                    is_page_modified = True
                if is_page_modified:
                    page.modified = datetime.now()
                    page.modified_by_id = user_id
            if page is not None:
                page.save()
                if not self.page_id:
                    self.page_id = page.id

    @classmethod
    def create_item(cls, data, user_id):
        region = data['region']
        menu = Menu.filter_by(region=region).first()
        item = cls(
            menu_id=menu.id, created_by_id=user_id, name=data['name'],
            path=data['path'])
        if int(data['parent']) > 0:
            item.parent_id = data['parent']
        item.update(data, user_id)
        return item

    def delete(self):
        for item in self.children:
            if item.page_id:
                item.page.delete()
            item.delete()
        super(MenuItem, self).delete()


    def __unicode__(self):
        return self.name


class Page(BaseModelMixin, db.Model):
    __tablename__ = 'pages'

    id = db.Column(
        db.Integer, primary_key=True, autoincrement=True, nullable=False)
    ts = db.Column(db.DateTime, default=datetime.now)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    modified = db.Column(db.DateTime)
    modified_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    menu_item = db.relationship('MenuItem', backref='page', lazy='dynamic')
    slug = db.Column(db.String(255), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)

    def __unicode__(self):
        return self.title

    @property
    def roles(self):
        return self.menu_item.first().get_roles()

    def has_access(self, user_role):
        roles = self.roles
        if roles is None or len(roles) == 0:
            return True
        return user_role in roles

    def to_dict(self, include=None, exclude=None):
        item = self.menu_item.first()
        return dict(
            id=self.id,
            ts=self.ts.isoformat(sep=' ')[:19],
            created_by_id=self.created_by_id,
            modified=self.modified.isoformat(sep=' ')[:19] \
                if self.modified else None,
            modified_by_id=self.modified_by_id,
            menu_item=item.id if item else None,
            slug=self.slug,
            title=self.title,
            content=self.content
        )
