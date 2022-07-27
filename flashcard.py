from flask import Flask, request, abort, session, jsonify
from flask import redirect, url_for, render_template, make_response
from resource import User, Deck, Card, UserDeck, UserCard, Genre, Activity
from resource import Error, Base, engine, Session_db, Icons
from resource import Pages, PermissionChanged, get_activity_content
from flask_session import Session
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException
from sqlalchemy import or_, and_, desc, func
from json import JSONDecodeError
from datetime import datetime
import json
import traceback
import random
import string

app = Flask(__name__)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)
Base.metadata.create_all(engine)


def auth():
    if not session.get('user'):
        abort(401, 'ERR005')
    if request.cookies.get('token') != session.get('user').get('token'):
        abort(401, 'ERR005')


def get_page(page):
    doc = 'Empty Content'
    db_session = Session_db()
    if page == 'explore' or page == 'decks' or page == 'training':
        user = db_session.query(User).filter_by(user_name=session.get('user').get('user_name')).first()
        decks_ = []
        if page == 'explore':
            a_deck_ids = [d.deck_id for d in db_session.query(UserDeck).filter(UserDeck.user_id == user.user_id).all()]
            decks_ = db_session.query(Deck, UserDeck, Genre) \
                .select_from(Deck).join(UserDeck).join(Genre) \
                .filter(UserDeck.user_id != user.user_id, UserDeck.privacy == 'public',
                        ~UserDeck.deck_id.in_(a_deck_ids)).all()
            doc = render_template('explore.html', decks_count=len(decks_))
        elif page == 'decks' or page == 'training':
            decks_ = db_session.query(Deck, UserDeck, Genre) \
                .select_from(Deck).join(UserDeck).join(Genre) \
                .filter(UserDeck.user_id == user.user_id).all()
            db_session.close()
            if page == 'decks':
                doc = render_template('decks.html', decks_count=len(decks_))
            elif page == 'training':
                doc = render_template('training.html', decks_count=len(decks_))
        #############################################################################################################
        for deck, user_deck, genre in decks_:
            uc_ref = db_session.query(UserDeck.user_id).select_from(UserDeck) \
                .filter(UserDeck.privacy != 'external').filter(UserDeck.deck_id == deck.deck_id).first()
            user_count = db_session.query(UserDeck).filter(UserDeck.deck_id == deck.deck_id).count()
            card_count = db_session.query(Card).filter(Card.deck_id == deck.deck_id).count()
            creator = db_session.query(User).filter_by(user_id=uc_ref.user_id).first()
            doc += render_template('deck.html', creator=creator, user_count=user_count, deck=deck, page=page,
                                   card_count=card_count, genre=genre, user_deck=user_deck)
        db_session.close()
    elif page == 'progress':
        user = db_session.query(User).filter_by(user_name=session.get('user').get('user_name')).first()
        decks_ = db_session.query(Genre, Deck, UserDeck).select_from(Deck) \
            .join(UserDeck).join(Genre).filter(UserDeck.user_id == user.user_id) \
            .order_by(desc(UserDeck.la_dt)).all()
        doc = render_template('progress.html', decks_count=len(decks_))
        for g, d, ud in decks_:
            ucs = db_session.query(func.sum(UserCard.c_attempt), func.sum(UserCard.w_attempt))\
                .select_from(UserCard).join(Card).filter(UserCard.user_id == user.user_id) \
                .filter(Card.deck_id == d.deck_id).group_by(Card.deck_id).first()
            card_count = db_session.query(Card).filter(Card.deck_id == d.deck_id).count()
            accuracy = inaccuracy = 0
            if ud.attempts != 0:
                accuracy = round(ucs[0]*100/(ud.attempts * card_count), 2)
                inaccuracy = round(ucs[1]*100/(ud.attempts * card_count), 2)
            doc += render_template('progress_card.html', deck=d, genre=g, user_deck=ud,
                                   accuracy=accuracy, inaccuracy=inaccuracy)
        db_session.close()
    elif page == 'activities':
        doc = ''
        user = db_session.query(User).filter_by(user_name=session.get('user').get('user_name')).first()
        activities = db_session.query(Activity)\
            .filter(Activity.user_id == user.user_id).order_by(desc(Activity.date_time)).all()
        for activity in activities:
            doc += render_template('activity_form.html', activity=activity,
                                   activity_content=get_activity_content(activity.a_type, activity.target, activity.id))
        db_session.close()
    return {
        'index': Pages.get(page).get('index'),
        'title': page.capitalize(),
        'header': Pages.get(page).get('header'),
        'content': doc
    }


