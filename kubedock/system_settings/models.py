import json
from ..core import db
from ..exceptions import APIError


class SystemSettings(db.Model):
    """
    System-wide settings. Intended to be shown in web-interface as well.
    """
    __tablename__ = 'system_settings'

    id = db.Column(db.Integer, primary_key=True, nullable=False)
    name = db.Column(db.String(255), nullable=False, unique=True)
    value = db.Column(db.Text, nullable=True)
    label = db.Column(db.Text, nullable=True)
    description = db.Column(db.Text, default='')
    placeholder = db.Column(db.String, default='')
    options = db.Column(db.String, nullable=True)
    setting_group = db.Column(db.Text, nullable=True)

    @classmethod
    def get_all(cls):
        result = []
        for row in cls.query.all():
            data = {k: v
                    for k, v in vars(row).items()
                    if not k.startswith('_')}
            if data['options']:
                data['options'] = json.loads(data['options'])
            result.append(data)
        return result

    @classmethod
    def get(cls, id):
        entry = cls.query.get(id)
        if entry is None:
            raise APIError('No such resource', 404)
        data = {k: v for k, v in vars(entry).items() if not k.startswith('_')}
        if data['options']:
            data['options'] = json.loads(data['options'])
        return data

    @classmethod
    def get_by_name(cls, name):
        entry = cls.query.filter_by(name=name).first()
        if entry is None:
            return ''
        return entry.value

    @classmethod
    def set(cls, id, value):
        entry = cls.query.get(id)
        if entry is None:
            raise APIError('No such resource', 404)
        entry.value = value
        db.session.commit()

    @classmethod
    def set_by_name(cls, name, value, commit=True):
        entry = cls.query.filter_by(name=name).first()
        if entry is None:
            raise APIError('No such resource', 404)
        entry.value = value
        if commit:
            db.session.commit()
