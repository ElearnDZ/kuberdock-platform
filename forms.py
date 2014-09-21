from wtforms import Form, BooleanField, StringField, validators


class RegisterUserForm(Form):
    login = StringField('Login', [validators.Length(min=4, max=16)])
    fullname = StringField('Fullname', [validators.Length(min=4, max=64)])
    password = StringField('Password', [validators.Length(min=4, max=64)])
    email = StringField('Email Address', [validators.Length(min=6, max=64)])
