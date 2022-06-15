"""Simple web server for a traffic counting application"""
#!/usr/bin/env python

# This is a simple web server for a traffic counting application.
# It's your job to extend it by adding the backend functionality to support
# recording the traffic in a SQL database. You will also need to support
# some predefined users and access/session control. You should only
# need to extend this file. The client side code (html, javascript and css)
# is complete and does not require editing or detailed understanding.
## pylint: disable=line-too-long
# import the various libraries needed
import datetime
from datetime import datetime
import http.cookies as Cookie # some cookie handling support
from http.server import BaseHTTPRequestHandler, HTTPServer # the heavy lifting of the web server
import urllib # some url parsing support
import json # support for json encoding
import sys # needed for agument handling
import sqlite3
import string
import time
from dateutil.relativedelta import relativedelta

DB_NAME =  'traffic.db' # Global variable name for traffic data base
vehicle_list = {"car": 0, "van":1, "truck":2, "taxi":3, "other":4, "motorbike":5, "bicycle":6, "bus":7}

def access_database(dbfile, query):
    """ access_database requires the name of a sqlite3 database file and the query.
        It does not return the result of the query."""
    connect = sqlite3.connect(dbfile)
    cursor = connect.cursor()
    cursor.execute(query)
    connect.commit()
    connect.close()

def access_database_with_result(dbfile, query):
    """access_database requires the name of an sqlite3 database file and the query.
       It returns the result of the query"""
    connect = sqlite3.connect(dbfile)
    cursor = connect.cursor()
    rows = cursor.execute(query).fetchall()
    connect.commit()
    connect.close()
    return rows


def build_response_refill(where, what):
    """This function builds a refill action that allows part of the
       currently loaded page to be replaced."""
    return {"type":"refill","where":where,"what":what}


def build_response_redirect(where):
    """This function builds the page redirection action
       It indicates which page the client should fetch.
       If this action is used, only one instance of it should
       contained in the response and there should be no refill action."""
    return {"type":"redirect", "where":where}


def handle_multiple_browser_logins(current_user):
    """This function handles the session when multiple browser login takes place"""
    print("Sessions before validate", access_database_with_result(DB_NAME, "SELECT * FROM session"))
    if current_user:
        user_id = access_database_with_result(DB_NAME, "SELECT userid FROM users WHERE username = '%s'"%(current_user))
        last_session = access_database_with_result(DB_NAME, "SELECT MAX(sessionid) FROM session WHERE userid = '%s' AND end = '%s'"%(user_id[0][0], 0))
        access_database(DB_NAME, "UPDATE session SET end = '%s' WHERE sessionid != '%s' AND userid = '%s' AND end = '%s'"%(int(time.time()), last_session[0][0], user_id[0][0], 0))


def handle_validate(iuser, imagic):
    """Decide if the combination of user and magic is valid"""
    ## alter as required
    if (iuser and imagic):
        user_id = access_database_with_result(DB_NAME, "SELECT userid FROM users WHERE username = '%s'"%(iuser))
        session_count = access_database_with_result(DB_NAME, "SELECT * FROM session WHERE userid = '%s' AND magic = '%s' AND end = '%s'"%(user_id[0][0], imagic, 0))
        if len(session_count) > 0:
            return True
    return False


def handle_delete_session(iuser, imagic):
    """Remove the combination of user and magic from the data base, ending the login"""
    user_id = access_database_with_result(DB_NAME, "SELECT userid FROM users WHERE username = '%s'"%(iuser))
    access_database(DB_NAME, "UPDATE session SET end = '%s' WHERE userid = '%s' AND magic = '%s'"%(int(time.time()), user_id[0][0], imagic))
    return