@app.route('/')
def index():
    if not session.get('user'):
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))


@app.route('/dashboard')
@app.route('/dashboard/<page>')
def dashboard(page=None):
    auth()
    if page is None:
        return make_response(render_template('index.html',
                                             header='Your Dashboard',
                                             icons=Icons,
                                             pages=Pages.keys()), 200)
    else:
        if page not in Pages:
            abort(404)
        return jsonify(get_page(page))


@app.route('/getuser')
def getuser():
    auth()
    db_session = Session_db()
    user = db_session.query(User).filter_by(user_name=session.get('user').get('user_name')).first()
    db_session.close()
    return {
        'first_name': user.f_name,
        'last_name': user.l_name,
        'user_name': user.user_name
    }


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('register.html', title='Registration')
    elif request.method == 'POST':
        db_session = Session_db()
        r = db_session.query(User).filter_by(user_name=request.form['user']).first()
        if r is not None:
            db_session.close()
            abort(409, 'ERR004')
        user = User(f_name=request.form['fname'],
                    l_name=request.form['lname'],
                    user_name=request.form['user'],
                    password=request.form['pass'],
                    security_ques=request.form['secques'],
                    security_ans=request.form['secans'])
        db_session.add(user)
        db_session.flush()
        db_session.add(Activity(user_id=user.user_id, a_type='REGISTRATION', target=user.user_name,
                                date_time=datetime.utcnow().strftime("%A, %B-%d %Y, %H:%M:%S UTC")))
        db_session.commit()
        db_session.close()
        return redirect(url_for('login'))


@app.route('/reset', methods=['GET', 'POST'])
def reset():
    if request.method == 'GET':
        return render_template('register.html', title='Reset Your Password')
    elif request.method == 'POST':
        db_session = Session_db()
        r = db_session.query(User).filter_by(user_name=request.form['user']).first()
        print(r.security_ques, r.security_ans)
        print(request.form['secques'], request.form['secans'])
        if r is None:
            db_session.close()
            abort(404, 'ERR001')
        if int(r.security_ques) == int(request.form['secques']) and str(r.security_ans) == str(request.form['secans']):
            r = db_session.query(User).filter_by(user_name=request.form['user']).first()
            r.password = request.form['pass']
            db_session.commit()
            db_session.close()
            return redirect(url_for('login'))
        else:
            db_session.close()
            abort(401, 'ERR003')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    elif request.method == 'POST':
        db_session = Session_db()
        user = db_session.query(User).filter_by(user_name=request.form['user']).first()
        if user is None:
            abort(404, 'ERR001')

        if user.password != request.form['pass']:
            abort(401, 'ERR002')

        session['user'] = {
            'token': ''.join(random.choices(string.digits + string.ascii_letters, k=12)),
            'user_name': user.user_name
        }
        db_session.add(Activity(user_id=user.user_id, a_type='LOGIN', target=user.user_name,
                                date_time=datetime.utcnow().strftime("%A, %B-%d %Y, %H:%M:%S UTC")))
        db_session.commit()
        db_session.close()
        res = make_response(redirect('/'))
        res.set_cookie('token', session.get('user').get('token'))
        return res


@app.route('/logout')
def logout():
    auth()
    db_session = Session_db()
    user = db_session.query(User).filter(User.user_name == session['user']['user_name']).first()
    db_session.add(Activity(user_id=user.user_id, a_type='LOGOUT', target=user.user_name,
                            date_time=datetime.utcnow().strftime("%A, %B-%d %Y, %H:%M:%S UTC")))
    db_session.commit()
    db_session.close()
    session['user'] = None
    return make_response(redirect(url_for('login')))


