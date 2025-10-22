from extensions import *
from sqlalchemy.dialects.postgresql import TSVECTOR
import os

class City(db.Model):
    __tablename__ = "city"

    id = db.Column(db.Integer, primary_key=True)
    city_name = db.Column(db.String(100), nullable=False)
    ascii_name = db.Column(db.String(100), nullable=False)
    admin1 = db.Column(db.String(100))
    admin2 = db.Column(db.String(100))
    admin3 = db.Column(db.String(100))
    admin4 = db.Column(db.String(100))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    zipcode = db.Column(db.String(20))  # string legyen
    country_code = db.Column(db.String(2), db.ForeignKey('countries.code'))
    if os.environ.get('DB_TYPE') == 'postgres':
        search_vector = db.Column(TSVECTOR)

    if os.environ.get("DB_TYPE") == "postgres":
        score_expr = func.greatest(
            func.similarity(City.city_name, term),
            func.similarity(City.ascii_name, term),
            func.similarity(City.admin1, term),
            func.similarity(City.admin2, term),
            func.similarity(City.admin3, term)
        )
    else:
        score_expr = func.length(func.replace(City.city_name, term, term))  # nagyon egyszerű mérőszám SQLite-on


class CityZipcode(db.Model):
    __tablename__ = "city_zipcodes"

    id = db.Column(db.Integer, primary_key=True)
    city_id = db.Column(db.Integer, db.ForeignKey("city.id"), nullable=False)
    zipcode = db.Column(db.String(20), nullable=False)

    city = db.relationship("City", backref=db.backref("zipcodes", lazy=True))


class AlterName(db.Model):
    __tablename__ = "alter_names"

    id = db.Column(db.Integer, primary_key=True)
    city_id = db.Column(db.Integer, db.ForeignKey('city.id'), nullable=False)
    alternames = db.Column(db.String(1000), nullable=False)
    if os.environ.get('DB_TYPE') == 'postgres':
        search_vector = db.Column(TSVECTOR)


class Country(db.Model):
    __tablename__ = 'countries'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    code = db.Column(db.String(2), unique=True, nullable=False)
    capital = db.Column(db.String(255), nullable=False)
    region = db.Column(db.String(2), nullable=False)
    currency_code = db.Column(db.String(3), nullable=False)
    language_code = db.Column(db.String(2), nullable=False)
    flag_url = db.Column(db.String(255), nullable=False)
    dialling_code = db.Column(db.String(10), nullable=False)
    iso_code = db.Column(db.String(3), nullable=False)

    cities = db.relationship('City', backref='country', lazy=True, primaryjoin="Country.code==foreign(City.country_code)")