def handle_login_request(iuser, imagic, parameters):
    """A user has supplied a username (parameters['usernameinput'][0])
       and password (parameters['passwordinput'][0]) check if these are
       valid and if so, create a suitable session record in the database
       with a random magic identifier that is returned.
       Return the username, magic identifier and the response action set."""
    response = []
    ## alter as required
    if len(parameters) == 4:
        if (iuser and imagic):
            if handle_validate(iuser, imagic) is True:
                # the user is already logged in, so end the existing session.
                handle_delete_session(iuser, imagic)
                response.append(build_response_redirect('/index.html'))
        user_name = parameters['usernameinput'][0]
        input_pass = parameters['passwordinput'][0]
        user_password = access_database_with_result(DB_NAME, 'SELECT password FROM users WHERE username = "' + user_name + '"')
        if (user_password and (input_pass == user_password[0][0])): ## The user is valid
            response.append(build_response_redirect('/page.html'))
            user = user_name
            magic = parameters['randn'][0]
            unique_user_id = access_database_with_result(DB_NAME, 'SELECT userid FROM users WHERE username = "' + user_name + '"')
            access_database(DB_NAME, "INSERT INTO session (userid, magic, start, end) VALUES ('%s','%s','%s','%s')"%(unique_user_id[0][0], magic, int(time.time()), 0))
            handle_multiple_browser_logins(parameters['usernameinput'][0])
        else: ## The user is not valid
            response.append(build_response_refill('message', 'Invalid password'))
            user = '!'
            magic = ''
    else:
        response.append(build_response_refill('message', 'Please provide username or password'))
        user = ''
        magic = ''
    return [user, magic, response]


def validate_location(location):
    """THis function check if the location is a valid string"""
    valid_string = string.ascii_letters.lower() + string.digits + ' '
    for char in location:
        if char not in valid_string:
            return False
    return True

# def validate_type(type):
#     if type in vehicle_list.keys():
#         return True
#     else:
#         return False

def validate_occupancy(occupancy):
    """This function checks if the occupancy parameter is valid"""
    number_list = ['0','1','2','3','4']
    return(occupancy in number_list)

def handle_add_request(iuser, imagic, parameters):
    """The user has requested a vehicle be added to the count
       parameters['locationinput'][0] the location to be recorded
       parameters['occupancyinput'][0] the occupant count to be recorded
       parameters['typeinput'][0] the type to be recorded
       Return the username, magic identifier (these can be empty  strings) and the response action set."""
    response = []
    ## alter as required
    if handle_validate(iuser, imagic) is not True:
        #Invalid sessions redirect to login
        response.append(build_response_redirect('/index.html'))
        user = '!'
        magic = ''
    elif ((len(parameters) == 5) and (validate_location(parameters['locationinput'][0])) and (validate_occupancy(parameters['occupancyinput'][0]))):
        session_id = access_database_with_result(DB_NAME, "SELECT sessionid FROM session WHERE magic = '%s'"%(imagic))
        if parameters['typeinput'][0] in vehicle_list.keys():
            vehicle_type = vehicle_list[parameters['typeinput'][0]]
            access_database(DB_NAME, "INSERT INTO traffic (sessionid, time, type, occupancy, location, mode) VALUES ('%s','%s','%s','%s','%s','%s')"%(session_id[0][0], int(time.time()), vehicle_type, int(parameters['occupancyinput'][0]), parameters['locationinput'][0], 1))
            total_list = access_database_with_result(DB_NAME, "SELECT count(*) FROM traffic WHERE sessionid = '%s' AND mode = '%s'"%(session_id[0][0], 1))
            response.append(build_response_refill('message', 'Entry added.'))
            response.append(build_response_refill('total', str(total_list[0][0])))
        else:
            response.append(build_response_refill('message', 'Invalid vehicle type'))
    else:
        response.append(build_response_refill('message', 'Please provide valid details'))
        response.append(build_response_refill('total', '0'))
    user = ''
    magic = ''
    return [user, magic, response]


