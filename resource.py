from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import create_engine

Base = declarative_base()
engine = create_engine('sqlite:///resource_database.sqlite3')
Session_db = sessionmaker(bind=engine)
Pages = {
    'training': {'header': 'Train Your Mind', 'index': 0},
    'decks': {'header': 'Deck Managements', 'index': 1},
    'explore': {'header': 'Explore Public Decks', 'index': 2},
    'progress': {'header': 'Track Your Progress', 'index': 3},
    'activities': {'header': 'Your Past Activities', 'index': 4}
}

Icons = {
    'training': 'bi bi-activity',
    'decks': 'bi bi-stack',
    'explore': 'bi bi-lightbulb',
    'progress': 'bi bi-graph-up-arrow',
    'activities': 'bi bi-receipt'
}


class User(Base):
    __tablename__ = 'user'
    user_id = Column(Integer, autoincrement=True, primary_key=True)
    user_name = Column(String, unique=True)
    password = Column(String, nullable=False)
    f_name = Column(String, nullable=False)
    l_name = Column(String)
    security_ques = Column(Integer, nullable=False)
    security_ans = Column(String, nullable=False)


class Genre(Base):
    __tablename__ = 'genre'
    genre_id = Column(Integer, autoincrement=True, primary_key=True)
    name = Column(String, unique=True, nullable=False)


class Deck(Base):
    __tablename__ = 'deck'
    deck_id = Column(Integer, autoincrement=True, primary_key=True)
    genre_id = Column(Integer, ForeignKey(Genre.genre_id), nullable=False)
    name = Column(String, nullable=False)
    desc = Column(String)


class Card(Base):
    __tablename__ = 'card'
    card_id = Column(Integer, autoincrement=True, primary_key=True)
    deck_id = Column(Integer, ForeignKey(Deck.deck_id), nullable=False)
    question = Column(String, nullable=False)
    answer = Column(String, nullable=False)


class UserDeck(Base):
    __tablename__ = 'user_deck'
    id = Column(Integer, autoincrement=True, primary_key=True)
    user_id = Column(Integer, ForeignKey(User.user_id), nullable=False)
    deck_id = Column(Integer, ForeignKey(Deck.deck_id), nullable=False)
    privacy = Column(String, nullable=False)
    attempts = Column(Integer, nullable=False)
    la_dt = Column(String)


class UserCard(Base):
    __tablename__ = 'user_card'
    id = Column(Integer, autoincrement=True, primary_key=True)
    user_id = Column(Integer, ForeignKey(User.user_id), nullable=False)
    card_id = Column(Integer, ForeignKey(Card.card_id), nullable=False)
    c_attempt = Column(Integer, nullable=False, default=0)
    w_attempt = Column(Integer, nullable=False, default=0)


class Activity(Base):
    __tablename__ = 'activity'
    id = Column(Integer, autoincrement=True, primary_key=True)
    user_id = Column(Integer, ForeignKey(User.user_id), nullable=False)
    a_type = Column(String, nullable=False)
    target = Column(String, nullable=False)
    date_time = Column(String, nullable=False)


def get_activity_content(a_type, target, a_id):
    activity_titles = {
        'REGISTRATION': 'Registered in this application. \n User Name: ' + target,
        'LOGIN': 'Logged in to the Flash Card Application. \n User Name: ' + target,
        'LOGOUT': 'Logged out from the Flash Card Application. \n User Name: ' + target,
        'IMPORT': 'Imported the deck - "' + target + '" in your collection from public repositories',
        'CREATE': 'Created the deck - "' + target + '" and added in your collection successfully',
        'UPDATE': 'Updated the contents of the deck - "' + target + '"',
        'DELETE': 'Deleted the deck - "' + target + '" from your collection',
        'ATTEMPT': 'You attempted the deck - "' + target + '"'
    }
    if a_type in activity_titles:
        return activity_titles[a_type]
    else:
        return 'This activity is miscellaneous. Please contact the Administration. Activity ID: ' + a_id


class Error:
    messages = {
        'default': 'Something went wrong',
        'ERR001': 'User doesn\'t exist',
        'ERR002': 'Invalid password',
        'ERR003': 'Authentication failed',
        'ERR004': 'Registration unsuccessful',
        'ERR005': 'Unauthorized request',
        'ERR006': 'No such Forms'
    }
    descriptions = {
        'ERR001': 'It seems that you are not registered. Kindly go back or register yourself to continue',
        'ERR002': 'You have entered wrong password. Go back to try again or reset your password here',
        'ERR003': 'The combination of security question and answer doesn\'t match. You can go back to try again or '
                  'you can register with another username (You will lost your progress in this case). Unfortunately, '
                  'there is no other way to reset your password! Sorry!',
        'ERR004': 'It seems that another user exists with the same username. Try another username',
        'ERR005': 'You aren\'t logged-in. Please login to continue',
        'ERR006': 'The requested form wasn\'t found on the server. Please check you\'ve entered the correct url'
    }

    actions = {
        'default': [],
        'ERR001': [
            {'name': 'Register', 'url': '/register'}
        ],
        'ERR002': [
            {'name': 'Reset Password', 'url': '/reset'}
        ],
        'ERR005': [
            {'name': 'Log In', 'url': '/login'}
        ],
        'ERR006': [
            {'name': 'Go to Dashboard', 'url': '/dashboard'}
        ]
    }

    def __init__(self, code):
        if code in Error.messages.keys():
            self.msg = Error.messages[code]
        else:
            self.msg = Error.messages['default']
        if code in Error.descriptions.keys():
            self.desc = Error.descriptions[code]
        else:
            self.desc = code
        if code in Error.actions.keys():
            self.action = Error.actions[code]
        else:
            self.action = Error.actions['default']


class PermissionChanged(Exception):
    pass
