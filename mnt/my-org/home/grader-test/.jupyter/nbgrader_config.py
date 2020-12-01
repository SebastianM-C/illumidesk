
c = get_config()

c.CourseDirectory.root = '/home/grader-test/test'
c.CourseDirectory.course_id = 'test'
c.ClearSolutions.code_stub = {
    'python': '# your code here
raise NotImplementedError',
    'javascript': '// your code here
throw new Error();',
    'julia': '# your code here
throw(ErrorException())'
}
