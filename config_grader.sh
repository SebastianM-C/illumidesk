if [[ $# -ne 2 ]]; then
    echo "Illegal number of parameters. Course name and grader name not provided."
    exit 2
fi


course_id="$1"
grader_name="$2"

echo "c = get_config()

c.CourseDirectory.course_id = \""$course_id"\"" > mnt/my-org/home/grader-"$course_id"/"$course_id"/nbgrader_config.py

mkdir -p mnt/my-org/home/"$grader_name"/.jupyter/
mkdir -p mnt/my-org/home/"$grader_name"/"$course_id"/

cp mnt/my-org/home/grader-"$course_id"/"$course_id"/nbgrader_config.py mnt/my-org/home/"$grader_name"/"$course_id"/
cp mnt/my-org/home/grader-"$course_id"/.jupyter/nbgrader_config.py mnt/my-org/home/"$grader_name"/.jupyter/
sed -i "s/grader-$course_id/jovyan/g" mnt/my-org/home/"$grader_name"/.jupyter/nbgrader_config.py
chown -R 1000:100 mnt/my-org/home/"$grader_name"