@app.route('/explore', methods=['PUT'])
def explore():
    auth()
    if 'rtype' not in request.args or request.args['rtype'] != 'add' or 'id' not in request.args:
        abort(400)

    if request.method == 'PUT':
        db_session = Session_db()
        deck = db_session.query(Deck).filter_by(deck_id=request.args['id']).first()
        deckname = deck.name
        try:
            user = db_session.query(User).filter_by(user_name=session.get('user').get('user_name')).first()
            ud = db_session.query(UserDeck) \
                .filter(UserDeck.privacy != 'external', UserDeck.deck_id == deck.deck_id).first()
            if ud.privacy != 'public':
                print(ud.privacy)
                raise PermissionChanged
            user_deck = UserDeck(user_id=user.user_id, deck_id=deck.deck_id, privacy='external', attempts=0)
            cards = db_session.query(Card).filter(Card.deck_id == deck.deck_id).all()
            for card in cards:
                user_card = UserCard(user_id=user.user_id, card_id=card.card_id, c_attempt=0, w_attempt=0)
                db_session.add(user_card)
                db_session.flush()
            db_session.add(user_deck)
            db_session.add(Activity(user_id=user.user_id, a_type='IMPORT', target=deck.name,
                                    date_time=datetime.utcnow().strftime("%A, %B-%d %Y, %H:%M:%S UTC")))
            db_session.flush()
        except SQLAlchemyError:
            db_session.rollback()
            db_session.close()
            abort(500)
        except PermissionChanged:
            db_session.rollback()
            db_session.close()
            return make_response('The access of ' + deckname + ' has been restricted by the creator.', 403)
        else:
            db_session.commit()
            return make_response("The deck " + deckname + " is successfully added to your collection.", 200)
        finally:
            db_session.close()


