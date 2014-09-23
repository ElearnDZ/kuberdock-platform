from flask import g, redirect, url_for, request, flash, render_template, abort
from flask.views import MethodView
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config import DATABASE_URL
from models import User, Container
from forms import RegisterUserForm


engine = create_engine(DATABASE_URL)
Session = sessionmaker(engine)
session = Session()

def add_or_none(obj):
    try:
        session.add(obj)
        session.commit()
        return True
    except:
        session.rollback()
    finally:
        session.close()
    return False


class IndexView(MethodView):
    def get(self):
        q = session.query(User)
        return render_template('index.html', users=q.all())

class RegisterUserView(MethodView):
    def get(self):
        form = RegisterUserForm()
        return render_template('register.html', form=form)

    def post(self):
        form = RegisterUserForm(request.form)
        if form.validate():
            user = User(form.login.data, form.email.data,
                        form.fullname.data, form.password.data)
            if add_or_none(user):
                flash('Thanks for registering')
                return redirect(url_for('index'))
            else:
                g.alert_type = 'danger'
                flash('"{0}" already registered'.format(form.email.data))
        return render_template('register.html', form=form)


class UserView(MethodView):
    def get(self, user_id):
        user = session.query(User).get(user_id)
        if not user: abort(404)
        return render_template('user.html', user=user)
