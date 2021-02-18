import os


c = get_config()

c.CourseDirectory.root = "/home/grader-test/test"
c.CourseDirectory.course_id = "test"
c.ClearSolutions.code_stub = {
    "python": "# your code here\nraise NotImplementedError",
    "javascript": "// your code here\nthrow new Error();",
    "julia": "# your code here\nthrow(ErrorException())"
}
