#coding=utf-8
import csv
import math
import random
import re
import time
random.seed(int(time.time()))
import sys,hashlib
reload(sys)
sys.setdefaultencoding('utf8')
import web
web.config.debug = False
from web import form

#数据库连接
db = web.database(dbn = 'mssql', user = 'SA', host = 'aposta.yun', pw = 'JC4xvyp!', db = 'UserListDB')
#res = db.query("SELECT * FROM users")
#db.insert("users", uname = 'test{}'.format(len(res)), password = 'asdf', email = 'fake')
res = db.query("SELECT * FROM users")
print res

#定义渲染模板位置
render = web.template.render('templates/')

#定义url
urls = (
  '/', 'index',
  '/register','register',
  '/login', 'login',
  '/logout','logout',
  '/upload', 'upload',
  '/test', 'test',
  '/clockin', 'clockin',
  '/addfriend', 'addfriend',
)

app = web.application(urls, globals())
session = web.session.Session(app,
        web.session.DiskStore('sessions'), 
        initializer={'username': None, 'teststatus': None}
    )


loginform = form.Form(
    form.Textbox('username',
        form.notnull,
        form.regexp('[A-Za-z0-9\-]+', 'Must be alpha or digit!')),
        #form.Validator('Must be more than 5 characters!', y:len(y)>5)),
    form.Password('password',
        form.notnull,
        form.regexp('[A-Za-z0-9\-]+', 'Must be alpha or digit!')),
        #form.Validator('Must be more than 5 characters!', lambda y:len(y)>5)),
    form.Button('Login')
)


class TestStatus:
    def __init__(self, user):
        self.user = user
        self.count = 0
        self.time = int(time.time())
        self.correct = 0

    def correctness(self):
        self.count += 1
        self.correct += 1

    def incorrect(self):
        self.count += 1

    def reset(self):
        self.count = 0
        self.time = int(time.time())
        self.correct = 0

    def writeback(self):
        cr = 1.
        if self.count != 0:
            cr = float(self.correct) / self.count
        db.insert('testresult',
                uname = self.user,
                testtime = self.time,
                count = self.count,
                correctness = cr
            )
        act = Activity(user = self.user, 
                atype = Activity.str2type('testing'),
                cnt = self.count
            )
        uploadActivity(act)



class Word:
    def __init__(self, name, mean, count):
        self.name = name
        self.mean = mean
        self.count = count

    def addcount(self):
        self.count += 1

    def writeback(self, user):
        t = db.transaction()
        db.query("UPDATE word SET count = $cnt WHERE uname = $name AND wordname = $word",
                vars = {'cnt': self.count, 'name': user, 'word': self.name})
        t.commit()

"""
count ranged from 0 to inf
lottery ranged from 7 to 1
"""
def getLottery(count):
    return math.floor(math.exp(-count) * 6) + 1

def getRandomWordFromDB(user):
    words = db.query("SELECT * FROM word WHERE uname = $name",
            vars = {'name': user}
        )
    total = 0
    if len(words) == 0:
        return Word(name = 'Please Upload Some Words First!',
                mean = 'Go back to previous page, select "Upload..."',
                count = -10)
    for i in words:
        total += getLottery(int(i['count']))
    pick = random.randint(0, total)
    total = 0
    for i in words:
        total += getLottery(int(i['count']))
        if total >= pick:
            return Word( name = i['wordname'].rstrip(' '), 
                         mean = i['meaning'].rstrip(' '),
                         count = int(i['count']))
    


class Activity:
    def __init__(self, user, atype, cnt = None, word = None, content = None):
        self.type = atype
        self.user = user
        self.time = 'DEFAULT'
        self.cnt = cnt
        self.word = word
        self.content = content

    def settime(self, time):
        self.time = time

    def getcontent(self):
        if not self.content == None:
            return self.content

        if self.type == 1 and self.cnt != None:
            return 'uploaded {} new words'.format(self.cnt)
        elif self.type == 2 and self.cnt != None:
            return 'conducted a test of {} words'.format(self.cnt)
        elif self.type == 3 and self.word != None:
            return 'shared a new word {}'.format(self.word)
        elif self.type == 4:
            return 'commited the clock-in today'
        return None

    def __str__(self):
        return '{} {}'.format(self.user, self.getcontent())

    @staticmethod
    def type2str(inttype):
        if inttype == 1:
            return 'upload'
        elif inttype == 2:
            return 'testing'
        elif inttype == 3:
            return 'share'
        elif inttype == 4:
            return 'clockin'
        else:
            return 'unknown'

    @staticmethod
    def str2type(strtype):
        if strtype == 'upload':
            return 1
        elif strtype == 'testing':
            return 2
        elif strtype == 'share':
            return 3
        elif strtype == 'clockin':
            return 4
        else:
            return 0

def uploadActivity(a):
    t = db.transaction()
    if a.cnt == 0:  # bad activity
        return
    try:
        db.insert('activity', 
                uname = a.user,
                time = int(time.time()),
                type = a.type,
                content = a.getcontent(),
                AID = int(time.time() * 1000)
                )
    except Exception as e:
        print("Upload Activity Failed", e)
    else:
        t.commit()