@app.route('/decks', methods=['GET', 'POST', 'DELETE'])
def decks():
    auth()
    if 'rtype' not in request.args \
            or request.args.get('rtype') not in ['create', 'edit', 'delete', 'getcard']:
        abort(400)
    if request.args['rtype'] in ['edit', 'delete'] and 'id' not in request.args:
        abort(400)
    if (request.args['rtype'] != 'delete' and request.method == 'DELETE') or \
            (request.method != 'DELETE' and request.args['rtype'] == 'delete'):
        abort(400)
    if request.args['rtype'] == 'delete' and 'entity' not in request.args:
        abort(400)
    if request.args['rtype'] == 'delete' and request.args['entity'] not in ['card', 'deck']:
        abort(400)
    if request.args['rtype'] == 'getcard' and request.method != 'GET':
        abort(400)
    #######################################################################################################
    if request.method == 'GET':
        db_session = Session_db()
        if request.args['rtype'] == 'create':
            db_session = Session_db()
            genres = db_session.query(Genre).all()
            db_session.close()
            return render_template('deck_form.html', request='create', genres=genres)
        elif request.args['rtype'] == 'edit':
            deck_id = request.args['id']
            deck = db_session.query(Deck).filter_by(deck_id=deck_id).first()
            genres = db_session.query(Genre).all()
            cards = db_session.query(Card).join(Deck).filter(Deck.deck_id == deck_id).all()
            user = db_session.query(User).filter_by(user_name=session.get('user').get('user_name')).first()
            user_deck = db_session.query(UserDeck).filter_by(user_id=user.user_id, deck_id=deck_id).first()
            db_session.close()
            page = render_template('deck_form.html', request='edit', deck=deck, genres=genres, user_deck=user_deck)
            for card in cards:
                page += render_template('card_form.html', card=card, state='old')
            return make_response(page, 200)
        elif request.args['rtype'] == 'getcard':
            db_session.close()
            return render_template('card_form.html', state='new')
    #######################################################################################################
    elif request.method == 'POST':
        db_session = Session_db()
        try:
            data = json.loads(request.data)
            ######################################################################
            if 'genre' not in data or data['genre'] == '':
                genre_name = data['newgenre']
            else:
                genre_name = data['genre']

            genre = db_session.query(Genre).filter_by(name=genre_name).first()
            if not genre:
                genre = Genre(name=genre_name)
                db_session.add(genre)
            db_session.flush()
            ######################################################################################
            deck = None
            if request.args['rtype'] == 'create':
                deck = Deck(name=data['name'], genre_id=genre.genre_id, desc=data['desc'])
                db_session.add(deck)
            elif request.args['rtype'] == 'edit':
                deck_id = request.args['id']
                deck = db_session.query(Deck).filter_by(deck_id=deck_id).first()
                deck.genre_id = genre.genre_id
                deck.name = data['name']
                deck.desc = data['desc']
            db_session.flush()
            ############################################################################################
            user = db_session.query(User).filter_by(user_name=session.get('user').get('user_name')).first()
            if request.args['rtype'] == 'create':
                db_session.add(Activity(user_id=user.user_id, a_type='CREATE', target=deck.name,
                                        date_time=datetime.utcnow().strftime("%A, %B-%d %Y, %H:%M:%S UTC")))
                user_deck = UserDeck(user_id=user.user_id, deck_id=deck.deck_id, privacy=data['privacy'], attempts=0)
                db_session.add(user_deck)
            elif request.args['rtype'] == 'edit':
                db_session.add(Activity(user_id=user.user_id, a_type='UPDATE', target=deck.name,
                                        date_time=datetime.utcnow().strftime("%A, %B-%d %Y, %H:%M:%S UTC")))
                user_deck = db_session.query(UserDeck).filter_by(deck_id=deck.deck_id, user_id=user.user_id).first()
                user_deck.privacy = data['privacy']
                if data['privacy'] == 'private':
                    db_session.query(UserDeck).filter(UserDeck.user_id != user.user_id,
                                                      UserDeck.deck_id == deck.deck_id).delete()
                    cards = db_session.query(Card).filter(Card.deck_id == deck.deck_id).all()
                    for card in cards:
                        db_session.query(UserCard).filter(UserCard.user_id != user.user_id,
                                                          UserCard.card_id == card.card_id).delete()
            db_session.flush()
            #################################################################################################
            for card in data['cards']:
                if card['state'] == 'new':
                    c = Card(deck_id=deck.deck_id, question=card['question'], answer=card['answer'])
                    db_session.add(c)
                    db_session.flush()
                    uc = UserCard(user_id=user.user_id, card_id=c.card_id, c_attempt=0, w_attempt=0)
                    db_session.add(uc)
                    db_session.flush()
                elif card['state'] == 'old':
                    c = db_session.query(Card).filter_by(card_id=card['cid']).first()
                    c.question = card['question']
                    c.answer = card['answer']
                    db_session.flush()
            ###################################################################################################
        except SQLAlchemyError:
            db_session.rollback()
            db_session.close()
            traceback.print_exc()
            abort(500)
        except JSONDecodeError:
            db_session.rollback()
            db_session.close()
            traceback.print_exc()
            abort(500)
        except KeyError:
            db_session.rollback()
            db_session.close()
            traceback.print_exc()
            abort(500)
        else:
            db_session.commit()
        finally:
            db_session.close()

            resp_msg = ''
            if request.args['rtype'] == 'create':
                resp_msg = 'Your deck has been created successfully.'
            elif request.args['rtype'] == 'edit':
                resp_msg = 'Your deck has been updated successfully.'

        return make_response(resp_msg, 201)
    #######################################################################################################
    elif request.method == 'DELETE':
        db_session = Session_db()
        if request.args['entity'] == 'deck':
            deck_id = request.args['id']
            deckname = db_session.query(Deck).filter_by(deck_id=deck_id).first().name
            try:
                user = db_session.query(User).filter_by(user_name=session.get('user').get('user_name')).first()
                deck = db_session.query(Deck).filter_by(deck_id=deck_id).first()
                db_session.add(Activity(user_id=user.user_id, a_type='DELETE', target=deck.name,
                                        date_time=datetime.utcnow().strftime("%A, %B-%d %Y, %H:%M:%S UTC")))
                user_deck = db_session.query(UserDeck).filter_by(user_id=user.user_id, deck_id=deck_id).first()
                cards = db_session.query(Card).filter_by(deck_id=deck_id).all()
                if user_deck.privacy == 'external':
                    for c in cards:
                        db_session.query(UserCard).filter_by(card_id=c.card_id, user_id=user.user_id).delete()
                    db_session.query(UserDeck).filter_by(deck_id=deck_id, user_id=user.user_id).delete()
                else:
                    for c in cards:
                        db_session.query(UserCard).filter_by(card_id=c.card_id).delete()
                    db_session.query(UserDeck).filter_by(deck_id=deck_id).delete()
                    db_session.query(Card).filter_by(deck_id=deck_id).delete()
                    db_session.query(Deck).filter_by(deck_id=deck_id).delete()
                db_session.flush()
            except SQLAlchemyError as e:
                db_session.rollback()
                db_session.close()
                abort(500, e.code)
            else:
                db_session.commit()
                return make_response("Successfully deleted the deck - " + deckname + " from your collection", 200)
            finally:
                db_session.close()
        elif request.args['entity'] == 'card':
            card_id = request.args['id']
            try:
                db_session.query(Card).filter_by(card_id=card_id).delete()
                db_session.query(UserCard).filter_by(card_id=card_id).delete()
                db_session.flush()
            except SQLAlchemyError as e:
                db_session.rollback()
                db_session.close()
                abort(500, e.code)
            else:
                db_session.commit()
                return make_response('Deleted the card successfully', 202)
            finally:
                db_session.close()