def handle_undo_request(iuser, imagic, parameters):
    """The user has requested a vehicle be removed from the count
       This is intended to allow counters to correct errors.
       parameters['locationinput'][0] the location to be recorded
       parameters['occupancyinput'][0] the occupant count to be recorded
       parameters['typeinput'][0] the type to be recorded
       Return the username, magic identifier (these can be empty  strings) and the response action set."""
    response = []
    ## alter as required
    try:
        if handle_validate(iuser, imagic) is not True:
            #Invalid sessions redirect to login
            response.append(build_response_redirect('/index.html'))
            user = '!'
            magic = ''
        elif ((len(parameters) == 5) and (validate_location(parameters['locationinput'][0]))):
            session_id = access_database_with_result(DB_NAME, "SELECT sessionid FROM session WHERE magic = '%s'"%(imagic))
            if session_id:
                max_time = access_database_with_result(DB_NAME, "SELECT MAX(time) FROM traffic WHERE sessionid = '%s' AND type = '%s' AND location = '%s' AND occupancy = '%s' AND mode = '%s'"%(session_id[0][0], vehicle_list[parameters['typeinput'][0]], parameters['locationinput'][0], int(parameters['occupancyinput'][0]), 1))
            if max_time:
                access_database(DB_NAME, "UPDATE traffic SET mode = '%s' WHERE time = '%s'"%(2, max_time[0][0]))
                access_database(DB_NAME, "INSERT INTO traffic (sessionid, time, type, location, occupancy, mode) VALUES ('%s', '%s', '%s', '%s', '%s', '%s')"%(session_id[0][0], int(time.time()), vehicle_list[parameters['typeinput'][0]], parameters['locationinput'][0], int(parameters['occupancyinput'][0]), 0))
                total_list = access_database_with_result(DB_NAME, "SELECT count(*) FROM traffic WHERE sessionid = '%s' AND mode = '%s'"%(session_id[0][0], 1))
                response.append(build_response_refill('message', 'Entry Un-done.'))
                response.append(build_response_refill('total', str(total_list[0][0])))
            else:
                response.append(build_response_refill('message', 'No entries available to undo for the session'))
        else:
            response.append(build_response_refill('message', 'Please provide location details'))
            response.append(build_response_refill('total', '0'))
        user = ''
        magic = ''
    except:
        response.append(build_response_refill('message', 'Record not found'))
        user = ''
        magic = ''
    return [user, magic, response]


def handle_back_request(iuser, imagic, parameters):
    """This code handles the selection of the back button on the record form (page.html)
       You will only need to modify this code if you make changes elsewhere that break its behaviour"""
    response = []
    ## alter as required
    if handle_validate(iuser, imagic) is not True:
        response.append(build_response_redirect('/index.html'))
    else:
        response.append(build_response_redirect('/summary.html'))
    user = ''
    magic = ''
    return [user, magic, response]


def handle_logout_request(iuser, imagic, parameters):
    """This code handles the selection of the logout button on the summary page (summary.html)
       You will need to ensure the end of the session is recorded in the database
       And that the session magic is revoked."""
    response = []
    ## alter as required
    if imagic:
        access_database(DB_NAME, "UPDATE session SET end = '%s' WHERE magic = '%s'"%(int(time.time()), imagic))
    response.append(build_response_redirect('/index.html'))
    user = '!'
    magic = ''
    return [user, magic, response]


def handle_summary_request(iuser, imagic, parameters):
    """This code handles a request for an update to the session summary values.
       You will need to extract this information from the database.
       You must return a value for all vehicle types, even when it's zero."""
    response = []
    ## alter as required
    if handle_validate(iuser, imagic) is not True:
        response.append(build_response_redirect('/index.html'))
        user = '!'
        magic = ''
    else:
        session_id = access_database_with_result(DB_NAME, "SELECT sessionid FROM session WHERE magic = '%s'"%(imagic))
        if session_id:
            vehicle_sum_list = ['sum_car', 'sum_van', 'sum_truck', 'sum_taxi', 'sum_other', 'sum_motorbike', 'sum_bicycle', 'sum_bus']
            total_count = 0
            for vehicle in range(len(vehicle_sum_list)):
                count = access_database_with_result(DB_NAME, "SELECT count(*) FROM traffic WHERE sessionid = '%s' AND mode = '%s' AND type = '%s'"%(session_id[0][0], 1, list(vehicle_list.values())[vehicle]))
                total_count += count[0][0]
                response.append(build_response_refill(vehicle_sum_list[vehicle], str(count[0][0])))
            response.append(build_response_refill('total', total_count))
        else:
            response.append(build_response_refill('message', 'No summary to display for current session'))
    user = ''
    magic = ''
    return [user, magic, response]


