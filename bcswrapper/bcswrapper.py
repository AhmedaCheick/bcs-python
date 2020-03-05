import json
import os
from datetime import datetime

import requests


class Bootcampspot:
    """API wrapper class
    """

    def __init__(self, student_ok=False):
        '''Get Auth and call `/me` endpoint for course info'''

        # set up your login credentials
        # as environment variables with:
        # os.environ['BCS_USER'] = 'my.email@email.com'
        # os.environ['BCS_PASS'] = 'mypassword123'

        _creds = {"email": os.environ['BCS_USER'],
                  "password": os.environ['BCS_PASS']}

        self._bcs_root = "https://bootcampspot.com/api/instructor/v1"
        response = requests.post(
            f"{self._bcs_root}/login", json=_creds)
        self._auth = response.json()['authenticationInfo']['authToken']
        self._head = {
            'Content-Type': 'application/json',
            'authToken': self._auth
        }
        # Get relevent values
        me = requests.get(
            self._bcs_root + "/me", headers=self._head).json()
        self.user = me['userAccount']
        if student_ok:
            stu_check = None
        else:
            stu_check = 2
        self.courses = [{'courseName': enrollment['course']['name'], 'courseId': enrollment['courseId'], 'enrollmentId': enrollment['id']}
                        for enrollment in me['enrollments'] if enrollment['courseRoleId'] != stu_check]
        self._course = None
        self._enrollment = None

        self.course_list = [course['courseId']
                            for course in self.courses]

        self.enrollment_list = [course['enrollmentId']
                                for course in self.courses]

    def __repr__(self):
        '''Return list of course details on print'''
        return json.dumps(self.courses)

    @property
    def enrollment(self):
        return self._enrollment

    @enrollment.setter
    def enrollment(self, enrollmentId=int):
        if enrollmentId not in self.enrollment_list:
            raise EnrollmentError(enrollmentId, self.enrollment_list)
        else:
            self.enrollment = enrollmentId

    @property
    def course(self):
        return self._course

    @course.setter
    def course(self, courseId=int):
        if courseId not in self.course_list:
            raise CourseError(courseId, self.course_list)
        else:
            self._course = courseId
            self._enrollment = [course['enrollmentId']
                                for course in self.courses if course['courseId'] == self._course][0]

    def _course_check(self, _course):
        # Set courseId if not set
        if not _course == None:
            if _course not in self.course_list:
                raise CourseError(_course, self.course_list)
            else:
                return _course
        else:
            return self.course

    def _enrollment_check(self, _enrollment):
        # Set enrollmentId if not set
        if not _enrollment == None:
            if _enrollment not in self.enrollment_list:
                raise EnrollmentError(_enrollment, self.enrollment_list)
            else:
                return _enrollment
        else:
            return self.enrollment

    def _call(self, endpoint=str, body=dict):
        '''Grab response from endpoint'''
        response = requests.post(
            f"{self._bcs_root}/{endpoint}", headers=self._head, json=body)
        if response.status_code == 200:
            return response.json()

    def grades(self, courseId=None, milestones=False):
        '''Grabs grades for students'''

        '''API Response:
        
          {
        "assignmentTitle": str,
        "studentName": str,
        "submitted": bool,
        "grade": str
        },
        '''

        courseId = self._course_check(courseId)

        body = {'courseId': courseId}
        response = self._call('grades', body)
        _grades = {}

        def _value_check(grade):
            if type(grade) != str or grade == None:
                return "Not Submitted"
            else:
                return grade

        for assignment in response:
            if 'Milestone' in assignment['assignmentTitle'] and not milestones:
                pass
            else:
                try:
                    _grades[assignment['assignmentTitle']
                            ][assignment['studentName']] = _value_check(assignment['grade'])
                except:
                    _grades[assignment['assignmentTitle']] = {
                        assignment['studentName']: _value_check(assignment['grade'])}

        return _grades

    def sessions(self, courseId=int, enrollmentId=int):
        '''Grabs Current Week's Sessions

        Response:
            currentWeekSessions: {'session': {
                'name': 'Stuff', 'startTime': ISO8601}}

        '''
        courseId = self._course_check(courseId)
        enrollmentId = self._enrollment_check(enrollmentId)

        body = {'enrollmentId': enrollmentId}

        # Perform API call
        sessions = self._call('sessions', body=body)

        sessions_list = []

        # Loop through current week sessions
        for session in sessions['currentWeekSessions']:

            session_info = session['session']
            session_type = session['context']['contextCode']

            # Filter on courseId and session code (to remove career entries)
            # Pull out session name, start time (ISO 8601 with UTC TZ removed)
            if session_info['courseId'] == courseId and session_type == 'academic':
                sessions_list.append({'id': session_info['id'],
                                      'name': session_info['name'],
                                      'startTime': session_info['startTime'][:-1],
                                      'chapter': session_info['chapter']})

        return sessions_list

    def attendance(self, courseId=None, by='session'):
        '''Grab attendance

            Returns dict of {studentName: ('absences', 'pending', 'remote')}
        '''
        '''
        API Response Format:
        {
         'sessionName': str,
         'studentName': str,
         'pending': bool,
         'present': bool,
         'remote': bool,
         'excused': bool | |None
         }
        '''
        courseId = self._course_check(courseId)

        body = {'courseId': courseId}
        response = self._call(endpoint='attendance', body=body)

        def switch(session):
            if session['present'] == True and session['remote'] == False:
                return 'present'
            elif session['remote'] == True:
                return 'remote'
            elif session['excused'] == True and not session['excused'] == None:
                return 'excused'
            elif session['present'] == False and session['excused'] == False:
                return 'absent'

        _attendance = {}
        if by == 'session':
            by_not = 'student'
        else:
            by_not = 'session'

        for session in response:
            try:
                _attendance[session[by+'Name']][session[by_not+'Name']] = switch(
                    session)
            except:
                _attendance[session[by+'Name']] = {
                    session[by_not+'Name']: switch(session)}

        # {session['studentName']: {session['sessionName']: switch(
        #     session['pending'], session['present'], session['remote'])} for session in response}

        return _attendance

    def session_details(self, enrollmentId=int, courseId=int):
        '''Grabs info on today's class @TODO support for manual datetime entries)
        '''

        '''
        API Response Format:
        {"session": {"session": {'id': int, 'courseId': int,
            'shortDescription': str}, 'videobcs_rootList': []}}
        '''

        cur_date = datetime.utcnow().date()
        session_list = self.sessions(
            enrollmentId=enrollmentId, courseId=courseId)

        current_session_id = None

        for session in session_list:
            if datetime.fromisoformat(session['startTime']).date() == cur_date:
                current_session_id = session['id']
                break

        body = {'sessionId': current_session_id}
        session_detail_response = self._call('sessionDetail', body)

        return session_detail_response['session']


class BCSError(Exception):
    '''Base class for BCS errors'''

    def __init__(self, arg1, arg2, arg3):
        self.arg1 = arg1
        self.arg2 = arg2
        self.arg3 = arg3

    def __str__(self):
        return f"Uh oh! {self.arg1} not a valid {self.arg3}\nTry one of these: {self.arg2}"


class CourseError(BCSError):
    '''Course not in courses error'''

    def __init__(self, arg1, arg2):
        super().__init__(arg1, arg2, 'course')


class EnrollmentError(BCSError):
    '''Enrollment not in enrollments error'''

    def __init__(self, arg1, arg2):
        super().__init__(arg1, arg2, 'enrollment')