@app.route('/training', methods=['GET', 'POST'])
def training():
    auth()
    if 'rtype' not in request.args or request.args['rtype'] not in ['training', 'valid', 'prev', 'next']:
        abort(400)
    rtype = request.args['rtype']
    info = session.get('user')
    if rtype in ['training', 'valid'] and 'id' not in request.args:
        abort(400)
    if (rtype == 'prev' or rtype == 'next') and ('deck' not in info or 'cards' not in info or 'index' not in info):
        abort(400)
    #####################################################################################
    if request.method == 'GET':
        db_session = Session_db()
        try:
            user = db_session.query(User).filter(User.user_name == session.get('user').get('user_name')).first()
            if request.args['rtype'] == 'training':
                deck_id = request.args['id']
                deck = db_session.query(Deck).filter(Deck.deck_id == deck_id).first()
                cards = db_session.query(Card).select_from(Card).join(UserCard) \
                    .filter(UserCard.user_id == user.user_id) \
                    .filter(Card.deck_id == deck_id).order_by(desc(UserCard.w_attempt)).all()
                session['user']['deck'] = deck_id
                session['user']['cards'] = [{'id': c.card_id, 'attempt': False, 'stat': {}} for c in cards]
                session['user']['index'] = -1
                user_deck = db_session.query(UserDeck).filter(UserDeck.user_id == user.user_id,
                                                              UserDeck.deck_id == deck.deck_id).first()
                user_deck.attempts += 1
                user_deck.la_dt = datetime.utcnow().strftime("%A, %B-%d %Y, %H:%M:%S UTC")
                db_session.add(Activity(user_id=user.user_id, a_type='ATTEMPT', target=deck.name,
                                        date_time=datetime.utcnow().strftime("%A, %B-%d %Y, %H:%M:%S UTC")))
                db_session.flush()
                return {'page': render_template('training_form.html', deck=deck, c_att=0, c_rem=len(cards))}
            elif request.args['rtype'] == 'next' or request.args['rtype'] == 'prev':
                prev_card = next_card = False
                deck_id = session['user']['deck']
                cards = session['user']['cards']
                card_index = session['user']['index']
                if request.args['rtype'] == 'next':
                    card_index += 1
                elif request.args['rtype'] == 'prev':
                    card_index -= 1
                if card_index < len(cards) - 1:
                    next_card = True
                if card_index > 0:
                    prev_card = True
                session['user']['index'] = card_index
                user_card = db_session.query(UserCard).filter(UserCard.card_id == cards[card_index]['id'],
                                                              UserCard.user_id == user.user_id).first()
                card = db_session.query(Card).filter(Card.card_id == cards[card_index]['id']).first()
                deck = db_session.query(Deck).filter(Deck.deck_id == deck_id).first()
                if 'choices' not in session['user']['cards'][card_index]:
                    choices = prepare_choices(db_session, card, deck, user)
                    session['user']['cards'][card_index]['choices'] = choices
                else:
                    choices = session['user']['cards'][card_index]['choices']
                attempt = session['user']['cards'][card_index]['attempt']
                stat = session['user']['cards'][card_index]['stat']
                this_card = render_template('card.html', card=card, card_index=card_index, stat=stat,
                                            user_card=user_card, choices=choices, attempt=attempt)
                return {'prev': prev_card, 'this': this_card, 'next': next_card}
        except SQLAlchemyError:
            traceback.print_exc()
            db_session.rollback()
            db_session.close()
            abort(500)
        except KeyError:
            traceback.print_exc()
            db_session.rollback()
            db_session.close()
            abort(500)
        finally:
            db_session.commit()
            db_session.close()
    #################################################################################################################
    elif request.method == 'POST':
        if request.args['rtype'] == 'valid':
            db_session = Session_db()
            try:
                user = db_session.query(User).filter(User.user_name == session.get('user').get('user_name')).first()
                option_id = int(request.args['id'])
                card_index = session['user']['index']
                choices = session['user']['cards'][card_index]['choices']
                answer = choices[option_id]
                card_id = session['user']['cards'][card_index]['id']
                user_card = db_session.query(UserCard).filter(UserCard.user_id == user.user_id,
                                                              UserCard.card_id == card_id).first()
                card = db_session.query(Card).filter(Card.card_id == card_id).first()
                correct_id = 0
                for i, c in enumerate(choices):
                    if c == card.answer:
                        correct_id = i
                        break
                if card.answer == answer:
                    user_card.c_attempt += 1
                    db_session.flush()
                    stat = {'valid': True, 'correct_id': correct_id, 'option_id': option_id}
                else:
                    user_card.w_attempt += 1
                    db_session.flush()
                    stat = {'valid': False, 'correct_id': correct_id, 'option_id': option_id}
                session['user']['cards'][card_index]['attempt'] = True
                session['user']['cards'][card_index]['stat'] = stat
                c_att = 0
                for c in session['user']['cards']:
                    if c['attempt']:
                        c_att += 1
                stat['c_att'] = c_att
                stat['c_rem'] = len(session['user']['cards']) - c_att
                return stat
            except SQLAlchemyError:
                db_session.rollback()
                db_session.close()
                abort(500)
            finally:
                db_session.commit()
                db_session.close()


def prepare_choices(db_session, card, deck, user):
    choices = [card.answer]
    cards = db_session.query(Card).select_from(Card).join(Deck).join(UserDeck).join(Genre) \
        .filter(or_(UserDeck.privacy == 'public', UserDeck.privacy == 'external',
                    and_(UserDeck.privacy == 'private', UserDeck.user_id == user.user_id))) \
        .filter(Genre.genre_id == deck.genre_id).filter(Card.card_id != card.card_id).all()
    random.shuffle(cards)
    n = 3
    if len(cards) < 3:
        n = len(cards)
    choices += [c.answer for c in random.sample(cards, n)]
    random.shuffle(choices)
    return choices


@app.route('/cleardata')
def clear_training_data():
    auth()
    session.get('user').pop('deck', None)
    session.get('user').pop('cards', None)
    session.get('user').pop('index', None)
    return make_response('', 202)


@app.errorhandler(HTTPException)
def error(exc):
    _err = Error(code=exc.description)
    return render_template('errorpage.html',
                           code=exc.code,
                           msg=_err.msg,
                           desc=_err.desc,
                           actions=_err.action), exc.code


if __name__ == '__main__':
    app.run()
