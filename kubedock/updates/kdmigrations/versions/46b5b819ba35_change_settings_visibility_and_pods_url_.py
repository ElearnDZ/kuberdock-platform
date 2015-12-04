"""change settings visibility and pods url path

Revision ID: 46b5b819ba35
Revises: 18d04a76914f
Create Date: 2015-12-06 16:22:28.630713

"""

# revision identifiers, used by Alembic.
revision = '46b5b819ba35'
down_revision = '18d04a76914f'

from alembic import op
import sqlalchemy as sa


Session = sa.orm.sessionmaker()
Base = sa.ext.declarative.declarative_base()


class Role(Base):
    __tablename__ = 'rbac_role'

    id = sa.Column(sa.Integer, primary_key=True)
    rolename = sa.Column(sa.String(64), unique=True)


class MenuItemRole(Base):
    __tablename__ = 'menuitem_roles'

    id = sa.Column(
        sa.Integer, primary_key=True, autoincrement=True, nullable=False)
    menuitem_id = sa.Column(sa.Integer, sa.ForeignKey('menus_items.id'))
    role_id = sa.Column(sa.Integer, sa.ForeignKey('rbac_role.id'))
    role = sa.orm.relationship('Role', backref=sa.orm.backref('menus_assocs'))
    menuitem = sa.orm.relationship('MenuItem', backref=sa.orm.backref('roles_assocs'))


class MenuItem(Base):
    __tablename__ = 'menus_items'

    id = sa.Column(
        sa.Integer, primary_key=True, autoincrement=True, nullable=False)
    name = sa.Column(sa.String(255), nullable=False)
    path = sa.Column(sa.String(1000), nullable=True)


def upgrade():
    session = Session(bind=op.get_bind())
    pods = session.query(MenuItem).filter(MenuItem.name=='Pods').one()
    pods.path = '/pods/'
    admin = session.query(Role).filter(Role.rolename=='Admin').one()
    for i in session.query(MenuItemRole).filter(MenuItemRole.role!=admin):
        if i.menuitem.name=='Settings':
            session.delete(i)
    session.commit()


def downgrade():
    session = Session(bind=op.get_bind())
    pods = session.query(MenuItem).filter(MenuItem.name=='Pods').one()
    pods.path = '/'
    setts = session.query(MenuItem).filter(MenuItem.name=='Settings').first()
    if setts is not None:
        session.add_all(MenuItemRole(role=role, menuitem=setts)
            for role in session.query(Role).filter(Role.rolename.in_(['User', 'TrialUser'])))
    session.commit()