def getShownAcitvity(uname):
    results = db.query("SELECT * FROM activity WHERE activity.uname = $name OR activity.uname IN (SELECT use_uname FROM friends WHERE uname = $name)", vars={'name':uname})
    out = []
    for i in results:
        acti = Activity(user = i['uname'], atype = i['type'], content = i['content'])
        acti.settime(int(i['time']))
        out.append(acti)
    out.sort(key = lambda x: x.time, reverse = True)
    if len(out) > 15:
        out = out[0:15] 
    return out

print ([str(i) for i in getShownAcitvity('huahua')])

class index: 
    def GET(self): 
        if not session.username:
            raise web.seeother('/login')
        else:
            username = session.username
            if session.teststatus != None and session.teststatus.count > 0:
                session.teststatus.writeback()
                session.teststatus.reset()
            activities = getShownAcitvity(username)
            return render.index(username, activities)

def validateRegister(i):
    if not i.username:
        return "Need a Username"
    if not i.pwd1:
        return "Need a password"
    if i.pwd1 != i.pwd2:
        return "password not identical"
    EMAIL_REGEX = re.compile("[^@]+@[^@]+\.[^@]+")
    if not EMAIL_REGEX.match(i.email):
        return "Not a valid email"

    user = db.query("SELECT uname FROM users WHERE uname = $name OR email = $mail", 
            vars = {'name':i.username, 'mail': i.email})
    if user and len(user) > 0:
        return "User/Email Already Exists!"
    return True
    
    
class register:
    def GET(self):
        return render.register("")
    def POST(self): 
        i = web.input()
        msg = validateRegister(i)
        if validateRegister(i) == True:
            userInsert = db.insert('users', 
                    uname=i.username, 
                    password=hashlib.md5(i.pwd1).hexdigest(),
                    email = i.email
            )
            #return render.index(i.username)
            raise web.seeother('/')
        else:
            print(msg)
            return render.register(msg)

class login:
    def GET(self): 
        form = loginform()
        return render.login(form,user='user')

    def POST(self): 
        form = loginform() 
        if not form.validates(): 
            return render.login(form,user='user')
        else:
            # form.d.boe and form['boe'].value are equivalent ways of
            # extracting the validated arguments from the form.
            users = db.query('select * from users where uname=$name', vars={'name':form.d.username})
            print users
            if len(users) > 0:
                result = users[0]
            else:
                result = None
            #for user in users:
            #    result = user
            if result and result['password'] == hashlib.md5(form.d.password).hexdigest():
                session.username = form.d.username
                raise web.seeother('/')
            return render.login(form,user=None)

class upload:
    def GET(self):
        if not session.username:
            raise web.seeother("/login")
        else:
            #web.header("Content-Type:", "text/html; charset=utf-8;")
            return render.upload()
    def POST(self):
        x = web.input(myfile={})
        filedir = './users'.format(session.username)
        if 'myfile' in x:
            fin = x.myfile.file
            dr = csv.DictReader(fin)
            try:
                t = db.transaction()
                names = dr.fieldnames
                to_db_i = [(session.username, i[names[0]], i[names[1]], 0) for i in dr]
                words = db.query("SELECT wordname FROM word where word.uname=$name", vars={'name': session.username})
                words = [ent['wordname'].rstrip(' ') for ent in words]
                to_db = [i for i in to_db_i if not i[1] in words]
                cursor = db._db_cursor()
                cursor.executemany("INSERT INTO word (uname, wordname, meaning, count) VALUES (%s, %s, %s, %d);", to_db)
                t.commit()
                
                wdcnt = len(to_db)
                if wdcnt > 0:
                    act = Activity(user = session.username, atype = Activity.str2type('upload'), cnt = wdcnt)
                    print(act.getcontent())
                    uploadActivity(act)
            except Exception as e:
                print("Error Occured", e)
        raise web.seeother('/')
    

class test:
    def GET(self):
        if not session.username:
            raise web.seeother("/login")
        else:
            if session.teststatus == None:
                session.teststatus = TestStatus(session.username)
            word = getRandomWordFromDB(session.username)
            if word.count >= 0:
                word.addcount()
                word.writeback(session.username)
                session.teststatus.correctness()
            return render.test(word)

class clockin:
    def GET(self):
        if not session.username:
            raise web.seeother("/login")
        else:
            start = time.time()
            start = start - start % 86400
            results = db.query("SELECT * FROM activity WHERE activity.uname = $name AND activity.time > $start", 
                    vars={'name':session.username, 'start': start})
            showmsg = "You cannot clockin as you haven't done anything today!"
            if len(results) > 0:
                showmsg = "Great! You have done today's clock-in"
                havedone = False 
                print(results)
                for i in results:
                    if Activity.type2str(int(i['type'])) == 'clockin':
                        havedone = True
                if not havedone:
                    act = Activity(user = session.username,
                        atype = Activity.str2type('clockin'),
                        )
                    uploadActivity(act)
                else:
                    print "Already have done!"
            return render.clockin(showmsg)
                
class addfriend:
    def GET(self):
        if not session.username:
            raise web.seeother("/login")
        else:
            return render.addfriend()

    def POST(self):
        i = web.input()
        if i.username:
            # query for this name
            user = db.query("SELECT uname FROM users WHERE uname = $name",
                    vars = {'name':i.username})
            if user and len(user) > 0:
                targetname = user[0]['uname']
                db.insert('friends',
                        uname = session.username,
                        use_uname = targetname
                    )
        else:
            return render.addfriend()
        raise web.seeother('/')
    

class logout:
    def GET(self):
        session.username = None
        raise web.seeother('/')


if __name__=="__main__":
    app.run()
