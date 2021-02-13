if [[ $# -ne 2 ]]; then
    echo "Illegal number of parameters. Course name and grader name not provided."
    exit 2
fi


course_id="$1"
grader_name="$2"

cp mnt/my-org/home/grader-"$course_id"/"$course_id"/lti_grades_sender_assignments.json mnt/my-org/home/"$grader_name"/"$course_id"/