# HTTPRequestHandler class
class myHTTPServer_RequestHandler(BaseHTTPRequestHandler):
    """HTTPRequestHandler Class"""
    # GET This function responds to GET requests to the web server.
    def do_GET(self):
        """Function respondes to get requests"""
        # The set_cookies function adds/updates two cookies returned with a webpage.
        # These identify the user who is logged in. The first parameter identifies the user
        # and the second should be used to verify the login session.
        def set_cookies(x, user, magic):
            ucookie = Cookie.SimpleCookie()
            ucookie['u_cookie'] = user
            x.send_header("Set-Cookie", ucookie.output(header='', sep=''))
            mcookie = Cookie.SimpleCookie()
            mcookie['m_cookie'] = magic
            x.send_header("Set-Cookie", mcookie.output(header='', sep=''))

        # The get_cookies function returns the values of the user and magic cookies if they exist
        # it returns empty strings if they do not.
        def get_cookies(source):
            rcookies = Cookie.SimpleCookie(source.headers.get('Cookie'))
            user = ''
            magic = ''
            for keyc, valuec in rcookies.items():
                if keyc == 'u_cookie':
                    user = valuec.value
                if keyc == 'm_cookie':
                    magic = valuec.value
            return [user, magic]

        # Fetch the cookies that arrived with the GET request
        # The identify the user session.
        user_magic = get_cookies(self)

        print(user_magic)

        # Parse the GET request to identify the file requested and the parameters
        parsed_path = urllib.parse.urlparse(self.path)

        # Decided what to do based on the file requested.

        # Return a CSS (Cascading Style Sheet) file.
        # These tell the web client how the page should appear.
        if self.path.startswith('/css'):
            self.send_response(200)
            self.send_header('Content-type', 'text/css')
            self.end_headers()
            with open('.'+self.path, 'rb') as file:
                self.wfile.write(file.read())
            file.close()

        # Return a Javascript file.
        # These tell contain code that the web client can execute.
        elif self.path.startswith('/js'):
            self.send_response(200)
            self.send_header('Content-type', 'text/js')
            self.end_headers()
            with open('.'+self.path, 'rb') as file:
                self.wfile.write(file.read())
            file.close()

        # A special case of '/' means return the index.html (homepage)
        # of a website
        elif parsed_path.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            with open('./index.html', 'rb') as file:
                self.wfile.write(file.read())
            file.close()

        # Return html pages.
        elif parsed_path.path.endswith('.html'):
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            with open('.'+parsed_path.path, 'rb') as file:
                self.wfile.write(file.read())
            file.close()

        # The special file 'action' is not a real file, it indicates an action
        # we wish the server to execute.
        elif parsed_path.path == '/action':
            self.send_response(200) #respond that this is a valid page request
            # extract the parameters from the GET request.
            # These are passed to the handlers.
            parameters = urllib.parse.parse_qs(parsed_path.query)

            if 'command' in parameters:
                # check if one of the parameters was 'command'
                # If it is, identify which command and call the appropriate handler function.
                if parameters['command'][0] == 'login':
                    [user, magic, response] = handle_login_request(user_magic[0], user_magic[1], parameters)
                    #The result of a login attempt will be to set the cookies to identify the session.
                    set_cookies(self, user, magic)
                elif parameters['command'][0] == 'add':
                    [user, magic, response] = handle_add_request(user_magic[0], user_magic[1], parameters)
                    if user == '!': # Check if we've been tasked with discarding the cookies.
                        set_cookies(self, '', '')
                elif parameters['command'][0] == 'undo':
                    [user, magic, response] = handle_undo_request(user_magic[0], user_magic[1], parameters)
                    if user == '!': # Check if we've been tasked with discarding the cookies.
                        set_cookies(self, '', '')
                elif parameters['command'][0] == 'back':
                    [user, magic, response] = handle_back_request(user_magic[0], user_magic[1], parameters)
                    if user == '!': # Check if we've been tasked with discarding the cookies.
                        set_cookies(self, '', '')
                elif parameters['command'][0] == 'summary':
                    [user, magic, response] = handle_summary_request(user_magic[0], user_magic[1], parameters)
                    if user == '!': # Check if we've been tasked with discarding the cookies.
                        set_cookies(self, '', '')
                elif parameters['command'][0] == 'logout':
                    [user, magic, response] = handle_logout_request(user_magic[0], user_magic[1], parameters)
                    if user == '!': # Check if we've been tasked with discarding the cookies.
                        set_cookies(self, '', '')
                else:
                    # The command was not recognised, report that to the user.
                    response = []
                    response.append(build_response_refill('message', 'Internal Error: Command not recognised.'))

            else:
                # There was no command present, report that to the user.
                response = []
                response.append(build_response_refill('message', 'Internal Error: Command not found.'))

            text = json.dumps(response)
            print(text)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(bytes(text, 'utf-8'))

        elif self.path.endswith('/statistics/hours.csv'):
            ## if we get here, the user is looking for a statistics file
            ## this is where requests for /statistics/hours.csv should be handled.
            ## you should check a valid user is logged in. You are encouraged to wrap this behavour in a function.
            text = "Username,Day,Week,Month\n"
            last_logout_time=access_database_with_result(DB_NAME, "select Max(end) from session")
            last_logout_datetime = datetime.fromtimestamp(last_logout_time[0][0])
            last_logout_begining = datetime(last_logout_datetime.year, last_logout_datetime.month, last_logout_datetime.day, 0 ,0, 0, 0)
            last_logout_begining_time = int(time.mktime(last_logout_begining.timetuple()))
            recent_week = last_logout_begining - relativedelta(days = 6)
            recent_week_beginning = datetime(recent_week.year, recent_week.month, recent_week.day,0,0,0,0)
            recent_week_beginning_time = int(time.mktime(recent_week_beginning.timetuple()))
            recent_month = last_logout_begining - relativedelta(months=1)
            recent_month_beginning = datetime(recent_month.year, recent_month.month, recent_month.day,0,0,0,0)
            recent_month_beginning_time = int(time.mktime(recent_month_beginning.timetuple()))
            daily_working_hours=access_database_with_result(DB_NAME, "SELECT users.username,\
                round(sum((JULIANDAY(DATEtime(session.end, 'unixepoch', 'localtime'))\
                    -JULIANDAY(DATEtime(session.start, 'unixepoch', 'localtime')))*24),1)\
                         as diff FROM users join session on users.userid=session.userid where \
                             session.end >= '%s' and session.end<= '%s' and session.end != '%s' group by session.userid"%(last_logout_begining_time, last_logout_time[0][0], 0))
            weekly_working_hours=access_database_with_result(DB_NAME, "SELECT users.username,\
                round(sum((JULIANDAY(DATEtime(session.end, 'unixepoch', 'localtime'))\
                    -JULIANDAY(DATEtime(session.start, 'unixepoch', 'localtime')))*24),1)\
                         as diff FROM users join session on users.userid=session.userid where\
                              session.end >= '%s' and session.end<= '%s' and session.end != '%s' group by session.userid"%(recent_week_beginning_time, last_logout_time[0][0], 0))
            yearly_working_hours=access_database_with_result(DB_NAME,"SELECT users.username,\
                round(sum((JULIANDAY(DATEtime(session.end, 'unixepoch', 'localtime'))-\
                    JULIANDAY(DATEtime(session.start, 'unixepoch', 'localtime')))*24),1)\
                         as diff FROM users join session on users.userid=session.userid where\
                              session.end >= '%s' and session.end<= '%s' and session.end != '%s' group by session.userid"%(recent_month_beginning_time, last_logout_time[0][0], 0))
            usernames = access_database_with_result(DB_NAME, "select username from users where username != '%s'"%(0))
            for user in usernames:
                working_hours=[0.0,0.0,0.0]
                for row in daily_working_hours:
                    if user[0]==row[0]:
                        working_hours[0] = row[1]
                for row in weekly_working_hours:
                    if user[0]==row[0]:
                        working_hours[1] = row[1]
                for row in yearly_working_hours:
                    if user[0]==row[0]:
                        working_hours[2] = row[1]
                text += user[0] + "," + str(working_hours[0]) + "," + str(working_hours[1]) + "," + str(working_hours[2]) + "\n"

            encoded = bytes(text, 'utf-8')
            self.send_response(200)
            self.send_header('Content-type', 'text/csv')
            self.send_header("Content-Disposition", 'attachment; filename="{}"'.format('hours.csv'))
            self.send_header("Content-Length", len(encoded))
            self.end_headers()
            self.wfile.write(encoded)

        elif self.path.endswith('/statistics/traffic.csv'):
            ## if we get here, the user is looking for a statistics file
            ## this is where requests for  /statistics/traffic.csv should be handled.
            ## you should check a valid user is checked in. You are encouraged to wrap this behavour in a function.
            print(access_database_with_result(DB_NAME, "SELECT * FROM traffic"))
            recent_entry_day = access_database_with_result(DB_NAME, "SELECT MAX(time) FROM traffic")
            if recent_entry_day:
                recent_time_stamp = recent_entry_day[0][0]
                recent_day_time_obj = datetime.fromtimestamp(recent_time_stamp)
                recent_day_begining_date_time_obj = datetime(recent_day_time_obj.year, recent_day_time_obj.month, recent_day_time_obj.day, 0, 0, 0, 0)
                recent_day_begining_timestamp = int(time.mktime(recent_day_begining_date_time_obj.timetuple()))
                rows = access_database_with_result(DB_NAME, "SELECT location,type,occupancy,\
                    COUNT(occupancy) FROM traffic where mode = '%s' and time between '%s' and '%s' GROUP BY location,\
                        type"%(1, recent_day_begining_timestamp, recent_time_stamp))
                text = "Location,Type,Occupancy1,Occupancy2,Occupancy3,Occupancy4\n"
                type={0:"car", 1:"van", 2:"truck", 3:"taxi", 4:"other", 5:"motorbike", 6:"bicycle", 7:"bus"}
                for row in rows:
                    location, vehicle, occupancy = row[0], type[row[1]],[0,0,0,0]
                    for index in range(4):
                        if row[2] == index + 1:
                            occupancy[index] = row[3]
                            break
                    text += location + "," + vehicle + "," + str(occupancy[0]) + "," + str(occupancy[1]) + ",\
                        " + str(occupancy[2]) + "," + str(occupancy[3]) + "\n"
                encoded = bytes(text, 'utf-8')
                self.send_response(200)
                self.send_header('Content-type', 'text/csv')
                self.send_header("Content-Disposition", 'attachment; filename="{}"'.format('traffic.csv'))
                self.send_header("Content-Length", len(encoded))
                self.end_headers()
                self.wfile.write(encoded)

        else:
            # A file that does n't fit one of the patterns above was requested.
            self.send_response(404)
            self.end_headers()
        return

def run():
    """This is the entry point function to this code."""
    print('starting server...')
    ## You can add any extra start up code here
    # Server settings
    # Choose port 8081 over port 80, which is normally used for a http server
    if len(sys.argv) < 2: # Check we were given both the script name and a port number
        print("Port argument not provided.")
        return
    server_address = ('127.0.0.1', int(sys.argv[1]))
    httpd = HTTPServer(server_address, myHTTPServer_RequestHandler)
    print('running server on port =',sys.argv[1],'...')
    httpd.serve_forever() # This function will not return till the server is aborted.

run()
